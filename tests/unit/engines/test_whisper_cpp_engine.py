import json
import wave
from pathlib import Path
import pytest
from transcribe_inbox.engines.whisper_cpp_engine import WhisperCppEngine
from transcribe_inbox.engines.base import TranscriptionRequest

FAKE_WHISPER_JSON = {
    "result": {"language": "ko"},
    "transcription": [
        {"offsets": {"from": 3000, "to": 8000}, "text": " 첫 번째 문장입니다."},
        {"offsets": {"from": 12000, "to": 17000}, "text": " 두 번째 문장입니다."},
    ],
}


def _write_fake_wav(path: Path, duration_seconds: float) -> None:
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(16000)
        f.writeframes(b"\x00\x00" * int(16000 * duration_seconds))


class FakeProcess:
    def __init__(self, returncode, stderr=b""):
        self.returncode = returncode
        self.pid = 4242
        self._stderr = stderr

    def communicate(self):
        return b"", self._stderr


def test_transcribe_parses_offsets_into_segments(tmp_path, monkeypatch):
    output_written = {}

    def fake_popen(args, stdout, stderr):
        of_index = args.index("-of")
        json_path = Path(args[of_index + 1]).with_suffix(".json")
        json_path.write_text(json.dumps(FAKE_WHISPER_JSON))
        output_written["path"] = json_path
        return FakeProcess(returncode=0)

    monkeypatch.setattr("subprocess.Popen", fake_popen)

    engine = WhisperCppEngine(
        binary_path="/opt/homebrew/bin/whisper-cli",
        vad_model_path="/models/ggml-silero-v6.2.0.bin",
        model_path="/models/ggml-large-v3.bin",
        engine_version="1.0.0",
    )
    audio_path = tmp_path / "normalized.wav"
    # 20s real WAV, vs. last segment ending at 17.0 -- proves duration comes
    # from the file (trailing 3s of trimmed VAD silence), not the transcript.
    _write_fake_wav(audio_path, duration_seconds=20.0)
    request = TranscriptionRequest(
        audio_path=audio_path, language="ko", alignment_enabled=False,
        diarization_enabled=False, source_filename="2주차.m4a",
    )
    doc = engine.transcribe(request)

    assert doc.engine == "whisper.cpp"
    assert doc.language == "ko"
    assert len(doc.segments) == 2
    assert doc.segments[0].start == 3.0
    assert doc.segments[0].end == 8.0
    assert doc.segments[0].text == "첫 번째 문장입니다."
    assert doc.segments[1].start == 12.0
    assert doc.audio_duration_seconds == 20.0


def test_transcribe_tolerates_invalid_utf8_in_whisper_cli_own_json_output(tmp_path, monkeypatch):
    """whisper.cpp occasionally splits a single multi-byte CJK/Hangul
    character's tokens across two output segments, leaving its own -oj JSON
    file with an invalid UTF-8 byte sequence (upstream bug,
    ggml-org/whisper.cpp#1798) -- reproduced here by corrupting one
    continuation byte inside a real 3-byte Hangul character. A strict decode
    would fail the entire transcription over one broken character; the
    engine must decode leniently and keep everything else intact instead."""
    good_json_bytes = json.dumps(FAKE_WHISPER_JSON, ensure_ascii=False).encode("utf-8")
    marker = "첫".encode("utf-8")  # a real 3-byte Hangul character, present in FAKE_WHISPER_JSON's text
    assert len(marker) == 3
    corrupt_char = bytes([marker[0], marker[1], 0x20])  # valid lead byte, invalid final continuation byte
    corrupted_json_bytes = good_json_bytes.replace(marker, corrupt_char, 1)

    def fake_popen(args, stdout, stderr):
        of_index = args.index("-of")
        json_path = Path(args[of_index + 1]).with_suffix(".json")
        json_path.write_bytes(corrupted_json_bytes)
        return FakeProcess(returncode=0)

    monkeypatch.setattr("subprocess.Popen", fake_popen)

    engine = WhisperCppEngine(
        binary_path="/opt/homebrew/bin/whisper-cli",
        vad_model_path="/models/ggml-silero-v6.2.0.bin",
        model_path="/models/ggml-large-v3.bin",
        engine_version="1.0.0",
    )
    audio_path = tmp_path / "normalized.wav"
    _write_fake_wav(audio_path, duration_seconds=20.0)
    request = TranscriptionRequest(
        audio_path=audio_path, language="ko", alignment_enabled=False,
        diarization_enabled=False, source_filename="2주차.m4a",
    )

    doc = engine.transcribe(request)  # must not raise UnicodeDecodeError

    assert len(doc.segments) == 2  # both segments still parsed, not just the undamaged one
    assert "�" in doc.segments[0].text  # the broken character was replaced, not silently dropped
    assert doc.segments[1].text == "두 번째 문장입니다."  # the untouched segment is fully intact


def test_transcribe_raises_on_nonzero_exit(tmp_path, monkeypatch):
    def fake_popen(args, stdout, stderr):
        return FakeProcess(returncode=1, stderr=b"model not found")

    monkeypatch.setattr("subprocess.Popen", fake_popen)
    engine = WhisperCppEngine(
        binary_path="/opt/homebrew/bin/whisper-cli",
        vad_model_path="/models/ggml-silero-v6.2.0.bin",
        model_path="/models/ggml-large-v3.bin",
        engine_version="1.0.0",
    )
    audio_path = tmp_path / "normalized.wav"
    _write_fake_wav(audio_path, duration_seconds=1.0)
    request = TranscriptionRequest(
        audio_path=audio_path, language="ko", alignment_enabled=False,
        diarization_enabled=False, source_filename="x.m4a",
    )
    try:
        engine.transcribe(request)
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "model not found" in str(exc)


def test_monitoring_pid_is_none_when_idle():
    engine = WhisperCppEngine(
        binary_path="/opt/homebrew/bin/whisper-cli",
        vad_model_path="/models/ggml-silero-v6.2.0.bin",
        model_path="/models/ggml-large-v3.bin",
        engine_version="1.0.0",
    )
    assert engine.monitoring_pid() is None


def test_transcribe_disables_context_carryover(tmp_path, monkeypatch):
    captured_args = {}

    def fake_popen(args, stdout, stderr):
        captured_args["args"] = args
        of_index = args.index("-of")
        json_path = Path(args[of_index + 1]).with_suffix(".json")
        json_path.write_text(json.dumps(FAKE_WHISPER_JSON))
        return FakeProcess(returncode=0)

    monkeypatch.setattr("subprocess.Popen", fake_popen)

    engine = WhisperCppEngine(
        binary_path="/opt/homebrew/bin/whisper-cli",
        vad_model_path="/models/ggml-silero-v6.2.0.bin",
        model_path="/models/ggml-large-v3.bin",
        engine_version="1.0.0",
    )
    audio_path = tmp_path / "normalized.wav"
    _write_fake_wav(audio_path, duration_seconds=20.0)
    request = TranscriptionRequest(
        audio_path=audio_path, language="ko", alignment_enabled=False,
        diarization_enabled=False, source_filename="2주차.m4a",
    )
    engine.transcribe(request)

    args = captured_args["args"]
    mc_index = args.index("-mc")
    assert args[mc_index + 1] == "0"


REPEATED_WHISPER_JSON = {
    "result": {"language": "ko"},
    "transcription": [
        {"offsets": {"from": 0, "to": 2000}, "text": " 정상 발화입니다."},
        {"offsets": {"from": 2000, "to": 4000}, "text": " rfc에 디파인이 되어있는"},
        {"offsets": {"from": 4000, "to": 6000}, "text": " rfc에 디파인이 되어있는"},
        {"offsets": {"from": 6000, "to": 8000}, "text": " rfc에 디파인이 되어있는"},
        {"offsets": {"from": 8000, "to": 10000}, "text": " rfc에 디파인이 되어있는"},
    ],
}

CLEAN_RETRY_JSON = {
    "result": {"language": "ko"},
    "transcription": [
        {"offsets": {"from": 0, "to": 3000}, "text": " 실제로는 다른 내용을 말했습니다."},
    ],
}

STILL_REPEATING_RETRY_JSON = {
    "result": {"language": "ko"},
    "transcription": [
        {"offsets": {"from": 0, "to": 1000}, "text": " rfc에 디파인이 되어있는"},
        {"offsets": {"from": 1000, "to": 2000}, "text": " rfc에 디파인이 되어있는"},
        {"offsets": {"from": 2000, "to": 3000}, "text": " rfc에 디파인이 되어있는"},
    ],
}


def _make_engine() -> WhisperCppEngine:
    return WhisperCppEngine(
        binary_path="/opt/homebrew/bin/whisper-cli",
        vad_model_path="/models/ggml-silero-v6.2.0.bin",
        model_path="/models/ggml-large-v3.bin",
        engine_version="1.0.0",
    )


def _fake_popen_returning(json_bodies):
    """Returns (fake_popen, calls) -- fake_popen writes json_bodies[n] to -of
    on its (n+1)-th call, and `calls` records every args list it was called
    with, in order."""
    calls = []

    def fake_popen(args, stdout, stderr):
        calls.append(args)
        of_index = args.index("-of")
        json_path = Path(args[of_index + 1]).with_suffix(".json")
        body = json_bodies[len(calls) - 1]
        json_path.write_text(json.dumps(body))
        return FakeProcess(returncode=0)

    return fake_popen, calls


def _make_request(tmp_path) -> TranscriptionRequest:
    audio_path = tmp_path / "normalized.wav"
    _write_fake_wav(audio_path, duration_seconds=20.0)
    return TranscriptionRequest(
        audio_path=audio_path, language="ko", alignment_enabled=False,
        diarization_enabled=False, source_filename="x.m4a",
    )


def test_no_repetition_leaves_segments_untouched(tmp_path, monkeypatch):
    fake_popen, calls = _fake_popen_returning([FAKE_WHISPER_JSON])
    monkeypatch.setattr("subprocess.Popen", fake_popen)

    doc = _make_engine().transcribe(_make_request(tmp_path))

    assert len(calls) == 1  # no retry call made
    assert len(doc.segments) == 2
    assert doc.segments[0].text == "첫 번째 문장입니다."


def test_repetition_resolved_on_first_retry_attempt(tmp_path, monkeypatch):
    fake_popen, calls = _fake_popen_returning([REPEATED_WHISPER_JSON, CLEAN_RETRY_JSON])
    monkeypatch.setattr("subprocess.Popen", fake_popen)
    monkeypatch.setattr(
        "transcribe_inbox.engines.whisper_cpp_engine.extract_wav_span",
        lambda source_path, start_seconds, end_seconds, dest_path: start_seconds - 0.5,
    )

    doc = _make_engine().transcribe(_make_request(tmp_path))

    assert len(calls) == 2  # initial decode + exactly one retry
    assert len(doc.segments) == 2
    assert doc.segments[0].text == "정상 발화입니다."
    assert doc.segments[1].text == "실제로는 다른 내용을 말했습니다."
    assert doc.segments[1].start == pytest.approx(1.5)
    assert doc.segments[1].end == pytest.approx(4.5)


def test_repetition_falls_back_to_placeholder_after_max_retries(tmp_path, monkeypatch):
    fake_popen, calls = _fake_popen_returning(
        [REPEATED_WHISPER_JSON, STILL_REPEATING_RETRY_JSON, STILL_REPEATING_RETRY_JSON]
    )
    monkeypatch.setattr("subprocess.Popen", fake_popen)
    monkeypatch.setattr(
        "transcribe_inbox.engines.whisper_cpp_engine.extract_wav_span",
        lambda source_path, start_seconds, end_seconds, dest_path: start_seconds,
    )

    doc = _make_engine().transcribe(_make_request(tmp_path))

    assert len(calls) == 3  # initial decode + exactly MAX_REPETITION_RETRIES(2) retries
    assert len(doc.segments) == 2
    assert doc.segments[1].text.startswith("[⚠️ 반복 감지 - 확인 필요]")
    assert "rfc에 디파인이 되어있는" in doc.segments[1].text
    assert doc.segments[1].start == 2.0
    assert doc.segments[1].end == 10.0


def test_empty_retry_result_is_treated_as_a_failed_attempt_not_silent_deletion(tmp_path, monkeypatch):
    empty_json = {"result": {"language": "ko"}, "transcription": []}
    fake_popen, calls = _fake_popen_returning([REPEATED_WHISPER_JSON, empty_json, empty_json])
    monkeypatch.setattr("subprocess.Popen", fake_popen)
    monkeypatch.setattr(
        "transcribe_inbox.engines.whisper_cpp_engine.extract_wav_span",
        lambda source_path, start_seconds, end_seconds, dest_path: start_seconds,
    )

    doc = _make_engine().transcribe(_make_request(tmp_path))

    assert len(calls) == 3
    assert len(doc.segments) == 2
    assert doc.segments[1].text.startswith("[⚠️ 반복 감지 - 확인 필요]")
