"""Spec §9-6: both engines must preserve the original absolute timeline.
Assertions check timing windows only, never transcribed text, so they don't
break on minor decoder/model changes."""
import json
import os
import pytest
from pathlib import Path

from transcribe_inbox.engines.base import TranscriptionRequest
from transcribe_inbox.engines.whisper_cpp_engine import WhisperCppEngine
from transcribe_inbox.engines.whisper_mlx_engine import WhisperMlxEngine

pytestmark = pytest.mark.integration

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
WHISPER_CLI = os.environ.get("WHISPER_CLI_BINARY", "/opt/homebrew/bin/whisper-cli")
VAD_MODEL = os.environ.get("WHISPER_VAD_MODEL_PATH", "/opt/homebrew/share/whisper-vad/ggml-silero-v6.2.0.bin")
ASR_MODEL = os.environ.get("WHISPER_ASR_MODEL_PATH", "/opt/homebrew/share/whisper-models/ggml-large-v3.bin")
WHISPER_MLX_MODEL = os.environ.get("WHISPER_MLX_MODEL_PATH", "/opt/homebrew/share/whisper-mlx/whisper-large-v3-mlx")
HUGGINGFACE_TOKEN = os.environ.get("HUGGINGFACE_TOKEN", "")

TOLERANCE_SECONDS = 1.5


def _expected_second_segment_start(fixture_name: str) -> float:
    metadata = json.loads((FIXTURES_DIR / f"{fixture_name}.meta.json").read_text())
    return metadata["expected_second_segment_start_seconds"]


def _skip_unless_ready(*, fixture_name: str, binary: str | None = None):
    if binary is not None and not Path(binary).exists():
        pytest.skip(f"{binary} not installed")
    if not (FIXTURES_DIR / f"{fixture_name}.wav").exists():
        pytest.skip("fixtures not generated — run tests/fixtures/generate_fixtures.py")


def test_whisper_cpp_preserves_timeline_on_normal_fixture():
    _skip_unless_ready(fixture_name="timeline_normal", binary=WHISPER_CLI)
    engine = WhisperCppEngine(WHISPER_CLI, VAD_MODEL, ASR_MODEL, engine_version="unknown")
    request = TranscriptionRequest(
        audio_path=FIXTURES_DIR / "timeline_normal.wav", language="ko",
        alignment_enabled=False, diarization_enabled=False, source_filename="timeline_normal.wav",
    )
    doc = engine.transcribe(request)

    assert len(doc.segments) >= 2
    expected = _expected_second_segment_start("timeline_normal")
    assert abs(doc.segments[1].start - expected) <= TOLERANCE_SECONDS


def test_whisper_cpp_does_not_pull_timestamp_forward_across_long_silence():
    _skip_unless_ready(fixture_name="timeline_long_silence", binary=WHISPER_CLI)
    engine = WhisperCppEngine(WHISPER_CLI, VAD_MODEL, ASR_MODEL, engine_version="unknown")
    request = TranscriptionRequest(
        audio_path=FIXTURES_DIR / "timeline_long_silence.wav", language="ko",
        alignment_enabled=False, diarization_enabled=False, source_filename="timeline_long_silence.wav",
    )
    doc = engine.transcribe(request)

    assert len(doc.segments) >= 2
    # Speech B must start near speech_a_duration + 35s, never pulled back
    # near speech A's own end (that would mean the VAD gap was lost).
    expected = _expected_second_segment_start("timeline_long_silence")
    assert doc.segments[-1].start >= expected - TOLERANCE_SECONDS


@pytest.mark.skipif(not HUGGINGFACE_TOKEN, reason="HUGGINGFACE_TOKEN not set")
def test_whispermlx_preserves_timeline_on_normal_fixture():
    """Spec §9-6 requires both engines, not just whisper.cpp."""
    _skip_unless_ready(fixture_name="timeline_normal")
    engine = WhisperMlxEngine(WHISPER_MLX_MODEL, engine_version="unknown", hf_token=HUGGINGFACE_TOKEN)
    request = TranscriptionRequest(
        audio_path=FIXTURES_DIR / "timeline_normal.wav", language="ko",
        alignment_enabled=True, diarization_enabled=True, source_filename="timeline_normal.wav",
    )
    doc = engine.transcribe(request)

    expected = _expected_second_segment_start("timeline_normal")
    # whispermlx's segments come from speaker-aware re-segmentation (Task 5),
    # not whisper.cpp's own VAD chunking, so don't assume segments[1] is
    # "speech B" -- just require some segment to start near the expected time.
    matching = [s for s in doc.segments if abs(s.start - expected) <= TOLERANCE_SECONDS]
    assert matching, f"no segment starts near expected {expected}s; got starts={[s.start for s in doc.segments]}"
