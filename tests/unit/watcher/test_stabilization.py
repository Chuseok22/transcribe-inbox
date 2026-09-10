import time
from transcribe_inbox.watcher.stabilization import wait_for_file_stable, is_folder_quiescent

def test_stable_file_returns_true(tmp_path):
    f = tmp_path / "a.m4a"
    f.write_bytes(b"x" * 100)
    clock = iter([0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    result = wait_for_file_stable(
        f, stable_seconds=5.0, poll_interval=1.0,
        now_fn=lambda: next(clock), sleep_fn=lambda _: None,
    )
    assert result is True

def test_missing_file_returns_false(tmp_path):
    missing = tmp_path / "gone.m4a"
    result = wait_for_file_stable(
        missing, stable_seconds=5.0, poll_interval=1.0,
        now_fn=time.monotonic, sleep_fn=lambda _: None,
    )
    assert result is False

def test_growing_then_stable_file_waits_from_last_growth(tmp_path):
    f = tmp_path / "a.m4a"
    f.write_bytes(b"x")  # just needs to exist; size_fn below overrides the size used

    sizes = [10, 10, 20, 20, 20, 20, 20]  # grows once, on the 3rd sample
    call_count = {"n": 0}

    def size_fn(path):
        value = sizes[call_count["n"]]
        call_count["n"] += 1
        return value

    clock = iter([0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0])

    result = wait_for_file_stable(
        f, stable_seconds=3.0, poll_interval=1.0,
        now_fn=lambda: next(clock), sleep_fn=lambda _: None, size_fn=size_fn,
    )

    assert result is True
    # The stability clock must reset on the growth at the 3rd sample (t=3.0)
    # and only return once 3s have elapsed *since then* (t=6.0), i.e. after
    # 6 samples. If the reset were missing, elapsed time since the very
    # first sample (t=0.0) would already hit 3s by the 3rd sample, returning
    # early -- exactly the bug this test exists to catch.
    assert call_count["n"] == 6, f"expected exactly 6 size samples, got {call_count['n']}"

def test_folder_quiescent_false_when_recent_mtime(tmp_path):
    folder = tmp_path / "session"
    folder.mkdir()
    (folder / "a.m4a").write_bytes(b"x")
    assert is_folder_quiescent(folder, quiet_seconds=60.0, now_fn=time.time) is False

def test_folder_quiescent_true_when_old_enough(tmp_path):
    folder = tmp_path / "session"
    folder.mkdir()
    f = folder / "a.m4a"
    f.write_bytes(b"x")
    far_future = lambda: f.stat().st_mtime + 61.0
    assert is_folder_quiescent(folder, quiet_seconds=60.0, now_fn=far_future) is True

def test_folder_quiescent_ignores_dotfiles(tmp_path):
    folder = tmp_path / "session"
    folder.mkdir()
    f = folder / "a.m4a"
    f.write_bytes(b"x")
    (folder / ".DS_Store").write_bytes(b"junk")
    far_future = lambda: f.stat().st_mtime + 61.0
    assert is_folder_quiescent(folder, quiet_seconds=60.0, now_fn=far_future) is True

def test_folder_quiescent_false_when_empty(tmp_path):
    folder = tmp_path / "session"
    folder.mkdir()
    assert is_folder_quiescent(folder, quiet_seconds=60.0, now_fn=time.time) is False
