from transcribe_inbox.observability.stall import Heartbeat

def test_update_records_progress_and_time():
    clock = iter([100.0, 105.0])
    hb = Heartbeat(last_progress_at=next(clock))
    hb.update(42.0, "ALIGNING", now_fn=lambda: 105.0)
    assert hb.progress_percent == 42.0
    assert hb.current_stage == "ALIGNING"
    assert hb.last_progress_at == 105.0

def test_is_stalled_true_after_warning_window():
    hb = Heartbeat(last_progress_at=0.0)
    assert hb.is_stalled(warning_after_seconds=1800.0, now_fn=lambda: 1801.0) is True

def test_is_stalled_false_before_warning_window():
    hb = Heartbeat(last_progress_at=0.0)
    assert hb.is_stalled(warning_after_seconds=1800.0, now_fn=lambda: 100.0) is False
