from __future__ import annotations
import time
from pathlib import Path
from typing import Callable

from transcribe_inbox.hashing import is_hidden_file


def wait_for_file_stable(
    path: Path,
    *,
    stable_seconds: float = 5.0,
    poll_interval: float = 1.0,
    now_fn: Callable[[], float] = time.monotonic,
    sleep_fn: Callable[[float], None] = time.sleep,
    size_fn: Callable[[Path], int] | None = None,
) -> bool:
    """Blocks (via injectable clock/sleep) until `path`'s size hasn't changed for
    `stable_seconds`. Returns False if the file disappears mid-wait (spec §8)."""
    size_fn = size_fn or (lambda p: p.stat().st_size)
    last_size: int | None = None
    stable_since = now_fn()
    while True:
        if not path.exists():
            return False
        try:
            size = size_fn(path)
        except FileNotFoundError:
            # The file vanished in the gap between the exists() check above
            # and this stat -- same documented "disappeared mid-wait" case,
            # just a narrower race window.
            return False
        current = now_fn()
        if size != last_size:
            last_size = size
            stable_since = current
        if current - stable_since >= stable_seconds:
            return True
        sleep_fn(poll_interval)


def is_folder_quiescent(
    folder: Path,
    *,
    quiet_seconds: float = 60.0,
    now_fn: Callable[[], float] = time.time,
) -> bool:
    """True if every visible file under `folder` has an mtime at least
    `quiet_seconds` old. An mtime that old already implies the file is
    individually stable too (spec §3 asr-multitrack quiescence), so this
    single check covers both conditions without a nested blocking poll.
    Empty folders are never quiescent (nothing to process yet)."""
    visible_files = [p for p in folder.rglob("*") if p.is_file() and not is_hidden_file(p)]
    if not visible_files:
        return False
    now = now_fn()
    return all((now - f.stat().st_mtime) >= quiet_seconds for f in visible_files)
