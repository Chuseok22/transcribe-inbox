"""Generates synthetic WAV fixtures for timeline regression tests (spec §9-6).
Uses macOS `say` (Korean voice) for real, VAD-detectable speech and ffmpeg to
splice with true silence. Run once (or whenever fixtures need regenerating):
    uv run python tests/fixtures/generate_fixtures.py
"""
from __future__ import annotations
import json
import subprocess
import tempfile
import wave
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent
KOREAN_VOICE = "Yuna"  # `say -v '?'` lists installed voices; Yuna ships with macOS Korean support


def _synthesize_speech(text: str, output_path: Path) -> None:
    # LEI16 (16-bit PCM), not LEF32 -- `say` happily writes IEEE-float WAVs,
    # but Python's stdlib `wave` module (used below and in Task 7) cannot
    # read format tag 3 and raises `wave.Error: unknown format: 3`. This
    # also keeps every fixture part in the same PCM format the ffmpeg
    # concat demuxer expects, matching `anullsrc`'s s16 output.
    subprocess.run(
        ["say", "-v", KOREAN_VOICE, "-o", str(output_path), "--data-format=LEI16@16000", text], check=True,
    )


def _silence(duration_seconds: float, output_path: Path) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=16000:cl=mono",
         "-t", str(duration_seconds), str(output_path)],
        check=True, capture_output=True,
    )


def _duration_seconds(wav_path: Path) -> float:
    with wave.open(str(wav_path), "rb") as f:
        return f.getnframes() / float(f.getframerate())


def _concat(parts: list[Path], output_path: Path) -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as list_file:
        for part in parts:
            list_file.write(f"file '{part}'\n")
        list_file_path = list_file.name
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file_path,
         "-ar", "16000", "-ac", "1", str(output_path)],
        check=True, capture_output=True,
    )


def _write_metadata(fixture_name: str, expected_second_segment_start_seconds: float) -> None:
    metadata = {"expected_second_segment_start_seconds": expected_second_segment_start_seconds}
    (FIXTURES_DIR / f"{fixture_name}.meta.json").write_text(json.dumps(metadata, indent=2))


def generate_normal_fixture() -> None:
    """silence(3s) -> speech A -> silence(4s) -> speech B."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        silence_a, speech_a, silence_b, speech_b = (
            tmp_path / name for name in ("silence_a.wav", "speech_a.wav", "silence_b.wav", "speech_b.wav")
        )
        _silence(3.0, silence_a)
        _synthesize_speech("이것은 첫 번째 문장입니다.", speech_a)
        _silence(4.0, silence_b)
        _synthesize_speech("이것은 두 번째 문장입니다.", speech_b)

        expected_second_start = 3.0 + _duration_seconds(speech_a) + 4.0
        _concat([silence_a, speech_a, silence_b, speech_b], FIXTURES_DIR / "timeline_normal.wav")

    _write_metadata("timeline_normal", expected_second_start)


def generate_long_silence_fixture() -> None:
    """speech A -> silence(35s) -> speech B."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        speech_a, silence, speech_b = (
            tmp_path / name for name in ("speech_a.wav", "silence.wav", "speech_b.wav")
        )
        _synthesize_speech("첫 번째 발화입니다.", speech_a)
        _silence(35.0, silence)
        _synthesize_speech("두 번째 발화입니다.", speech_b)

        expected_second_start = _duration_seconds(speech_a) + 35.0
        _concat([speech_a, silence, speech_b], FIXTURES_DIR / "timeline_long_silence.wav")

    _write_metadata("timeline_long_silence", expected_second_start)


if __name__ == "__main__":
    generate_normal_fixture()
    generate_long_silence_fixture()
    print("Fixtures + metadata written to", FIXTURES_DIR)
