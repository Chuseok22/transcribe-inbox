from __future__ import annotations
import os
import time

from transcribe_inbox.config import ARCHIVE_ROOT, INBOX_ROOT, STAGING_ROOT
from transcribe_inbox.db.connection import connect_with_backoff
from transcribe_inbox.db.jobs import claim_next_pending_job
from transcribe_inbox.watcher.watch_service import run_startup_reconciliation, start_watching
from transcribe_inbox.worker import process_one_job

POLL_INTERVAL_SECONDS = 5.0


def run() -> None:
    STAGING_ROOT.mkdir(parents=True, exist_ok=True)
    ARCHIVE_ROOT.mkdir(parents=True, exist_ok=True)
    INBOX_ROOT.mkdir(parents=True, exist_ok=True)

    conn = connect_with_backoff(os.environ["DATABASE_URL"])
    # Watcher starts first so its handler exists for reconciliation to seed
    # pending multitrack sessions into (Task 14) -- registering the same
    # already-stable file twice is a harmless idempotent no-op either way.
    observer, handler = start_watching(conn, INBOX_ROOT)
    run_startup_reconciliation(conn, INBOX_ROOT, ARCHIVE_ROOT, handler)

    while True:
        handler.poll_pending_sessions()
        job = claim_next_pending_job(conn)
        if job is None:
            time.sleep(POLL_INTERVAL_SECONDS)
            continue
        process_one_job(conn, job, STAGING_ROOT)


if __name__ == "__main__":
    run()
