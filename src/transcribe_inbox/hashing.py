from __future__ import annotations
import hashlib
from pathlib import Path

_CHUNK_SIZE = 1024 * 1024


def is_hidden_file(path: Path) -> bool:
    return path.name.startswith(".")


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hash_session(session_dir: Path) -> str:
    """SHA256 over sorted (relative_path, file_hash) pairs, dotfiles excluded
    (spec §8 source_hash definition for asr-multitrack)."""
    files = [p for p in session_dir.rglob("*") if p.is_file() and not is_hidden_file(p)]
    files.sort(key=lambda p: p.relative_to(session_dir).as_posix())

    digest = hashlib.sha256()
    for file_path in files:
        rel = file_path.relative_to(session_dir).as_posix()
        digest.update(f"{rel}\0{hash_file(file_path)}\n".encode("utf-8"))
    return digest.hexdigest()
