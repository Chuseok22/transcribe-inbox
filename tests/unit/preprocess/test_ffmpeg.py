import wave
from pathlib import Path
from transcribe_inbox.preprocess.ffmpeg import normalize_to_wav, wav_duration_seconds, FFMPEG_BINARY

def test_normalize_to_wav_invokes_ffmpeg_without_silenceremove(tmp_path):
    source = tmp_path / "input.m4a"
    source.write_bytes(b"fake-audio-bytes")
    captured_args = {}

    def fake_run(args, **kwargs):
        captured_args["args"] = args
        Path(args[-1]).write_bytes(b"fake-wav-bytes")
        class Result:
            returncode = 0
        return Result()

    output = normalize_to_wav(source, run_fn=fake_run)

    assert output.suffix == ".wav"
    assert output.exists()
    args = captured_args["args"]
    assert args[0] == FFMPEG_BINARY
    assert str(source) in args
    assert "silenceremove" not in " ".join(args)
    assert "-ar" in args and "16000" in args
    assert "-ac" in args and "1" in args

def test_normalize_to_wav_raises_on_ffmpeg_failure(tmp_path):
    source = tmp_path / "input.m4a"
    source.write_bytes(b"x")

    def failing_run(args, **kwargs):
        class Result:
            returncode = 1
        return Result()

    try:
        normalize_to_wav(source, run_fn=failing_run)
        assert False, "expected RuntimeError"
    except RuntimeError:
        pass

def test_normalize_to_wav_cleans_up_temp_wav_when_run_fn_raises(tmp_path):
    source = tmp_path / "input.m4a"
    source.write_bytes(b"x")
    captured_output_path = {}

    def raising_run(args, **kwargs):
        captured_output_path["path"] = Path(args[-1])
        raise FileNotFoundError("ffmpeg binary not found")

    try:
        normalize_to_wav(source, run_fn=raising_run)
        assert False, "expected FileNotFoundError to propagate"
    except FileNotFoundError:
        pass

    assert not captured_output_path["path"].exists()


def test_wav_duration_seconds_reads_real_header_duration(tmp_path):
    wav_path = tmp_path / "a.wav"
    with wave.open(str(wav_path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(16000)
        f.writeframes(b"\x00\x00" * 16000 * 3)  # 3 seconds of silence

    assert wav_duration_seconds(wav_path) == 3.0
