from __future__ import annotations
import threading
from dataclasses import dataclass
from typing import Callable

from transcribe_inbox.observability.footprint import sample_process_footprint
from transcribe_inbox.observability.stall import Heartbeat
from transcribe_inbox.observability.system_metrics import available_memory_bytes, swap_out_bytes


@dataclass(frozen=True)
class MonitorSample:
    footprint_bytes: int | None
    available_memory_bytes: int


def sample_once(
    pid_provider: Callable[[], int | None],
    *,
    footprint_fn: Callable[[int], int | None] = sample_process_footprint,
    available_fn: Callable[[], int] = available_memory_bytes,
) -> MonitorSample:
    pid = pid_provider()
    footprint = footprint_fn(pid) if pid else None
    return MonitorSample(footprint_bytes=footprint, available_memory_bytes=available_fn())


class JobMonitor:
    """Samples footprint/available-memory on a background thread for the
    duration of a (blocking) `engine.transcribe()` call, and fires a
    one-time stall warning if the heartbeat goes stale (spec §9-5, §9-7 —
    observation and warning only, never a kill switch). A single post-hoc
    sample after `transcribe()` returns cannot see a peak during a
    60-90 minute call, so this must run concurrently, not after the fact."""

    def __init__(
        self,
        pid_provider: Callable[[], int | None],
        heartbeat: Heartbeat,
        *,
        sample_interval_seconds: float = 30.0,
        stall_warning_seconds: float = 1800.0,
        on_stall_warning: Callable[[], None] | None = None,
        sample_fn: Callable[[], MonitorSample] | None = None,
        swap_out_fn: Callable[[], int] = swap_out_bytes,
    ):
        self._heartbeat = heartbeat
        self._sample_interval = sample_interval_seconds
        self._stall_warning_seconds = stall_warning_seconds
        self._on_stall_warning = on_stall_warning
        self._sample_fn = sample_fn or (lambda: sample_once(pid_provider))
        self._swap_out_fn = swap_out_fn
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

        self.footprint_start_bytes: int | None = None
        self.footprint_peak_bytes: int | None = None
        self.footprint_end_bytes: int | None = None
        self.minimum_available_memory_bytes: int | None = None
        self.swap_out_delta_bytes: int | None = None
        self._swap_out_start_bytes: int | None = None

    def start(self) -> None:
        try:
            self._swap_out_start_bytes = self._swap_out_fn()
        except Exception:
            self._swap_out_start_bytes = None
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=self._sample_interval + 5.0)
        if self._swap_out_start_bytes is not None:
            try:
                self.swap_out_delta_bytes = self._swap_out_fn() - self._swap_out_start_bytes
            except Exception:
                self.swap_out_delta_bytes = None

    def _run(self) -> None:
        warned = False
        while True:
            self._record(self._sample_fn())
            if not warned and self._heartbeat.is_stalled(warning_after_seconds=self._stall_warning_seconds):
                warned = True
                if self._on_stall_warning:
                    self._on_stall_warning()
            if self._stop_event.wait(self._sample_interval):
                self._record(self._sample_fn())  # one final sample before exiting
                return

    def _record(self, sample: MonitorSample) -> None:
        if sample.footprint_bytes is not None:
            if self.footprint_start_bytes is None:
                self.footprint_start_bytes = sample.footprint_bytes
            self.footprint_peak_bytes = max(sample.footprint_bytes, self.footprint_peak_bytes or 0)
            self.footprint_end_bytes = sample.footprint_bytes
        if self.minimum_available_memory_bytes is None or sample.available_memory_bytes < self.minimum_available_memory_bytes:
            self.minimum_available_memory_bytes = sample.available_memory_bytes
