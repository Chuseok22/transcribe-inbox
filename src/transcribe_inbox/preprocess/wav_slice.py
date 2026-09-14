from __future__ import annotations
import wave
from pathlib import Path

PAD_SECONDS = 0.5


def extract_wav_span(
    source_path: Path, start_seconds: float, end_seconds: float, dest_path: Path,
) -> float:
    """Extracts [start_seconds - PAD_SECONDS, end_seconds + PAD_SECONDS] (clamped
    to source_path's own duration) into dest_path as a new WAV file with the
    same channel count/sample width/frame rate. Returns the absolute time (in
    source_path's timeline, seconds) that frame 0 of dest_path corresponds to
    -- callers must add this to every timestamp reported for dest_path to
    restore the absolute timeline."""
    with wave.open(str(source_path), "rb") as src:
        framerate = src.getframerate()
        total_seconds = src.getnframes() / float(framerate)

        # Clamped on both ends: a start_seconds past the source's own
        # duration (e.g. from a slightly-off VAD-remapped timestamp) would
        # otherwise make wave.setpos() raise "position not in range" and
        # crash the whole transcription instead of just yielding an empty clip.
        padded_start = min(max(0.0, start_seconds - PAD_SECONDS), total_seconds)
        padded_end = min(total_seconds, end_seconds + PAD_SECONDS)
        # A malformed/inverted span (end before start -- e.g. from a
        # miscomputed caller) must not fall through to readframes() with a
        # negative frame count, which the wave module silently reinterprets
        # as "read to end of chunk" instead of raising or returning empty.
        padded_end = max(padded_start, padded_end)

        start_frame = int(padded_start * framerate)
        end_frame = int(padded_end * framerate)

        src.setpos(start_frame)
        frames = src.readframes(end_frame - start_frame)

        with wave.open(str(dest_path), "wb") as dst:
            dst.setnchannels(src.getnchannels())
            dst.setsampwidth(src.getsampwidth())
            dst.setframerate(framerate)
            dst.writeframes(frames)

    return padded_start
