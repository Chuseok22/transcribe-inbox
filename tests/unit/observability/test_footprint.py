import json
from transcribe_inbox.observability.footprint import sample_process_footprint

def test_returns_footprint_bytes_from_json_output(tmp_path, monkeypatch):
    def fake_run(args, **kwargs):
        json_path = args[args.index("-j") + 1]
        with open(json_path, "w") as f:
            json.dump({"processes": [{"footprint": 123456789}]}, f)
        class Result:
            returncode = 0
        return Result()

    result = sample_process_footprint(4242, run_fn=fake_run)
    assert result == 123456789

def test_returns_none_on_any_failure(monkeypatch):
    def failing_run(args, **kwargs):
        raise OSError("footprint not found")

    assert sample_process_footprint(4242, run_fn=failing_run) is None
