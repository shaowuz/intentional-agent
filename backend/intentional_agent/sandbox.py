"""Bounded private files and Docker-only, network-disabled Python execution.

The container never receives a writable host mount. A validated snapshot of one
agent's workspace is copied into bounded tmpfs, then validated before persistence.
This module never executes agent code with the server's Python interpreter.
"""

from __future__ import annotations

import asyncio
import io
import os
import re
import shutil
import stat
import subprocess
import tarfile
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


MAX_FILE_BYTES = 128 * 1024
MAX_WORKSPACE_BYTES = 8 * 1024 * 1024
MAX_WORKSPACE_ENTRIES = 256
MAX_CODE_BYTES = 64 * 1024
MAX_OUTPUT_BYTES = 32 * 1024
MAX_ARCHIVE_BYTES = MAX_WORKSPACE_BYTES + 2 * 1024 * 1024
SANDBOX_IMAGE = os.environ.get("INTENTIONAL_AGENT_SANDBOX_IMAGE", "python:3.12-slim")
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,95}\Z")
_docker_cache: tuple[float, bool] = (0.0, False)

# Docker's cp endpoint does not reliably traverse tmpfs mounts. These fixed
# programs run through docker exec and stream archives without a shell.
_IMPORT_WORKSPACE = """
import pathlib, shutil, sys, tarfile
with tarfile.open(fileobj=sys.stdin.buffer, mode='r|') as archive:
    for member in archive:
        target = pathlib.Path('/workspace') / member.name
        if member.isdir():
            target.mkdir(mode=0o700, parents=True, exist_ok=True)
        elif member.isfile():
            target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            with archive.extractfile(member) as source, target.open('xb') as destination:
                shutil.copyfileobj(source, destination)
            target.chmod(0o600)
        else:
            raise ValueError('Only validated files and directories can be imported')
"""
_EXPORT_WORKSPACE = """
import sys, tarfile
with tarfile.open(fileobj=sys.stdout.buffer, mode='w|') as archive:
    archive.add('/workspace', arcname='workspace', recursive=True)
"""


def docker_available() -> bool:
    """Check the Docker daemon, caching for five seconds and bounding the wait."""
    global _docker_cache
    now = time.monotonic()
    if now - _docker_cache[0] < 5:
        return _docker_cache[1]
    available = False
    if shutil.which("docker"):
        try:
            result = subprocess.run(
                ["docker", "info", "--format", "{{.ServerVersion}}"],
                capture_output=True,
                timeout=2,
                check=False,
            )
            available = result.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            pass
    _docker_cache = (now, available)
    return available


def _parts(value: str) -> tuple[str, ...]:
    if not isinstance(value, str) or not value or len(value) > 1024:
        raise RuntimeError("Provide a nonempty workspace-relative file path.")
    if "\\" in value or "\x00" in value or ":" in value:
        raise RuntimeError("Workspace paths must be relative POSIX paths.")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise RuntimeError("Workspace paths must stay inside the private workspace.")
    if len(path.parts) > 16 or any(len(part) > 200 for part in path.parts):
        raise RuntimeError("Workspace path is too deeply nested or too long.")
    return path.parts


def _safe_directory(path: Path) -> None:
    try:
        path.mkdir(mode=0o700, exist_ok=True)
        mode = path.lstat().st_mode
        if not stat.S_ISDIR(mode) or stat.S_ISLNK(mode):
            raise RuntimeError("A workspace directory is not a regular directory.")
    except OSError:
        raise RuntimeError("The private workspace could not be opened.") from None


def _parent_fd(workspace: Path, parts: tuple[str, ...], create: bool = False) -> int:
    """Open a directory chain without following symlinks, including races."""
    descriptor = os.open(workspace, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in parts:
            if create:
                try:
                    os.mkdir(part, mode=0o700, dir_fd=descriptor)
                except FileExistsError:
                    pass
            child = os.open(
                part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor
            )
            os.close(descriptor)
            descriptor = child
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _inventory(workspace: Path) -> list[tuple[str, Path, bool, int]]:
    entries: list[tuple[str, Path, bool, int]] = []
    total = 0

    def visit(directory: Path) -> None:
        nonlocal total
        for item in sorted(directory.iterdir()):
            relative = item.relative_to(workspace).as_posix()
            _parts(relative)
            metadata = item.lstat()
            is_directory = stat.S_ISDIR(metadata.st_mode)
            if not is_directory and not stat.S_ISREG(metadata.st_mode):
                raise RuntimeError("Workspace files must be regular files, not links or devices.")
            size = 0 if is_directory else metadata.st_size
            if size > MAX_FILE_BYTES:
                raise RuntimeError("A workspace file exceeds the 128 KiB limit.")
            total += size
            entries.append((relative, item, is_directory, size))
            if total > MAX_WORKSPACE_BYTES or len(entries) > MAX_WORKSPACE_ENTRIES:
                raise RuntimeError("The private workspace exceeds its size or file-count limit.")
            if is_directory:
                visit(item)

    try:
        visit(workspace)
    except OSError:
        raise RuntimeError("The private workspace could not be inspected safely.") from None
    return entries


@dataclass
class _CommandResult:
    returncode: int | None
    stdout: bytes
    stderr: bytes
    timed_out: bool = False
    truncated: bool = False


class SandboxCleanupError(RuntimeError):
    """Execution must pause when the server cannot confirm container removal."""


async def _remove_container(name: str) -> None:
    for attempt in range(2):
        try:
            result = await _command(["docker", "rm", "--force", name], timeout=10)
            if result.returncode == 0 or b"no such container" in result.stderr.lower():
                return
        except OSError:
            pass
        if attempt == 0:
            await asyncio.sleep(0.1)
    raise SandboxCleanupError(
        "Sandbox cleanup could not be confirmed. Docker may still be running code; "
        "check Docker before resuming experiments."
    )


async def _command(
    arguments: list[str],
    *,
    data: bytes | None = None,
    timeout: float = 15,
    output_limit: int = MAX_OUTPUT_BYTES,
) -> _CommandResult:
    """Run the trusted Docker CLI, retaining bounded stdout and stderr."""
    process = await asyncio.create_subprocess_exec(
        *arguments,
        stdin=asyncio.subprocess.PIPE if data is not None else asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    truncated = False

    async def collect(stream: asyncio.StreamReader) -> bytes:
        nonlocal truncated
        result = bytearray()
        while chunk := await stream.read(8192):
            remaining = max(0, output_limit - len(result))
            result.extend(chunk[:remaining])
            if len(chunk) > remaining:
                truncated = True
        return bytes(result)

    async def send() -> None:
        if data is not None and process.stdin:
            try:
                process.stdin.write(data)
                await process.stdin.drain()
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                process.stdin.close()

    stdout_task = asyncio.create_task(collect(process.stdout))
    stderr_task = asyncio.create_task(collect(process.stderr))
    input_task = asyncio.create_task(send())
    timed_out = False
    try:
        await asyncio.wait_for(process.wait(), timeout=timeout)
    except TimeoutError:
        timed_out = True
        if process.returncode is None:
            process.kill()
        await process.wait()
    except BaseException:
        if process.returncode is None:
            process.kill()
        await process.wait()
        await asyncio.gather(stdout_task, stderr_task, input_task, return_exceptions=True)
        raise
    stdout, stderr, _ = await asyncio.gather(stdout_task, stderr_task, input_task)
    return _CommandResult(
        None if timed_out else process.returncode, stdout, stderr, timed_out, truncated
    )


class AgentSandbox:
    def __init__(self, root: Path):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._locks: dict[tuple[str, str], asyncio.Lock] = {}

    def workspace(self, run_id: str, agent_id: str) -> Path:
        if not all(isinstance(item, str) and _IDENTIFIER.fullmatch(item) for item in (run_id, agent_id)):
            raise RuntimeError("Invalid experiment or agent identifier.")
        directory = self.root / run_id
        _safe_directory(directory)
        workspace = directory / agent_id
        _safe_directory(workspace)
        return workspace

    def list_files(self, run_id: str, agent_id: str) -> dict:
        entries = _inventory(self.workspace(run_id, agent_id))
        return {
            "files": [
                {"path": relative, "bytes": size}
                for relative, _, directory, size in entries
                if not directory
            ]
        }

    def read_file(self, run_id: str, agent_id: str, path: str) -> dict:
        parts = _parts(path)
        workspace = self.workspace(run_id, agent_id)
        parent = descriptor = None
        try:
            parent = _parent_fd(workspace, parts[:-1])
            descriptor = os.open(
                parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent
            )
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode):
                raise RuntimeError("Only regular workspace files can be read.")
            if metadata.st_size > MAX_FILE_BYTES:
                raise RuntimeError("File exceeds the 128 KiB read limit.")
            content = bytearray()
            while chunk := os.read(descriptor, min(8192, MAX_FILE_BYTES + 1 - len(content))):
                content.extend(chunk)
                if len(content) > MAX_FILE_BYTES:
                    raise RuntimeError("File exceeds the 128 KiB read limit.")
            return {"path": "/".join(parts), "content": content.decode("utf-8"), "bytes": len(content)}
        except FileNotFoundError:
            raise RuntimeError("The requested workspace file does not exist.") from None
        except UnicodeDecodeError:
            raise RuntimeError("This file is not UTF-8 text.") from None
        except OSError:
            raise RuntimeError("The requested path is inaccessible or contains a link.") from None
        finally:
            if descriptor is not None:
                os.close(descriptor)
            if parent is not None:
                os.close(parent)

    def write_file(self, run_id: str, agent_id: str, path: str, content: str) -> dict:
        parts = _parts(path)
        if not isinstance(content, str):
            raise RuntimeError("File content must be UTF-8 text.")
        data = content.encode("utf-8")
        if len(data) > MAX_FILE_BYTES:
            raise RuntimeError("File content exceeds the 128 KiB write limit.")
        workspace = self.workspace(run_id, agent_id)
        entries = _inventory(workspace)
        previous_size = next((size for name, _, _, size in entries if name == "/".join(parts)), 0)
        if sum(size for _, _, _, size in entries) - previous_size + len(data) > MAX_WORKSPACE_BYTES:
            raise RuntimeError("The private workspace exceeds its size limit.")
        existing = {name for name, _, _, _ in entries}
        additions = sum("/".join(parts[:end]) not in existing for end in range(1, len(parts) + 1))
        if len(entries) + additions > MAX_WORKSPACE_ENTRIES:
            raise RuntimeError("The private workspace exceeds its file-count limit.")
        parent = descriptor = None
        temporary_name = f".write-{uuid.uuid4().hex}"
        try:
            parent = _parent_fd(workspace, parts[:-1], create=True)
            try:
                existing_mode = os.stat(parts[-1], dir_fd=parent, follow_symlinks=False).st_mode
                if not stat.S_ISREG(existing_mode):
                    raise RuntimeError("Only regular workspace files can be replaced.")
            except FileNotFoundError:
                pass
            descriptor = os.open(
                temporary_name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=parent,
            )
            view = memoryview(data)
            while view:
                view = view[os.write(descriptor, view):]
            os.fsync(descriptor)
            os.close(descriptor)
            descriptor = None
            os.replace(temporary_name, parts[-1], src_dir_fd=parent, dst_dir_fd=parent)
            return {"path": "/".join(parts), "bytes": len(data)}
        except OSError:
            raise RuntimeError("The workspace file could not be written safely.") from None
        finally:
            if descriptor is not None:
                os.close(descriptor)
            if parent is not None:
                try:
                    os.unlink(temporary_name, dir_fd=parent)
                except FileNotFoundError:
                    pass
                os.close(parent)

    @staticmethod
    def _archive(workspace: Path, uid: int, gid: int) -> bytes:
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode="w") as archive:
            for relative, path, directory, size in _inventory(workspace):
                entry = tarfile.TarInfo(relative)
                entry.uid, entry.gid = uid, gid
                entry.mode = 0o700 if directory else 0o600
                entry.type = tarfile.DIRTYPE if directory else tarfile.REGTYPE
                entry.size = size
                if directory:
                    archive.addfile(entry)
                else:
                    parent = _parent_fd(workspace, _parts(relative)[:-1])
                    descriptor = None
                    try:
                        descriptor = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent)
                        with os.fdopen(descriptor, "rb") as file:
                            descriptor = None
                            if not stat.S_ISREG(os.fstat(file.fileno()).st_mode):
                                raise RuntimeError("Workspace snapshot contains a non-regular file.")
                            archive.addfile(entry, file)
                    finally:
                        if descriptor is not None:
                            os.close(descriptor)
                        os.close(parent)
        return stream.getvalue()

    @staticmethod
    def _persist_archive(workspace: Path, data: bytes) -> None:
        """Validate each member; never use tarfile.extract or extractall."""
        if len(data) > MAX_ARCHIVE_BYTES:
            raise RuntimeError("The workspace export exceeds its size limit.")
        stage = Path(tempfile.mkdtemp(prefix=".snapshot-", dir=workspace.parent))
        backup = workspace.parent / f".backup-{uuid.uuid4().hex}"
        total = count = 0
        seen: set[str] = set()
        try:
            with tarfile.open(fileobj=io.BytesIO(data), mode="r:") as archive:
                for member in archive:
                    raw_parts = PurePosixPath(member.name).parts
                    if not raw_parts or raw_parts[0] != "workspace":
                        raise RuntimeError("Workspace export contains an invalid path.")
                    if len(raw_parts) == 1:
                        if not member.isdir():
                            raise RuntimeError("Workspace export root is not a directory.")
                        continue
                    relative = "/".join(_parts("/".join(raw_parts[1:])))
                    if relative in seen or (not member.isfile() and not member.isdir()):
                        raise RuntimeError("Workspace export contains duplicate paths, links, or devices.")
                    seen.add(relative)
                    count += 1
                    total += member.size
                    if member.size < 0 or member.size > MAX_FILE_BYTES or total > MAX_WORKSPACE_BYTES or count > MAX_WORKSPACE_ENTRIES:
                        raise RuntimeError("Workspace export exceeds its file or size limits.")
                    target = stage / relative
                    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                    if member.isdir():
                        target.mkdir(mode=0o700, exist_ok=True)
                    else:
                        source = archive.extractfile(member)
                        if source is None:
                            raise RuntimeError("Workspace export is incomplete.")
                        with source, target.open("xb") as destination:
                            shutil.copyfileobj(source, destination, length=8192)
                        target.chmod(0o600)
            os.replace(workspace, backup)
            try:
                os.replace(stage, workspace)
            except BaseException:
                os.replace(backup, workspace)
                raise
            shutil.rmtree(backup)
        except (OSError, tarfile.TarError):
            raise RuntimeError("Workspace export could not be validated; previous files were retained.") from None
        finally:
            if stage.exists():
                shutil.rmtree(stage)

    async def run_python(
        self, run_id: str, agent_id: str, code: str, timeout: float = 10
    ) -> dict:
        if not isinstance(code, str) or len(code.encode("utf-8")) > MAX_CODE_BYTES:
            raise RuntimeError("Python code must be text of at most 64 KiB.")
        if not isinstance(timeout, (int, float)) or not 0 < timeout <= 60:
            raise RuntimeError("Python timeout must be between 0 and 60 seconds.")
        workspace = self.workspace(run_id, agent_id)
        lock = self._locks.setdefault((run_id, agent_id), asyncio.Lock())
        async with lock:
            if not await asyncio.to_thread(docker_available):
                raise RuntimeError("Python execution requires a running Docker daemon; no host fallback is enabled.")
            return await self._execute(workspace, code, float(timeout))

    async def _execute(self, workspace: Path, code: str, timeout: float) -> dict:
        uid = (os.getuid() if hasattr(os, "getuid") else 0) or 65534
        gid = (os.getgid() if hasattr(os, "getgid") else 0) or 65534
        initial = self._archive(workspace, uid, gid)
        name = f"intentional-agent-{uuid.uuid4().hex}"
        create = [
            "docker", "create", "--name", name, "--pull", "never",
            "--network", "none", "--user", f"{uid}:{gid}", "--read-only",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "--pids-limit", "64", "--memory", "256m", "--memory-swap", "256m",
            "--cpus", "1", "--ulimit", "nofile=128:128", "--ulimit", "fsize=2097152:2097152",
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=16m,mode=1777",
            "--tmpfs", f"/workspace:rw,noexec,nosuid,size=16m,uid={uid},gid={gid},mode=0700",
            "--workdir", "/workspace", "--env", "HOME=/workspace",
            "--env", "PYTHONDONTWRITEBYTECODE=1", "--log-driver", "none",
            SANDBOX_IMAGE, "python", "-I", "-u", "-c", f"import time; time.sleep({timeout + 45})",
        ]
        try:
            result = await _command(create)
            if result.returncode != 0:
                raise RuntimeError(
                    f"The isolated Python environment could not start. Ensure Docker is running and pull {SANDBOX_IMAGE}."
                )
            if (await _command(["docker", "start", name])).returncode != 0:
                raise RuntimeError("The isolated Python environment failed to start.")
            imported = await _command(
                ["docker", "exec", "-i", name, "python", "-I", "-c", _IMPORT_WORKSPACE],
                data=initial,
            )
            if imported.returncode != 0:
                raise RuntimeError("The private workspace could not be copied into the sandbox.")
            result = await _command(
                ["docker", "exec", "-i", "--workdir", "/workspace", name, "python", "-I", "-u", "-"],
                data=code.encode("utf-8"),
                timeout=timeout,
            )
            response = {
                "engine": "docker",
                "image": SANDBOX_IMAGE,
                "stdout": result.stdout.decode("utf-8", errors="replace"),
                "stderr": result.stderr.decode("utf-8", errors="replace"),
                "exit_code": result.returncode,
                "timed_out": result.timed_out,
                "output_truncated": result.truncated,
                "files_persisted": False,
            }
            if not result.timed_out:
                snapshot = await _command(
                    ["docker", "exec", name, "python", "-I", "-c", _EXPORT_WORKSPACE],
                    output_limit=MAX_ARCHIVE_BYTES,
                )
                if snapshot.returncode != 0 or snapshot.truncated:
                    response["workspace_error"] = "Workspace export failed; previous files were retained."
                else:
                    try:
                        self._persist_archive(workspace, snapshot.stdout)
                        response["files_persisted"] = True
                    except RuntimeError as error:
                        response["workspace_error"] = str(error)
            return response
        except OSError:
            raise RuntimeError("Docker could not be started; no host fallback is enabled.") from None
        finally:
            # A create request may have succeeded in Docker even when the CLI
            # timed out. Attempt cleanup using our unique name in every case.
            cleanup = asyncio.create_task(_remove_container(name))
            try:
                await asyncio.shield(cleanup)
            except asyncio.CancelledError:
                await cleanup
                raise
