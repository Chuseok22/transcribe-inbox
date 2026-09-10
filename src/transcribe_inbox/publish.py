from __future__ import annotations
import json
import shutil
from pathlib import Path

from transcribe_inbox.transcript.formatters import to_markdown, to_plain_text, to_srt
from transcribe_inbox.transcript.schema import TranscriptDocument


def write_transcript_bundle(doc: TranscriptDocument, staging_dir: Path) -> None:
    staging_dir.mkdir(parents=True, exist_ok=True)
    (staging_dir / "transcript.json").write_text(
        json.dumps(doc.to_dict(), ensure_ascii=False, indent=2)
    )
    (staging_dir / "transcript.md").write_text(to_markdown(doc))
    (staging_dir / "transcript.txt").write_text(to_plain_text(doc))
    (staging_dir / "transcript.srt").write_text(to_srt(doc))


def publish_atomically(staging_dir: Path, final_dir: Path) -> None:
    """Moves a fully-written staging_dir into final_dir's place. staging_dir
    must live on the same volume as final_dir (see config.STAGING_ROOT) so
    this rename is atomic (spec §7). A directory-target rename fails with
    ENOTEMPTY if final_dir already exists non-empty, so remove it first."""
    final_dir.parent.mkdir(parents=True, exist_ok=True)
    if final_dir.exists():
        shutil.rmtree(final_dir)
    staging_dir.rename(final_dir)


def archive_source(source_path: Path, archive_root: Path, category: str, mode: str) -> Path:
    """Moves the original source (file for asr/diarize, directory for
    asr-multitrack) into archive_root/category/mode/, mirroring the
    resolved mode to avoid same-name collisions across modes (spec §8, §9-8)."""
    destination_dir = archive_root / category / mode
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / source_path.name

    if destination.exists():
        if destination.is_dir():
            shutil.rmtree(destination)
        else:
            destination.unlink()

    shutil.move(str(source_path), str(destination))
    return destination
