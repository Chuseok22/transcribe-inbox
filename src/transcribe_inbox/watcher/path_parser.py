from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path

from transcribe_inbox.config import UNCATEGORIZED_LABEL

VALID_MODES: frozenset[str] = frozenset({"asr", "asr-multitrack", "diarize"})
DEFAULT_MODE = "asr"
SINGLE_FILE_MODES = frozenset({"asr", "diarize"})
MULTITRACK_MODE = "asr-multitrack"


@dataclass(frozen=True)
class ParsedInboxPath:
    category: str
    mode: str
    job_path: Path


def parse_inbox_path(inbox_root: Path, absolute_path: Path) -> ParsedInboxPath | None:
    """Maps a file path under `inbox_root` to (category, mode, job_path).

    Only two shapes are recognized: `<category>[/<mode>]/<file>` for single-file
    modes, and `<category>/asr-multitrack/<session>/<file>` for multitrack — any
    other depth is ambiguous and returns None (caller must skip + log, never guess).
    """
    parts = absolute_path.relative_to(inbox_root).parts

    if len(parts) == 1:
        return ParsedInboxPath(category=UNCATEGORIZED_LABEL, mode=DEFAULT_MODE, job_path=absolute_path)

    if len(parts) == 2:
        category, _filename = parts
        return ParsedInboxPath(category=category, mode=DEFAULT_MODE, job_path=absolute_path)

    if len(parts) == 3:
        category, maybe_mode, _filename = parts
        if maybe_mode in SINGLE_FILE_MODES:
            return ParsedInboxPath(category=category, mode=maybe_mode, job_path=absolute_path)
        return None

    if len(parts) == 4:
        category, maybe_mode, session, _filename = parts
        if maybe_mode == MULTITRACK_MODE:
            job_path = inbox_root / category / maybe_mode / session
            return ParsedInboxPath(category=category, mode=maybe_mode, job_path=job_path)
        return None

    return None
