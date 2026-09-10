import time
from transcribe_inbox.observability.job_monitor import JobMonitor, MonitorSample, sample_once
from transcribe_inbox.observability.stall import Heartbeat

def test_sample_once_combines_footprint_and_available_memory():
    sample = sample_once(
        lambda: 4242,
        footprint_fn=lambda pid: 1000 if pid == 4242 else None,
        available_fn=lambda: 2000,
    )
    assert sample == MonitorSample(footprint_bytes=1000, available_memory_bytes=2000)

def test_sample_once_skips_footprint_when_no_pid():
    sample = sample_once(lambda: None, footprint_fn=lambda pid: 999, available_fn=lambda: 2000)
    assert sample.footprint_bytes is None

def test_job_monitor_tracks_start_peak_end_over_its_lifetime():
    values = iter([100, 300, 150])

    def fake_sample():
        return MonitorSample(footprint_bytes=next(values, 150), available_memory_bytes=5000)

    swap_values = iter([1_000_000, 1_050_000])  # sampled once at start(), once at stop()
    heartbeat = Heartbeat(last_progress_at=time.time())
    monitor = JobMonitor(
        lambda: 1, heartbeat, sample_interval_seconds=0.02, sample_fn=fake_sample,
        swap_out_fn=lambda: next(swap_values),
    )

    monitor.start()
    time.sleep(0.08)
    monitor.stop()

    assert monitor.footprint_start_bytes == 100
    assert monitor.footprint_peak_bytes == 300
    assert monitor.swap_out_delta_bytes == 50_000
    assert monitor.minimum_available_memory_bytes == 5000

def test_job_monitor_warns_once_when_heartbeat_goes_stale():
    warnings = []
    heartbeat = Heartbeat(last_progress_at=0.0)  # already "old" relative to real time.time()
    monitor = JobMonitor(
        lambda: 1, heartbeat, sample_interval_seconds=0.02, stall_warning_seconds=0.0,
        on_stall_warning=lambda: warnings.append(1),
        sample_fn=lambda: MonitorSample(footprint_bytes=None, available_memory_bytes=1000),
    )

    monitor.start()
    time.sleep(0.08)
    monitor.stop()

    assert len(warnings) == 1  # warns once, does not re-fire every sample
