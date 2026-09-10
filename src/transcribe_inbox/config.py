from __future__ import annotations
import os
from pathlib import Path

INBOX_ROOT = Path(os.environ.get("TRANSCRIBE_INBOX_ROOT", str(Path.home() / "Transcribe" / "inbox")))
ARCHIVE_ROOT = Path(os.environ.get("TRANSCRIBE_ARCHIVE_ROOT", str(Path.home() / "Transcribe" / "archive")))
OBSIDIAN_TRANSCRIPTS_ROOT = Path(
    os.environ.get(
        "OBSIDIAN_TRANSCRIPTS_ROOT",
        str(Path.home() / "Obsidian" / "second-brain" / "Transcripts"),
    )
)
# Staging must live under the same tree as the publish destination so the
# final `os.rename` in publish.py stays on one filesystem volume (spec §7).
STAGING_ROOT = OBSIDIAN_TRANSCRIPTS_ROOT / ".staging"

FILE_STABILIZATION_SECONDS = 5.0
FOLDER_QUIESCENCE_SECONDS = 60.0
STALL_WARNING_SECONDS = 1800.0
UNCATEGORIZED_LABEL = "미분류"


def output_dir_for(category: str, label: str) -> Path:
    return OBSIDIAN_TRANSCRIPTS_ROOT / category / label
