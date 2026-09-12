from __future__ import annotations
import os
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Callable

FFMPEG_BINARY = os.environ.get("FFMPEG_BINARY", "/opt/homebrew/bin/ffmpeg")


def normalize_to_wav(
    source_path: Path,
    *,
    run_fn: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> Path:
    """Decodes and resamples to 16kHz mono WAV — format/rate normalization
    only, never trims silence, so the timeline stays absolute (spec §4)."""
    fd, output_name = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    output_path = Path(output_name)

    args = [
        FFMPEG_BINARY, "-y",
        "-i", str(source_path),
        "-ar", "16000",
        "-ac", "1",
        str(output_path),
    ]
    succeeded = False
    try:
        result = run_fn(args, capture_output=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg failed for {source_path} (exit {result.returncode})")
        succeeded = True
        return output_path
    finally:
        # run_fn itself can raise (FileNotFoundError if ffmpeg's binary is
        # missing, OSError for other exec failures) before returncode is
        # ever checked -- without this finally, the pre-created temp WAV
        # would leak on that path.
        if not succeeded:
            output_path.unlink(missing_ok=True)


def wav_duration_seconds(wav_path: Path) -> float:
    """Reads the true audio duration from a WAV header — used instead of
    the last transcript segment's end time, which VAD trims short whenever
    trailing silence exists (spec §9-5 RTF must reflect real audio length)."""
    with wave.open(str(wav_path), "rb") as f:
        return f.getnframes() / float(f.getframerate())
