import sys
import types
import wave
from pathlib import Path
from transcribe_inbox.engines.base import TranscriptionRequest


def _write_fake_wav(path: Path, duration_seconds: float) -> None:
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(16000)
        f.writeframes(b"\x00\x00" * int(16000 * duration_seconds))


def _install_fake_whispermlx(monkeypatch):
    fake = types.ModuleType("whispermlx")
    fake_diarize_module = types.ModuleType("whispermlx.diarize")

    class FakeModel:
        def transcribe(self, audio_path, language, progress_callback=None):
            if progress_callback:
                progress_callback(50.0)
            return {
                "language": "ko",
                "segments": [{"start": 0.0, "end": 2.0, "text": "안녕하세요 반갑습니다"}],
            }

    captured = {}

    def load_model(model_path, device):
        captured["load_model_device"] = device
        return FakeModel()

    def load_align_model(language_code, device):
        return object(), object()

    def align(segments, model, metadata, audio_path, device, progress_callback=None):
        if progress_callback:
            progress_callback(75.0)
        return {
            "segments": [{
                "words": [
                    {"word": "안녕하세요", "start": 0.0, "end": 1.0},
                    {"word": "반갑습니다", "start": 1.0, "end": 2.0},
                ]
            }]
        }

    class FakeDiarizationPipeline:
        def __init__(self, token, device):
            captured["diarize_token"] = token
            captured["diarize_device"] = device

        def __call__(self, audio_path, progress_callback=None):
            if progress_callback:
                progress_callback(90.0)
            return "fake-diarization-dataframe"  # whispermlx returns a pandas.DataFrame here, not an object

    def assign_word_speakers(diarization_df, aligned_result):
        assert diarization_df == "fake-diarization-dataframe"
        segments = aligned_result["segments"]
        segments[0]["words"][0]["speaker"] = "SPEAKER_00"
        segments[0]["words"][1]["speaker"] = "SPEAKER_01"
        return {"segments": segments}

    fake.load_model = load_model
    fake.load_align_model = load_align_model
    fake.align = align
    fake.assign_word_speakers = assign_word_speakers
    fake_diarize_module.DiarizationPipeline = FakeDiarizationPipeline
    monkeypatch.setitem(sys.modules, "whispermlx", fake)
    monkeypatch.setitem(sys.modules, "whispermlx.diarize", fake_diarize_module)
    return captured


def test_transcribe_runs_full_pipeline_and_resegments_by_speaker(tmp_path, monkeypatch):
    captured = _install_fake_whispermlx(monkeypatch)
    from transcribe_inbox.engines.whisper_mlx_engine import WhisperMlxEngine

    engine = WhisperMlxEngine(model_path="/models/whisper-large-v3-mlx", engine_version="3.13.1", hf_token="fake-token")
    audio_path = tmp_path / "normalized.wav"
    _write_fake_wav(audio_path, duration_seconds=2.0)
    request = TranscriptionRequest(
        audio_path=audio_path, language="ko", alignment_enabled=True,
        diarization_enabled=True, source_filename="2026-09-08.m4a",
    )

    progress_events = []
    doc = engine.transcribe(request, progress_callback=lambda pct, stage: progress_events.append((pct, stage)))

    assert doc.engine == "whispermlx"
    assert doc.language == "ko"
    assert doc.audio_duration_seconds == 2.0
    assert len(doc.words) == 2
    assert doc.words[0].speaker == "SPEAKER_00"
    assert doc.words[1].speaker == "SPEAKER_01"
    # Speaker change with no pause must split into two segments (Task 5 rule).
    assert len(doc.segments) == 2
    assert [s.speaker for s in doc.segments] == ["SPEAKER_00", "SPEAKER_01"]
    assert [stage for _, stage in progress_events] == ["TRANSCRIBING", "ALIGNING", "DIARIZING"]
    # whispermlx's `load_model(device=...)` configures its internal VAD
    # torch model, not MLX acceleration (ASR always runs on MLX regardless) —
    # "mlx" is not a valid torch device string, so this must be "cpu".
    assert captured["load_model_device"] == "cpu"
    assert captured["diarize_token"] == "fake-token"


def test_monitoring_pid_returns_current_process(monkeypatch, tmp_path):
    _install_fake_whispermlx(monkeypatch)
    import os
    from transcribe_inbox.engines.whisper_mlx_engine import WhisperMlxEngine

    engine = WhisperMlxEngine(model_path="/models/x", engine_version="3.13.1", hf_token="fake-token")
    assert engine.monitoring_pid() == os.getpid()
