from __future__ import annotations
import hashlib
import json
import shutil
from pathlib import Path

from transcribe_inbox.hashing import hash_file, hash_session
from transcribe_inbox.transcript.formatters import to_markdown, to_plain_text, to_srt
from transcribe_inbox.transcript.schema import TranscriptDocument


def write_transcript_bundle(doc: TranscriptDocument, staging_dir: Path) -> None:
    staging_dir.mkdir(parents=True, exist_ok=True)
    (staging_dir / "transcript.json").write_text(
        json.dumps(doc.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (staging_dir / "transcript.md").write_text(to_markdown(doc), encoding="utf-8")
    (staging_dir / "transcript.txt").write_text(to_plain_text(doc), encoding="utf-8")
    (staging_dir / "transcript.srt").write_text(to_srt(doc), encoding="utf-8")


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
    resolved mode to avoid same-name collisions across modes (spec §8, §9-8).

    Never deletes or overwrites an existing destination -- this is also used
    to archive the original recording, and overwriting a previously archived
    original would be irreversible data loss. If the destination name is
    already taken, a short content-hash suffix (of the *new* source, taken
    before the move) disambiguates it instead."""
    destination_dir = archive_root / category / mode
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / source_path.name

    if destination.exists():
        content_hash = hash_session(source_path) if source_path.is_dir() else hash_file(source_path)
        suffix = content_hash[:8]
        candidate = _disambiguated_name(destination_dir, source_path, suffix)
        disambiguator = 1
        while candidate.exists():
            candidate = _disambiguated_name(destination_dir, source_path, f"{suffix}-{disambiguator}")
            disambiguator += 1
        destination = candidate

    shutil.move(str(source_path), str(destination))
    return destination


def _disambiguated_name(destination_dir: Path, source_path: Path, disambiguator: str) -> Path:
    if source_path.is_dir():
        return destination_dir / f"{source_path.name}-{disambiguator}"
    return destination_dir / f"{source_path.stem}-{disambiguator}{source_path.suffix}"
