"""Utility helpers shared across the package."""

from __future__ import annotations

import hashlib
import json
import os
import random
from typing import Any


def derive_seed(base_seed: int, *parts: Any) -> int:
    """Deterministically derive a 64-bit seed from a base seed and parts.

    Uses SHA-256 so the result is stable across processes and Python versions
    (``hash()`` is salted for strings and must not be used for reproducibility).
    """
    payload = "|".join([str(base_seed)] + [str(p) for p in parts])
    digest = hashlib.sha256(payload.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big", signed=False)


def rng_for(base_seed: int, *parts: Any) -> random.Random:
    """Return a ``random.Random`` instance seeded deterministically."""
    return random.Random(derive_seed(base_seed, *parts))


def stable_seed_from_text(text: str) -> int:
    """Return a stable 64-bit seed derived from arbitrary text."""
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big", signed=False)


def stable_hash(obj: Any) -> str:
    """Return a short stable hash for a JSON-serialisable object."""
    payload = json.dumps(obj, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def ensure_dir(path: str) -> str:
    """Create ``path`` (and parents) if needed and return it."""
    os.makedirs(path, exist_ok=True)
    return path


def atomic_write_text(path: str, text: str) -> None:
    """Write text to ``path`` atomically (write temp then rename)."""
    tmp = path + ".tmp"
    ensure_dir(os.path.dirname(os.path.abspath(path)))
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)
