from __future__ import annotations
import time
from typing import Callable

import psycopg

BACKOFF_SCHEDULE_SECONDS: list[int] = [1, 2, 5, 10, 30, 30]


def connect_with_backoff(
    dsn: str,
    *,
    connect_fn: Callable[[str], psycopg.Connection] = psycopg.connect,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> psycopg.Connection:
    """Retries forever (holding at the schedule's last interval once
    exhausted) rather than raising — launchd can start this daemon before
    Docker Desktop/PostgreSQL are up (spec §8)."""
    attempt = 0
    while True:
        try:
            return connect_fn(dsn)
        except psycopg.OperationalError:
            delay = BACKOFF_SCHEDULE_SECONDS[min(attempt, len(BACKOFF_SCHEDULE_SECONDS) - 1)]
            sleep_fn(delay)
            attempt += 1
