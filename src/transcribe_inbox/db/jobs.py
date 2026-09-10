from __future__ import annotations
import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psycopg
from psycopg.types.json import Jsonb


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
    category: str
    processing_mode: str
    tracks: list[dict] | None


def register_job(conn: psycopg.Connection, job: NewJob) -> uuid.UUID | None:
    """Returns the job id for a newly-created or FAILED->PENDING-reactivated
    job; returns None if a PENDING/PROCESSING/COMPLETED job with this hash
    already exists (idempotent skip, spec §8)."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, status FROM transcription_job WHERE source_hash = %s", (job.source_hash,),
        )
        row = cur.fetchone()
        if row is not None:
            existing_id, status = row
            if status != "FAILED":
                conn.rollback()
                return None
            cur.execute(
                """
                UPDATE transcription_job
                SET status = 'PENDING', retry_count = retry_count + 1,
                    error_code = NULL, error_message = NULL
                WHERE id = %s
                """,
                (existing_id,),
            )
            conn.commit()
            return existing_id

        new_id = uuid.uuid4()
        cur.execute(
            """
            INSERT INTO transcription_job
                (id, source_path, source_hash, category, processing_mode, tracks, status)
            VALUES (%s, %s, %s, %s, %s, %s, 'PENDING')
            """,
            (
                new_id, job.source_path, job.source_hash, job.category, job.processing_mode,
                Jsonb(job.tracks) if job.tracks is not None else None,
            ),
        )
        conn.commit()
        return new_id


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
            RETURNING id, source_path, category, processing_mode, tracks
            """
        )
        row = cur.fetchone()
        conn.commit()
        if row is None:
            return None
        return Job(id=row[0], source_path=row[1], category=row[2], processing_mode=row[3], tracks=row[4])


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
    PROCESSING (spec §8): requeue if the source still exists, otherwise fail
    with SOURCE_MISSING so it doesn't retry forever against a missing file."""
    with conn.cursor() as cur:
        cur.execute("SELECT id, source_path FROM transcription_job WHERE status = 'PROCESSING'")
        rows = cur.fetchall()
        for job_id, source_path in rows:
            if Path(source_path).exists():
                cur.execute("UPDATE transcription_job SET status = 'PENDING' WHERE id = %s", (job_id,))
            else:
                cur.execute(
                    "UPDATE transcription_job SET status = 'FAILED', error_code = 'SOURCE_MISSING' WHERE id = %s",
                    (job_id,),
                )
    conn.commit()


def find_completed_jobs_with_source_still_present(conn: psycopg.Connection) -> list[Job]:
    """Self-heal query: a crash between atomic publish and archive-move
    leaves a COMPLETED job whose source is still sitting in the inbox
    (spec §8) — the caller (watch service startup) archives it."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, source_path, category, processing_mode, tracks FROM transcription_job WHERE status = 'COMPLETED'"
        )
        rows = cur.fetchall()
    result = [
        Job(id=row[0], source_path=row[1], category=row[2], processing_mode=row[3], tracks=row[4])
        for row in rows
        if Path(row[1]).exists()
    ]
    conn.rollback()
    return result
