import psycopg
from transcribe_inbox.db.connection import connect_with_backoff, BACKOFF_SCHEDULE_SECONDS

def test_retries_with_exponential_schedule_then_succeeds():
    attempts = {"n": 0}

    def fake_connect(dsn):
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise psycopg.OperationalError("not ready")
        return "CONNECTION"

    sleeps = []
    result = connect_with_backoff("dsn", connect_fn=fake_connect, sleep_fn=sleeps.append)

    assert result == "CONNECTION"
    assert sleeps == BACKOFF_SCHEDULE_SECONDS[:2]

def test_holds_at_final_backoff_interval_once_schedule_is_exhausted():
    attempts = {"n": 0}

    def fake_connect(dsn):
        attempts["n"] += 1
        if attempts["n"] < len(BACKOFF_SCHEDULE_SECONDS) + 3:
            raise psycopg.OperationalError("still not ready")
        return "CONNECTION"

    sleeps = []
    result = connect_with_backoff("dsn", connect_fn=fake_connect, sleep_fn=sleeps.append)

    assert result == "CONNECTION"
    assert sleeps[-1] == BACKOFF_SCHEDULE_SECONDS[-1]
