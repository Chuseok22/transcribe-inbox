import os
import uuid
import pytest
import psycopg
from pathlib import Path

from transcribe_inbox.db.jobs import (
    NewJob, register_job, claim_next_pending_job, mark_completed, mark_failed,
    reconcile_stale_processing, find_completed_jobs_with_source_still_present,
)
from transcribe_inbox.hashing import hash_file

pytestmark = pytest.mark.integration

DSN = os.environ.get("TEST_DATABASE_URL", "postgresql://localhost/transcribe_inbox_test")


@pytest.fixture
def conn():
    connection = psycopg.connect(DSN, autocommit=False)
    connection.execute("TRUNCATE transcription_job")
    connection.commit()
    yield connection
    connection.close()


def test_register_job_creates_pending_row(conn):
    job_id = register_job(conn, NewJob(
        source_path="/inbox/컴퓨터네트워크/2주차.m4a", source_hash="hash-a",
        category="컴퓨터네트워크", processing_mode="asr",
    ))
    assert job_id is not None
    row = conn.execute("SELECT status FROM transcription_job WHERE id = %s", (job_id,)).fetchone()
    assert row[0] == "PENDING"


def test_register_job_with_same_hash_and_pending_status_is_skipped(conn):
    job = NewJob(source_path="/inbox/x.m4a", source_hash="hash-b", category="미분류", processing_mode="asr")
    first_id = register_job(conn, job)
    second_id = register_job(conn, job)
    assert first_id is not None
    assert second_id is None


def test_register_job_reactivates_a_failed_job(conn):
    job = NewJob(source_path="/inbox/x.m4a", source_hash="hash-c", category="미분류", processing_mode="asr")
    job_id = register_job(conn, job)
    mark_failed(conn, job_id, error_message="boom")

    reactivated_id = register_job(conn, job)

    assert reactivated_id == job_id
    row = conn.execute(
        "SELECT status, retry_count FROM transcription_job WHERE id = %s", (job_id,)
    ).fetchone()
    assert row[0] == "PENDING"
    assert row[1] == 1


def test_register_job_refreshes_path_of_an_unclaimed_pending_job_on_move(conn):
    """A file renamed/moved while its job is still PENDING (unclaimed) must
    have its stored path refreshed to the new location -- otherwise the old
    path lingers forever (worker fails it as missing, the startup scan skips
    the new path since the hash is now FAILED, and `retry` refuses it too)."""
    job_id = register_job(conn, NewJob(
        source_path="/inbox/old/2주차.m4a", source_hash="hash-moved", category="강의", processing_mode="asr",
    ))

    moved_id = register_job(conn, NewJob(
        source_path="/inbox/new/2주차.m4a", source_hash="hash-moved", category="강의", processing_mode="asr",
    ))

    assert moved_id == job_id
    row = conn.execute(
        "SELECT source_path, status, retry_count, error_code FROM transcription_job WHERE id = %s", (job_id,)
    ).fetchone()
    assert row == ("/inbox/new/2주차.m4a", "PENDING", 0, None)


def test_claim_next_pending_job_moves_it_to_processing(conn):
    job_id = register_job(conn, NewJob(
        source_path="/inbox/x.m4a", source_hash="hash-d", category="미분류", processing_mode="asr",
    ))
    claimed = claim_next_pending_job(conn)
    assert claimed.id == job_id
    row = conn.execute("SELECT status FROM transcription_job WHERE id = %s", (job_id,)).fetchone()
    assert row[0] == "PROCESSING"


def test_claim_next_pending_job_returns_none_when_queue_empty(conn):
    assert claim_next_pending_job(conn) is None


def test_reconcile_stale_processing_requeues_when_source_exists(conn, tmp_path):
    source = tmp_path / "x.m4a"
    source.write_bytes(b"x")
    # source_hash must be the *real* content hash -- reconcile_stale_processing
    # now recomputes and compares it (Fix 4) before requeuing.
    job_id = register_job(conn, NewJob(
        source_path=str(source), source_hash=hash_file(source), category="미분류", processing_mode="asr",
    ))
    claim_next_pending_job(conn)  # -> PROCESSING

    reconcile_stale_processing(conn)

    row = conn.execute("SELECT status FROM transcription_job WHERE id = %s", (job_id,)).fetchone()
    assert row[0] == "PENDING"


def test_reconcile_stale_processing_fails_job_when_content_changed(conn, tmp_path):
    """A stale PROCESSING job whose path now holds *different* content than
    when it was registered must not be silently requeued and transcribed
    under the old job's identity (Fix 4)."""
    source = tmp_path / "x.m4a"
    source.write_bytes(b"original content")
    job_id = register_job(conn, NewJob(
        source_path=str(source), source_hash=hash_file(source), category="미분류", processing_mode="asr",
    ))
    claim_next_pending_job(conn)  # -> PROCESSING
    source.write_bytes(b"totally different content")  # simulates a new file landing at the same path

    reconcile_stale_processing(conn)

    row = conn.execute(
        "SELECT status, error_code FROM transcription_job WHERE id = %s", (job_id,)
    ).fetchone()
    assert row == ("FAILED", "SOURCE_CHANGED")


def test_reconcile_stale_processing_fails_job_when_source_missing(conn):
    job_id = register_job(conn, NewJob(
        source_path="/inbox/gone.m4a", source_hash="hash-f", category="미분류", processing_mode="asr",
    ))
    claim_next_pending_job(conn)  # -> PROCESSING

    reconcile_stale_processing(conn)

    row = conn.execute(
        "SELECT status, error_code FROM transcription_job WHERE id = %s", (job_id,)
    ).fetchone()
    assert row == ("FAILED", "SOURCE_MISSING")


def test_reconcile_stale_processing_isolates_hashing_exceptions_per_row(conn, tmp_path, monkeypatch):
    """A hash-verification failure for one stale row (permissions, the file
    vanishing mid-check) must not abort reconciliation of the other stale
    rows, and must not let the exception escape reconcile_stale_processing
    itself -- same pattern as
    test_poll_pending_sessions_isolates_exceptions_per_candidate in
    tests/integration/watcher/test_watch_service.py."""
    failing_source = tmp_path / "failing.m4a"
    failing_source.write_bytes(b"x")
    failing_id = register_job(conn, NewJob(
        source_path=str(failing_source), source_hash=hash_file(failing_source),
        category="미분류", processing_mode="asr",
    ))
    claim_next_pending_job(conn)  # -> PROCESSING

    ok_source = tmp_path / "ok.m4a"
    ok_source.write_bytes(b"y")
    ok_id = register_job(conn, NewJob(
        source_path=str(ok_source), source_hash=hash_file(ok_source),
        category="미분류", processing_mode="asr",
    ))
    claim_next_pending_job(conn)  # -> PROCESSING

    real_hash_file = hash_file

    def flaky_hash_file(path):
        if str(path) == str(failing_source):
            raise OSError("permission denied")
        return real_hash_file(path)

    monkeypatch.setattr("transcribe_inbox.db.jobs.hash_file", flaky_hash_file)

    reconcile_stale_processing(conn)  # must not raise

    failing_row = conn.execute(
        "SELECT status, error_code FROM transcription_job WHERE id = %s", (failing_id,)
    ).fetchone()
    assert failing_row == ("FAILED", "RECONCILIATION_ERROR")

    ok_row = conn.execute("SELECT status FROM transcription_job WHERE id = %s", (ok_id,)).fetchone()
    assert ok_row[0] == "PENDING"


def test_reconcile_stale_processing_survives_an_aborted_transaction(conn, tmp_path, monkeypatch):
    """When the exception that trips a row's recovery handler is itself a DB
    error raised mid-statement (not a pure-Python hashing error), Postgres
    leaves the transaction aborted -- any further statement on it raises
    InFailedSqlTransaction until rolled back. The except handler's own
    recovery UPDATE must roll back first, or it would itself raise and
    escape reconcile_stale_processing (the exact daemon-crash-loop failure
    mode this fix prevents, reached via a DB error instead of a hashing
    error)."""
    source = tmp_path / "x.m4a"
    source.write_bytes(b"x")
    job_id = register_job(conn, NewJob(
        source_path=str(source), source_hash=hash_file(source),
        category="미분류", processing_mode="asr",
    ))
    claim_next_pending_job(conn)  # -> PROCESSING

    real_execute = psycopg.Cursor.execute
    call_count = {"n": 0}

    def flaky_execute(self, query, params=None, **kwargs):
        if isinstance(query, str) and query.strip().startswith("UPDATE transcription_job SET status = 'PENDING'"):
            call_count["n"] += 1
            # A genuine Postgres-level error (not a synthetic Python
            # exception) so the connection's transaction is *actually* left
            # aborted by the server -- reproducing the real failure mode,
            # where any further statement on it raises
            # InFailedSqlTransaction until a ROLLBACK.
            return real_execute(self, "SELECT * FROM this_table_does_not_exist_xyz", None, **kwargs)
        return real_execute(self, query, params, **kwargs)

    monkeypatch.setattr(psycopg.Cursor, "execute", flaky_execute)

    reconcile_stale_processing(conn)  # must not raise

    assert call_count["n"] == 1
    row = conn.execute(
        "SELECT status, error_code FROM transcription_job WHERE id = %s", (job_id,)
    ).fetchone()
    assert row == ("FAILED", "RECONCILIATION_ERROR")


def test_reconcile_stale_processing_rolls_back_when_the_recovery_write_itself_fails(conn, tmp_path, monkeypatch):
    """If the *recovery* UPDATE (the one that records RECONCILIATION_ERROR)
    itself fails with a genuine Postgres error, the transaction is left
    aborted -- without a rollback in that innermost except, every later
    statement on this shared connection (the next row in this same loop, or
    any later caller) would raise InFailedSqlTransaction forever."""
    failing_source = tmp_path / "failing.m4a"
    failing_source.write_bytes(b"x")
    failing_id = register_job(conn, NewJob(
        source_path=str(failing_source), source_hash=hash_file(failing_source),
        category="미분류", processing_mode="asr",
    ))
    claim_next_pending_job(conn)  # -> PROCESSING

    ok_source = tmp_path / "ok.m4a"
    ok_source.write_bytes(b"y")
    ok_id = register_job(conn, NewJob(
        source_path=str(ok_source), source_hash=hash_file(ok_source),
        category="미분류", processing_mode="asr",
    ))
    claim_next_pending_job(conn)  # -> PROCESSING

    real_hash_file = hash_file
    real_execute = psycopg.Cursor.execute

    def flaky_hash_file(path):
        # Trips the outer except for failing_source only, driving execution
        # into the recovery-write branch.
        if str(path) == str(failing_source):
            raise OSError("permission denied")
        return real_hash_file(path)

    def flaky_execute(self, query, params=None, **kwargs):
        # The recovery UPDATE itself (RECONCILIATION_ERROR) fails with a
        # genuine Postgres-level error, leaving the transaction aborted.
        if isinstance(query, str) and "RECONCILIATION_ERROR" in query:
            return real_execute(self, "SELECT * FROM this_table_does_not_exist_xyz", None, **kwargs)
        return real_execute(self, query, params, **kwargs)

    monkeypatch.setattr("transcribe_inbox.db.jobs.hash_file", flaky_hash_file)
    monkeypatch.setattr(psycopg.Cursor, "execute", flaky_execute)

    reconcile_stale_processing(conn)  # must not raise, must not poison the connection for the next row

    monkeypatch.undo()  # restore real hash_file/execute before verifying via the same conn

    failing_row = conn.execute(
        "SELECT status FROM transcription_job WHERE id = %s", (failing_id,)
    ).fetchone()
    # The recovery write itself failed, so this row is left as it was
    # (PROCESSING) rather than silently marked anything -- but the important
    # assertion is that the connection is still usable afterward.
    assert failing_row[0] == "PROCESSING"

    ok_row = conn.execute("SELECT status FROM transcription_job WHERE id = %s", (ok_id,)).fetchone()
    assert ok_row[0] == "PENDING"


def test_find_completed_jobs_with_source_still_present(conn, tmp_path):
    source = tmp_path / "x.m4a"
    source.write_bytes(b"x")
    job_id = register_job(conn, NewJob(
        source_path=str(source), source_hash="hash-g", category="미분류", processing_mode="asr",
    ))
    claim_next_pending_job(conn)
    mark_completed(conn, job_id, engine="whisper.cpp", engine_version="1.0.0", model_name="large-v3", metrics={})

    results = find_completed_jobs_with_source_still_present(conn)

    assert any(job.id == job_id for job in results)
