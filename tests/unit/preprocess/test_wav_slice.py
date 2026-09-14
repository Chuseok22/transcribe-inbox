import wave
from pathlib import Path
from transcribe_inbox.preprocess.wav_slice import extract_wav_span, PAD_SECONDS


def _write_wav(path: Path, duration_seconds: float, framerate: int = 16000) -> None:
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(framerate)
        f.writeframes(b"\x00\x00" * int(framerate * duration_seconds))


def test_extracts_span_with_padding_on_both_sides(tmp_path):
    source = tmp_path / "source.wav"
    _write_wav(source, duration_seconds=20.0)
    dest = tmp_path / "span.wav"

    absolute_start = extract_wav_span(source, start_seconds=5.0, end_seconds=8.0, dest_path=dest)

    assert absolute_start == 5.0 - PAD_SECONDS
    with wave.open(str(dest), "rb") as f:
        extracted_seconds = f.getnframes() / float(f.getframerate())
        assert extracted_seconds == (8.0 + PAD_SECONDS) - (5.0 - PAD_SECONDS)


def test_clamps_padding_at_start_of_audio(tmp_path):
    source = tmp_path / "source.wav"
    _write_wav(source, duration_seconds=20.0)
    dest = tmp_path / "span.wav"

    absolute_start = extract_wav_span(source, start_seconds=0.2, end_seconds=1.0, dest_path=dest)

    assert absolute_start == 0.0


def test_clamps_padding_at_end_of_audio(tmp_path):
    source = tmp_path / "source.wav"
    _write_wav(source, duration_seconds=10.0)
    dest = tmp_path / "span.wav"

    extract_wav_span(source, start_seconds=9.0, end_seconds=9.9, dest_path=dest)

    with wave.open(str(dest), "rb") as f:
        extracted_seconds = f.getnframes() / float(f.getframerate())
        assert extracted_seconds == 10.0 - (9.0 - PAD_SECONDS)


def test_preserves_source_audio_format(tmp_path):
    source = tmp_path / "source.wav"
    _write_wav(source, duration_seconds=5.0, framerate=16000)
    dest = tmp_path / "span.wav"

    extract_wav_span(source, start_seconds=1.0, end_seconds=2.0, dest_path=dest)

    with wave.open(str(dest), "rb") as f:
        assert f.getnchannels() == 1
        assert f.getsampwidth() == 2
        assert f.getframerate() == 16000


def test_does_not_crash_when_start_seconds_is_beyond_source_duration(tmp_path):
    """A caller-supplied span past the audio's own length (e.g. from a
    VAD-remapped timestamp slightly off) must not crash wave.setpos() with
    'position not in range' -- it should just yield an empty/near-empty clip."""
    source = tmp_path / "source.wav"
    _write_wav(source, duration_seconds=5.0)
    dest = tmp_path / "span.wav"

    absolute_start = extract_wav_span(source, start_seconds=6.0, end_seconds=6.5, dest_path=dest)

    assert absolute_start == 5.0  # clamped to the source's own duration
    with wave.open(str(dest), "rb") as f:
        assert f.getnframes() == 0


def test_inverted_span_yields_an_empty_clip_not_a_silent_overread(tmp_path):
    """end_seconds < start_seconds (a malformed/miscomputed span) must not
    fall through to wave.readframes() with a negative frame count -- the
    wave module silently reinterprets a negative count as "read to end of
    chunk", which would return several unrelated seconds of audio instead
    of failing loudly or yielding nothing."""
    source = tmp_path / "source.wav"
    _write_wav(source, duration_seconds=20.0)
    dest = tmp_path / "span.wav"

    extract_wav_span(source, start_seconds=10.0, end_seconds=2.0, dest_path=dest)

    with wave.open(str(dest), "rb") as f:
        assert f.getnframes() == 0
