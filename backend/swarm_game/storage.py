import fcntl
import hashlib
import json
import os
import platform
import re
import tempfile
from contextlib import contextmanager
from importlib.metadata import version
from pathlib import Path

from . import __version__
from .protocol import protocol_hash


def scrub(value):
    """Defense in depth; HTTP Authorization headers never enter log objects."""
    if isinstance(value, str):
        secret = os.environ.get("OPENROUTER_API_KEY")
        if secret:
            value = value.replace(secret, "[REDACTED]")
        return re.sub(r"sk-(?:or-v1-)?[A-Za-z0-9_-]{12,}", "[REDACTED]", value)
    if isinstance(value, dict):
        return {
            k: "[REDACTED]"
            if k.lower() in {"authorization", "api_key", "openrouter_api_key"}
            else scrub(v)
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [scrub(v) for v in value]
    return value


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(scrub(data), indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    fd, temp = tempfile.mkstemp(prefix=".writing-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as f:
            f.write(encoded)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def read_json(path):
    return json.loads(Path(path).read_text())


def code_hash():
    root = Path(__file__).parent
    digest = hashlib.sha256()
    for path in sorted([*root.glob("*.py"), *root.glob("prompts/*.txt")]):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def provenance():
    return {
        "version": __version__,
        "code_sha256": code_hash(),
        "prompt_sha256": protocol_hash(),
        "python": platform.python_version(),
        "dependencies": {p: version(p) for p in ("httpx", "jsonschema", "tiktoken", "python-dotenv")},
    }


@contextmanager
def exclusive_run(path):
    """Prevent two processes from issuing requests for the same episode."""
    with (Path(path) / ".lock").open("a") as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("Another process is already using this output directory") from None
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)
