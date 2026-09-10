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
