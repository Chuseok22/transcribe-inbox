from transcribe_inbox.notify import notify, notify_completed, notify_failed

def test_notify_invokes_osascript(monkeypatch):
    captured = {}
    def fake_run(args, **kwargs):
        captured["args"] = args
        return None
    monkeypatch.setattr("subprocess.run", fake_run)

    notify("제목", "본문")

    assert captured["args"][0] == "osascript"
    assert "제목" in captured["args"][2]
    assert "본문" in captured["args"][2]

def test_notify_completed_and_failed_build_readable_messages(monkeypatch):
    captured = []
    monkeypatch.setattr("subprocess.run", lambda args, **kwargs: captured.append(args))

    notify_completed("컴퓨터네트워크", "2주차.m4a")
    notify_failed("컴퓨터네트워크", "2주차.m4a", "ffmpeg exited 1")

    assert "완료" in captured[0][2] or "완료" in captured[0][-1]
    assert "실패" in captured[1][2] or "실패" in captured[1][-1]
