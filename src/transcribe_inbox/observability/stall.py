from __future__ import annotations
import time
from dataclasses import dataclass
from typing import Callable


@dataclass
class Heartbeat:
    last_progress_at: float
    progress_percent: float = 0.0
    current_stage: str = "STARTING"

    def update(self, percent: float, stage: str, *, now_fn: Callable[[], float] = time.time) -> None:
        self.progress_percent = percent
        self.current_stage = stage
        self.last_progress_at = now_fn()

    def is_stalled(self, *, warning_after_seconds: float = 1800.0, now_fn: Callable[[], float] = time.time) -> bool:
        """Elapsed-time warning threshold, not a kill switch (spec §9-7)."""
        return (now_fn() - self.last_progress_at) >= warning_after_seconds
