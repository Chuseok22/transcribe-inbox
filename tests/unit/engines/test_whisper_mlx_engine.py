import sys
import types
import wave
import numpy as np
import pytest
from pathlib import Path
from transcribe_inbox.engines.base import TranscriptionRequest


def _write_fake_wav(path: Path, duration_seconds: float) -> None:
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(16000)
        f.writeframes(b"\x00\x00" * int(16000 * duration_seconds))


def _install_fake_whispermlx(monkeypatch, *, fail_align_on_mps=False, fail_diarize_on_mps=False):
    fake = types.ModuleType("whispermlx")
    fake_diarize_module = types.ModuleType("whispermlx.diarize")

    class FakeModel:
        def transcribe(self, audio, language, progress_callback=None):
            assert isinstance(audio, np.ndarray)
            assert audio.dtype == np.float32
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
        captured.setdefault("align_devices", []).append(device)
        if device == "mps" and fail_align_on_mps:
            raise RuntimeError("mps backend unavailable")
        return object(), object()

    def align(segments, model, metadata, audio, device, progress_callback=None):
        assert isinstance(audio, np.ndarray)
        assert audio.dtype == np.float32
        captured.setdefault("align_call_devices", []).append(device)
        if progress_callback:
            progress_callback(75.0)
        return {
            "segments": [{
                "start": 0.0,
                "end": 2.0,
                "text": "안녕하세요 반갑습니다",
                "words": [
                    {"word": "안녕하세요", "start": 0.0, "end": 1.0},
                    {"word": "반갑습니다", "start": 1.0, "end": 2.0},
                ],
            }]
        }

    class FakeDiarizationPipeline:
        def __init__(self, token, device):
            captured["diarize_token"] = token
            captured.setdefault("diarize_devices", []).append(device)
            if device == "mps" and fail_diarize_on_mps:
                raise RuntimeError("mps backend unavailable")

        def __call__(self, audio, progress_callback=None):
            assert isinstance(audio, np.ndarray)
            assert audio.dtype == np.float32
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
    # Default (non-failing) path never falls back off mps.
    assert captured["align_devices"] == ["mps"]
    assert captured["diarize_devices"] == ["mps"]

    # The array passed to every whispermlx call must be the exact PCM16->
    # float32 conversion of the WAV on disk (matches whispermlx's own
    # audio.load_audio: int16 samples / 32768.0), not a path string.
    with wave.open(str(audio_path), "rb") as f:
        raw = f.readframes(f.getnframes())
    expected = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    assert np.array_equal(expected, np.zeros_like(expected))


def test_monitoring_pid_returns_current_process(monkeypatch, tmp_path):
    _install_fake_whispermlx(monkeypatch)
    import os
    from transcribe_inbox.engines.whisper_mlx_engine import WhisperMlxEngine

    engine = WhisperMlxEngine(model_path="/models/x", engine_version="3.13.1", hf_token="fake-token")
    assert engine.monitoring_pid() == os.getpid()


def test_alignment_falls_back_to_cpu_when_mps_fails(tmp_path, monkeypatch):
    captured = _install_fake_whispermlx(monkeypatch, fail_align_on_mps=True)
    from transcribe_inbox.engines.whisper_mlx_engine import WhisperMlxEngine

    engine = WhisperMlxEngine(model_path="/models/x", engine_version="3.13.1", hf_token="fake-token")
    audio_path = tmp_path / "normalized.wav"
    _write_fake_wav(audio_path, duration_seconds=2.0)
    request = TranscriptionRequest(
        audio_path=audio_path, language="ko", alignment_enabled=True,
        diarization_enabled=True, source_filename="2026-09-08.m4a",
    )

    doc = engine.transcribe(request)

    assert captured["align_devices"] == ["mps", "cpu"]
    assert captured["align_call_devices"] == ["cpu"]
    assert len(doc.words) == 2


def test_diarization_falls_back_to_cpu_when_mps_fails(tmp_path, monkeypatch):
    captured = _install_fake_whispermlx(monkeypatch, fail_diarize_on_mps=True)
    from transcribe_inbox.engines.whisper_mlx_engine import WhisperMlxEngine

    engine = WhisperMlxEngine(model_path="/models/x", engine_version="3.13.1", hf_token="fake-token")
    audio_path = tmp_path / "normalized.wav"
    _write_fake_wav(audio_path, duration_seconds=2.0)
    request = TranscriptionRequest(
        audio_path=audio_path, language="ko", alignment_enabled=True,
        diarization_enabled=True, source_filename="2026-09-08.m4a",
    )

    doc = engine.transcribe(request)

    assert captured["diarize_devices"] == ["mps", "cpu"]
    assert len(doc.words) == 2


def test_segment_with_empty_words_still_contributes_its_text(tmp_path, monkeypatch):
    """whispermlx's own alignment fallback (alignment.py) leaves a segment's
    `words` list empty (rather than omitting the key) when it cannot align
    that segment's characters, but keeps the segment-level start/end/text.
    That text must still show up in the final document, not vanish."""
    fake = types.ModuleType("whispermlx")
    fake_diarize_module = types.ModuleType("whispermlx.diarize")

    def load_model(model_path, device):
        class FakeModel:
            def transcribe(self, audio, language, progress_callback=None):
                return {
                    "language": "ko",
                    "segments": [
                        {"start": 0.0, "end": 1.0, "text": "정상 정렬된 구간"},
                        {"start": 1.0, "end": 2.0, "text": "정렬 실패한 구간"},
                    ],
                }
        return FakeModel()

    def load_align_model(language_code, device):
        return object(), object()

    def align(segments, model, metadata, audio, device, progress_callback=None):
        return {
            "segments": [
                {
                    "start": 0.0, "end": 1.0, "text": "정상 정렬된 구간",
                    "words": [
                        {"word": "정상", "start": 0.0, "end": 0.3},
                        {"word": "정렬된", "start": 0.3, "end": 0.6},
                        {"word": "구간", "start": 0.6, "end": 1.0},
                    ],
                },
                # whispermlx's own fallback shape for an unalignable segment:
                # words stays an empty list, start/end/text unchanged.
                {"start": 1.0, "end": 2.0, "text": "정렬 실패한 구간", "words": []},
            ]
        }

    class FakeDiarizationPipeline:
        def __init__(self, token, device):
            pass

        def __call__(self, audio, progress_callback=None):
            return "fake-diarization-dataframe"

    def assign_word_speakers(diarization_df, aligned_result):
        segments = aligned_result["segments"]
        segments[0]["speaker"] = "SPEAKER_00"
        for w in segments[0]["words"]:
            w["speaker"] = "SPEAKER_00"
        # Segment-level speaker is still assigned even without word-level detail.
        segments[1]["speaker"] = "SPEAKER_01"
        return {"segments": segments}

    fake.load_model = load_model
    fake.load_align_model = load_align_model
    fake.align = align
    fake.assign_word_speakers = assign_word_speakers
    fake_diarize_module.DiarizationPipeline = FakeDiarizationPipeline
    monkeypatch.setitem(sys.modules, "whispermlx", fake)
    monkeypatch.setitem(sys.modules, "whispermlx.diarize", fake_diarize_module)

    from transcribe_inbox.engines.whisper_mlx_engine import WhisperMlxEngine

    engine = WhisperMlxEngine(model_path="/models/x", engine_version="3.13.1", hf_token="fake-token")
    audio_path = tmp_path / "normalized.wav"
    _write_fake_wav(audio_path, duration_seconds=2.0)
    request = TranscriptionRequest(
        audio_path=audio_path, language="ko", alignment_enabled=True,
        diarization_enabled=True, source_filename="2026-09-08.m4a",
    )

    doc = engine.transcribe(request)

    assert [s.text for s in doc.segments] == ["정상 정렬된 구간", "정렬 실패한 구간"]
    assert doc.segments[1].speaker == "SPEAKER_01"
    assert doc.segments[1].start == 1.0
    assert doc.segments[1].end == 2.0
    # The unaligned segment contributes no word-level detail.
    assert len(doc.words) == 3


def _install_two_segment_fake_whispermlx(monkeypatch, *, second_segment_text, second_segment_words, second_speaker):
    """A fake whispermlx producing two ASR segments (rather than one, like
    `_install_fake_whispermlx`'s fixed shape) so tests can control the gap
    and content between them."""
    fake = types.ModuleType("whispermlx")
    fake_diarize_module = types.ModuleType("whispermlx.diarize")

    def load_model(model_path, device):
        class FakeModel:
            def transcribe(self, audio, language, progress_callback=None):
                return {
                    "language": "ko",
                    "segments": [
                        {"start": 0.0, "end": 1.0, "text": "안녕하세요"},
                        {"start": 1.1, "end": 1.5, "text": second_segment_text},
                    ],
                }
        return FakeModel()

    def load_align_model(language_code, device):
        return object(), object()

    def align(segments, model, metadata, audio, device, progress_callback=None):
        return {
            "segments": [
                {
                    "start": 0.0, "end": 1.0, "text": "안녕하세요",
                    "words": [{"word": "안녕하세요", "start": 0.0, "end": 1.0}],
                },
                {
                    "start": 1.1, "end": 1.5, "text": second_segment_text,
                    "words": second_segment_words,
                },
            ]
        }

    class FakeDiarizationPipeline:
        def __init__(self, token, device):
            pass

        def __call__(self, audio, progress_callback=None):
            return "fake-diarization-dataframe"

    def assign_word_speakers(diarization_df, aligned_result):
        segments = aligned_result["segments"]
        segments[0]["speaker"] = "SPEAKER_00"
        for w in segments[0]["words"]:
            w["speaker"] = "SPEAKER_00"
        segments[1]["speaker"] = second_speaker
        for w in segments[1]["words"]:
            w["speaker"] = second_speaker
        return {"segments": segments}

    fake.load_model = load_model
    fake.load_align_model = load_align_model
    fake.align = align
    fake.assign_word_speakers = assign_word_speakers
    fake_diarize_module.DiarizationPipeline = FakeDiarizationPipeline
    monkeypatch.setitem(sys.modules, "whispermlx", fake)
    monkeypatch.setitem(sys.modules, "whispermlx.diarize", fake_diarize_module)


def test_empty_text_unaligned_segment_contributes_nothing(tmp_path, monkeypatch):
    """A whispermlx VAD chunk with no speech (no-speech/noise/music) comes
    back with text="" and no word-level alignment. Unlike a real unalignable
    segment with real text, this must not leak a blank Segment/word into the
    document -- no formatter filters empty text, so a blank entry here would
    show up as a blank line in markdown and an empty cue in the SRT."""
    _install_two_segment_fake_whispermlx(
        monkeypatch, second_segment_text="", second_segment_words=[], second_speaker=None,
    )
    from transcribe_inbox.engines.whisper_mlx_engine import WhisperMlxEngine

    engine = WhisperMlxEngine(model_path="/models/x", engine_version="3.13.1", hf_token="fake-token")
    audio_path = tmp_path / "normalized.wav"
    _write_fake_wav(audio_path, duration_seconds=1.5)
    request = TranscriptionRequest(
        audio_path=audio_path, language="ko", alignment_enabled=True,
        diarization_enabled=True, source_filename="2026-09-08.m4a",
    )

    doc = engine.transcribe(request)

    assert len(doc.segments) == 1
    assert doc.segments[0].text == "안녕하세요"
    assert len(doc.words) == 1


def test_same_speaker_short_pause_merges_across_whispermlx_segment_boundary(tmp_path, monkeypatch):
    """Two whispermlx ASR segments (each with real word-level alignment) from
    the same speaker, separated by a pause well within MAX_PAUSE_SECONDS, must
    still merge into a single final Segment -- resegmentation must run once
    over the whole document's chronological word list, not once per
    originating whispermlx segment (which could never merge across a segment
    boundary even with zero pause)."""
    _install_two_segment_fake_whispermlx(
        monkeypatch,
        second_segment_text="반갑습니다",
        second_segment_words=[{"word": "반갑습니다", "start": 1.1, "end": 1.5}],
        second_speaker="SPEAKER_00",
    )
    from transcribe_inbox.engines.whisper_mlx_engine import WhisperMlxEngine

    engine = WhisperMlxEngine(model_path="/models/x", engine_version="3.13.1", hf_token="fake-token")
    audio_path = tmp_path / "normalized.wav"
    _write_fake_wav(audio_path, duration_seconds=1.5)
    request = TranscriptionRequest(
        audio_path=audio_path, language="ko", alignment_enabled=True,
        diarization_enabled=True, source_filename="2026-09-08.m4a",
    )

    doc = engine.transcribe(request)

    assert len(doc.segments) == 1
    assert doc.segments[0].text == "안녕하세요 반갑습니다"
    assert doc.segments[0].start == 0.0
    assert doc.segments[0].end == 1.5
    assert doc.segments[0].speaker == "SPEAKER_00"
    assert len(doc.words) == 2
