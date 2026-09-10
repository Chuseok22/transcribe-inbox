from __future__ import annotations
import json
import logging
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from transcribe_inbox.hashing import hash_file, hash_session

MULTITRACK_MODE = "asr-multitrack"

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class NewJob:
    source_path: str
    source_hash: str
    category: str
    processing_mode: str
    tracks: list[dict] | None = None


@dataclass(frozen=True)
class Job:
    id: uuid.UUID
    source_path: str
    source_hash: str
    category: str
    processing_mode: str
    tracks: list[dict] | None


def register_job(conn: psycopg.Connection, job: NewJob) -> uuid.UUID | None:
    """Returns the job id for a newly-created or FAILED->PENDING-reactivated
    job; returns None if a PENDING/PROCESSING/COMPLETED job with this hash
    already exists (idempotent skip, spec §8).

    A single atomic `INSERT ... ON CONFLICT ... DO UPDATE ... WHERE` statement
    replaces what used to be a SELECT-then-branch (check-then-act) sequence --
    that pattern was the root cause of several previously-found races between
    concurrent connections/threads registering the same source_hash at once.
    Postgres resolves the INSERT-vs-UPDATE race itself, and having nothing
    else interleaved between this statement's execute and its own commit
    means no other connection's rollback can land inside this transaction."""
    new_id = uuid.uuid4()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO transcription_job (id, source_path, source_hash, category, processing_mode, tracks, status)
            VALUES (%s, %s, %s, %s, %s, %s, 'PENDING')
            ON CONFLICT (source_hash) DO UPDATE
              SET status = 'PENDING', retry_count = transcription_job.retry_count + 1,
                  error_code = NULL, error_message = NULL,
                  source_path = EXCLUDED.source_path, category = EXCLUDED.category,
                  processing_mode = EXCLUDED.processing_mode, tracks = EXCLUDED.tracks
              WHERE transcription_job.status = 'FAILED'
            RETURNING id
            """,
            (
                new_id, job.source_path, job.source_hash, job.category, job.processing_mode,
                Jsonb(job.tracks) if job.tracks is not None else None,
            ),
        )
        row = cur.fetchone()
        conn.commit()
        return row[0] if row else None


def claim_next_pending_job(conn: psycopg.Connection) -> Job | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE transcription_job
            SET status = 'PROCESSING', started_at = now()
            WHERE id = (
                SELECT id FROM transcription_job
                WHERE status = 'PENDING'
                ORDER BY created_at
                LIMIT 1
                FOR UPDATE SKIP LOCKED
            )
            RETURNING id, source_path, source_hash, category, processing_mode, tracks
            """
        )
        row = cur.fetchone()
        conn.commit()
        if row is None:
            return None
        return Job(
            id=row[0], source_path=row[1], source_hash=row[2], category=row[3],
            processing_mode=row[4], tracks=row[5],
        )


def mark_completed(
    conn: psycopg.Connection,
    job_id: uuid.UUID,
    *,
    engine: str,
    engine_version: str,
    model_name: str,
    metrics: dict[str, Any],
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE transcription_job
            SET status = 'COMPLETED', completed_at = now(),
                engine = %s, engine_version = %s, model_name = %s, metrics = %s
            WHERE id = %s
            """,
            (engine, engine_version, model_name, Jsonb(metrics), job_id),
        )
    conn.commit()


def mark_failed(conn: psycopg.Connection, job_id: uuid.UUID, *, error_message: str, error_code: str | None = None) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE transcription_job
            SET status = 'FAILED', error_code = %s, error_message = %s
            WHERE id = %s
            """,
            (error_code, error_message, job_id),
        )
    conn.commit()


def reconcile_stale_processing(conn: psycopg.Connection) -> None:
    """Startup reconciliation for jobs a crashed previous run left in
    PROCESSING (spec §8): requeue if the source still exists AND still holds
    the same content it had when the job was registered, otherwise fail --
    SOURCE_MISSING if the path is gone, SOURCE_CHANGED if a different file
    now sits at that path (recomputing the hash here, rather than trusting
    the path alone, avoids silently transcribing unrelated new content under
    a stale job's id/hash)."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, source_path, source_hash, processing_mode FROM transcription_job WHERE status = 'PROCESSING'"
        )
        rows = cur.fetchall()
        for job_id, source_path, source_hash, processing_mode in rows:
            # Isolated per-row: a hashing failure for this one row
            # (permissions, the file vanishing mid-check) must not abort
            # reconciliation of the remaining stale rows. Each row's outcome
            # is committed immediately (rather than batched into one final
            # commit) so that a later row's failure -- and the rollback it
            # may require, see below -- can never discard an earlier row's
            # already-decided status.
            try:
                path = Path(source_path)
                if not path.exists():
                    cur.execute(
                        "UPDATE transcription_job SET status = 'FAILED', error_code = 'SOURCE_MISSING' WHERE id = %s",
                        (job_id,),
                    )
                    conn.commit()
                    continue
                current_hash = hash_session(path) if processing_mode == MULTITRACK_MODE else hash_file(path)
                if current_hash != source_hash:
                    cur.execute(
                        "UPDATE transcription_job SET status = 'FAILED', error_code = 'SOURCE_CHANGED' WHERE id = %s",
                        (job_id,),
                    )
                    conn.commit()
                    continue
                cur.execute("UPDATE transcription_job SET status = 'PENDING' WHERE id = %s", (job_id,))
                conn.commit()
            except Exception:
                # Can't verify the hash, so don't blindly requeue against
                # possibly-different content -- mark it FAILED with a clear
                # error code so it surfaces for investigation/explicit retry
                # instead of being left stuck in PROCESSING forever.
                logger.exception("Reconciliation failed for stale job %s", job_id)
                try:
                    # If the exception above came from one of this row's own
                    # cur.execute() calls (a real DB error, not a pure-Python
                    # one like a hashing OSError), Postgres has left this
                    # transaction aborted -- any further statement on it
                    # raises InFailedSqlTransaction until rolled back. This
                    # rollback is always safe to call even when the
                    # transaction isn't aborted; it just clears this row's
                    # own uncommitted work (already committed rows above are
                    # unaffected).
                    conn.rollback()
                    cur.execute(
                        "UPDATE transcription_job SET status = 'FAILED', error_code = 'RECONCILIATION_ERROR' WHERE id = %s",
                        (job_id,),
                    )
                    conn.commit()
                except Exception:
                    # Even the recovery write failed -- log and move on to
                    # the next row rather than let this handler become a new
                    # place an exception can escape reconcile_stale_processing
                    # from.
                    logger.exception("Failed to record RECONCILIATION_ERROR for stale job %s", job_id)


def find_status_by_hash(conn: psycopg.Connection, source_hash: str) -> str | None:
    """Returns the current status of the job registered under this exact
    source_hash, or None if no such job exists yet. Used by the startup scan
    (spec review Fix 5) to decide whether to skip a previously-FAILED file
    rather than silently reactivating it on every daemon restart."""
    with conn.cursor() as cur:
        cur.execute("SELECT status FROM transcription_job WHERE source_hash = %s", (source_hash,))
        row = cur.fetchone()
    conn.rollback()
    return row[0] if row else None


def find_completed_jobs_with_source_still_present(conn: psycopg.Connection) -> list[Job]:
    """Self-heal query: a crash between atomic publish and archive-move
    leaves a COMPLETED job whose source is still sitting in the inbox
    (spec §8) — the caller (watch service startup) archives it. Returns
    `source_hash` alongside each job so the caller can verify the file at
    `source_path` still holds the same content before archiving it."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, source_path, source_hash, category, processing_mode, tracks "
            "FROM transcription_job WHERE status = 'COMPLETED'"
        )
        rows = cur.fetchall()
    result = [
        Job(id=row[0], source_path=row[1], source_hash=row[2], category=row[3], processing_mode=row[4], tracks=row[5])
        for row in rows
        if Path(row[1]).exists()
    ]
    conn.rollback()
    return result
