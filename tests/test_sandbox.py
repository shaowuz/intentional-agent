"""File isolation tests and explicitly conditional Docker integration checks."""

import asyncio
import io
import os
import tarfile

import pytest

from intentional_agent import sandbox as module
from intentional_agent.sandbox import AgentSandbox, MAX_FILE_BYTES, docker_available


def test_private_files_persist_and_stay_separate(tmp_path):
    sandbox = AgentSandbox(tmp_path)
    sandbox.write_file("run-a", "agent-a", "notes/history.txt", "Private memory")
    assert sandbox.read_file("run-a", "agent-a", "notes/history.txt")["content"] == "Private memory"
    for run, agent in [("run-b", "agent-a"), ("run-a", "agent-b")]:
        with pytest.raises(RuntimeError, match="does not exist"):
            sandbox.read_file(run, agent, "notes/history.txt")


def test_list_files_returns_only_own_relative_files(tmp_path):
    sandbox = AgentSandbox(tmp_path)
    sandbox.write_file("run", "one", "notes/strategy.txt", "remember")
    sandbox.write_file("run", "two", "secret.txt", "private")
    assert sandbox.list_files("run", "one") == {
        "files": [{"path": "notes/strategy.txt", "bytes": 8}]
    }
    assert sandbox.list_files("other-run", "one") == {"files": []}


@pytest.mark.parametrize("path", ["../secret", "/etc/passwd", "a/../../secret", "a\\secret", "C:/secret", "a\x00b", "."])
def test_paths_cannot_escape_workspace(tmp_path, path):
    sandbox = AgentSandbox(tmp_path)
    with pytest.raises(RuntimeError):
        sandbox.write_file("run", "agent", path, "unsafe")
    with pytest.raises(RuntimeError):
        sandbox.read_file("run", "agent", path)


def test_symlink_file_and_directory_are_rejected(tmp_path):
    sandbox = AgentSandbox(tmp_path / "workspaces")
    outside = tmp_path / "outside.txt"
    outside.write_text("Never return this")
    workspace = sandbox.workspace("run", "agent")
    (workspace / "link").symlink_to(outside)
    (workspace / "directory").symlink_to(tmp_path, target_is_directory=True)
    for path in ["link", "directory/outside.txt"]:
        with pytest.raises(RuntimeError):
            sandbox.read_file("run", "agent", path)
        with pytest.raises(RuntimeError):
            sandbox.write_file("run", "agent", path, "overwrite")
    assert outside.read_text() == "Never return this"


def test_run_and_agent_directories_cannot_be_links(tmp_path):
    sandbox = AgentSandbox(tmp_path / "workspaces")
    (sandbox.root / "run").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(RuntimeError):
        sandbox.workspace("run", "agent")
    with pytest.raises(RuntimeError):
        sandbox.workspace("../run", "agent")


def test_bounded_writes_and_reads(tmp_path):
    sandbox = AgentSandbox(tmp_path)
    with pytest.raises(RuntimeError, match="write limit"):
        sandbox.write_file("run", "agent", "large.txt", "x" * (MAX_FILE_BYTES + 1))
    workspace = sandbox.workspace("run", "agent")
    (workspace / "large.txt").write_bytes(b"x" * (MAX_FILE_BYTES + 1))
    with pytest.raises(RuntimeError, match="read limit"):
        sandbox.read_file("run", "agent", "large.txt")


def test_fifo_reads_fail_without_blocking(tmp_path):
    sandbox = AgentSandbox(tmp_path)
    workspace = sandbox.workspace("run", "agent")
    os.mkfifo(workspace / "pipe")
    with pytest.raises(RuntimeError, match="regular"):
        sandbox.read_file("run", "agent", "pipe")


def _tar(entries):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        root = tarfile.TarInfo("workspace")
        root.type = tarfile.DIRTYPE
        archive.addfile(root)
        for name, kind, content in entries:
            item = tarfile.TarInfo(name)
            item.type = kind
            if kind == tarfile.REGTYPE:
                item.size = len(content)
                archive.addfile(item, io.BytesIO(content))
            else:
                item.linkname = content.decode()
                archive.addfile(item)
    return buffer.getvalue()


def test_valid_snapshot_replaces_only_own_workspace(tmp_path):
    sandbox = AgentSandbox(tmp_path)
    sandbox.write_file("run", "one", "old.txt", "old")
    sandbox.write_file("run", "two", "other.txt", "other")
    workspace = sandbox.workspace("run", "one")
    sandbox._persist_archive(workspace, _tar([("workspace/new.txt", tarfile.REGTYPE, b"new")]))
    assert sandbox.read_file("run", "one", "new.txt")["content"] == "new"
    assert not (workspace / "old.txt").exists()
    assert sandbox.read_file("run", "two", "other.txt")["content"] == "other"


@pytest.mark.parametrize("entries", [
    [("workspace/../escape", tarfile.REGTYPE, b"bad")],
    [("/workspace/escape", tarfile.REGTYPE, b"bad")],
    [("workspace/link", tarfile.SYMTYPE, b"/etc/passwd")],
    [("workspace/link", tarfile.LNKTYPE, b"workspace/file")],
    [("workspace/file", tarfile.REGTYPE, b"one"), ("workspace/file", tarfile.REGTYPE, b"two")],
    [("workspace/huge", tarfile.REGTYPE, b"x" * (MAX_FILE_BYTES + 1))],
])
def test_untrusted_snapshot_is_rejected_atomically(tmp_path, entries):
    sandbox = AgentSandbox(tmp_path)
    sandbox.write_file("run", "agent", "saved.txt", "keep")
    with pytest.raises(RuntimeError):
        sandbox._persist_archive(sandbox.workspace("run", "agent"), _tar(entries))
    assert sandbox.read_file("run", "agent", "saved.txt")["content"] == "keep"
    assert not (tmp_path / "run" / "escape").exists()


def test_docker_missing_never_executes_host_code(tmp_path, monkeypatch):
    monkeypatch.setattr(module, "docker_available", lambda: False)
    sandbox = AgentSandbox(tmp_path / "workspaces")
    marker = tmp_path / "must-not-exist"
    with pytest.raises(RuntimeError, match="no host fallback"):
        asyncio.run(sandbox.run_python("run", "agent", f"open({str(marker)!r}, 'w').write('bad')"))
    assert not marker.exists()


def test_command_output_is_bounded():
    import sys

    result = asyncio.run(module._command([sys.executable, "-c", "print('x' * 100000)"], output_limit=1024))
    assert len(result.stdout) == 1024
    assert result.truncated


def test_failed_cleanup_is_retried_and_reported(tmp_path, monkeypatch):
    calls = []

    async def fake_command(arguments, **kwargs):
        calls.append(arguments)
        if arguments[1] == "rm":
            return module._CommandResult(1, b"", b"daemon unavailable")
        if arguments[-1] == "-":
            return module._CommandResult(None, b"", b"", timed_out=True)
        return module._CommandResult(0, b"", b"")

    monkeypatch.setattr(module, "_command", fake_command)
    sandbox = AgentSandbox(tmp_path)
    with pytest.raises(module.SandboxCleanupError, match="cleanup could not be confirmed"):
        asyncio.run(sandbox._execute(sandbox.workspace("run", "agent"), "while True: pass", 1))
    assert sum(command[1] == "rm" for command in calls) == 2
    create = calls[0]
    assert create[create.index("--network") + 1] == "none"
    assert "--read-only" in create
    assert "--mount" not in create and "-v" not in create
    assert create[create.index("--pull") + 1] == "never"


def test_cleanup_retry_can_recover(monkeypatch):
    attempts = []

    async def fake_command(arguments, **kwargs):
        attempts.append(arguments)
        return module._CommandResult(1 if len(attempts) == 1 else 0, b"", b"temporary error")

    monkeypatch.setattr(module, "_command", fake_command)
    asyncio.run(module._remove_container("isolated-test"))
    assert len(attempts) == 2


def test_cancelled_execution_still_removes_container(tmp_path, monkeypatch):
    calls = []

    async def fake_command(arguments, **kwargs):
        calls.append(arguments)
        if arguments[-1] == "-":
            raise asyncio.CancelledError()
        return module._CommandResult(0, b"", b"")

    monkeypatch.setattr(module, "_command", fake_command)
    sandbox = AgentSandbox(tmp_path)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(sandbox._execute(sandbox.workspace("run", "agent"), "pass", 1))
    assert calls[-1][1:3] == ["rm", "--force"]


@pytest.mark.skipif(not docker_available(), reason="Docker daemon unavailable; actual isolation integration is not tested locally")
def test_docker_executes_persists_and_blocks_network(tmp_path):
    sandbox = AgentSandbox(tmp_path)
    sandbox.write_file("run", "agent", "memory.txt", "persistent")
    sandbox.write_file("run", "other", "secret.txt", "other agent secret")
    code = """
import os
import socket
from pathlib import Path
assert os.getuid() != 0
assert Path('memory.txt').read_text() == 'persistent'
assert not Path('/var/run/docker.sock').exists()
assert not Path('../other/secret.txt').exists()
assert not Path('/input').exists()
assert not Path('/host').exists()
try:
    socket.create_connection(('1.1.1.1', 443), timeout=1)
except OSError:
    print('network blocked')
else:
    raise AssertionError('public network must be blocked')
Path('result.txt').write_text('saved')
print('isolated execution complete')
"""
    result = asyncio.run(sandbox.run_python("run", "agent", code, timeout=10))
    assert result["exit_code"] == 0, result
    assert result["files_persisted"], result
    assert "network blocked" in result["stdout"]
    assert sandbox.read_file("run", "agent", "result.txt")["content"] == "saved"
    second = asyncio.run(sandbox.run_python("run", "agent", "print(open('result.txt').read())"))
    assert second["stdout"].strip() == "saved"


@pytest.mark.skipif(not docker_available(), reason="Docker daemon unavailable; actual timeout integration is not tested locally")
def test_docker_timeout_does_not_persist_partial_files(tmp_path):
    sandbox = AgentSandbox(tmp_path)
    result = asyncio.run(sandbox.run_python("run", "agent", "import time\nopen('partial', 'w').write('no')\ntime.sleep(30)", timeout=0.3))
    assert result["timed_out"]
    assert not result["files_persisted"]
    with pytest.raises(RuntimeError, match="does not exist"):
        sandbox.read_file("run", "agent", "partial")
