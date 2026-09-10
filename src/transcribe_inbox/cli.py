from __future__ import annotations
import argparse
import sys
from pathlib import Path

import psycopg

from transcribe_inbox.db.connection import connect_with_backoff


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="transcribe-inbox")
    subparsers = parser.add_subparsers(dest="command", required=True)

    retry_parser = subparsers.add_parser("retry", help="Reset a FAILED job back to PENDING")
    retry_parser.add_argument("job_id")

    return parser


def retry(conn: psycopg.Connection, job_id: str) -> None:
    row = conn.execute(
        "SELECT source_path, status FROM transcription_job WHERE id = %s", (job_id,)
    ).fetchone()
    if row is None:
        print(f"No job with id {job_id}", file=sys.stderr)
        sys.exit(1)
    source_path, status = row
    if status != "FAILED":
        print(f"Job {job_id} is {status}, not FAILED — nothing to do", file=sys.stderr)
        sys.exit(1)
    if not Path(source_path).exists():
        print(f"Source file no longer exists: {source_path}", file=sys.stderr)
        sys.exit(1)
    conn.execute(
        "UPDATE transcription_job SET status = 'PENDING', retry_count = retry_count + 1, error_code = NULL, error_message = NULL WHERE id = %s",
        (job_id,),
    )
    conn.commit()
    print(f"Job {job_id} reset to PENDING")


def main() -> None:
    import os
    args = build_parser().parse_args()
    conn = connect_with_backoff(os.environ["DATABASE_URL"])
    if args.command == "retry":
        retry(conn, args.job_id)
