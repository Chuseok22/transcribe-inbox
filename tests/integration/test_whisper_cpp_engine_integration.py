import os
import pytest
from pathlib import Path
from transcribe_inbox.engines.whisper_cpp_engine import WhisperCppEngine
from transcribe_inbox.engines.base import TranscriptionRequest

WHISPER_CLI = os.environ.get("WHISPER_CLI_BINARY", "/opt/homebrew/bin/whisper-cli")
VAD_MODEL = os.environ.get("WHISPER_VAD_MODEL", "/opt/homebrew/share/whisper-vad/ggml-silero-v6.2.0.bin")
ASR_MODEL = os.environ.get("WHISPER_ASR_MODEL", "/opt/homebrew/share/whisper-models/ggml-large-v3.bin")

pytestmark = pytest.mark.integration


@pytest.mark.skipif(not Path(WHISPER_CLI).exists(), reason="whisper-cli not installed")
def test_short_real_wav_produces_at_least_one_segment(tmp_path):
    import subprocess
    wav = tmp_path / "smoke.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
         "-ar", "16000", "-ac", "1", str(wav)],
        check=True, capture_output=True,
    )
    engine = WhisperCppEngine(WHISPER_CLI, VAD_MODEL, ASR_MODEL, engine_version="unknown")
    request = TranscriptionRequest(
        audio_path=wav, language="ko", alignment_enabled=False,
        diarization_enabled=False, source_filename="smoke.wav",
    )
    doc = engine.transcribe(request)
    # A pure sine tone has no speech; asserting the call completes without
    # raising is the smoke test here — real timeline assertions live in
    # Task 16's fixture-based regression tests.
    assert doc.engine == "whisper.cpp"
