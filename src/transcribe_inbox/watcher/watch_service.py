# src/transcribe_inbox/watcher/watch_service.py
from __future__ import annotations
import logging
import threading
import time
from typing import Callable
from pathlib import Path

import psycopg
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from transcribe_inbox.config import FILE_STABILIZATION_SECONDS, FOLDER_QUIESCENCE_SECONDS
from transcribe_inbox.db.jobs import (
    NewJob, register_job, reconcile_stale_processing, find_completed_jobs_with_source_still_present,
)
from transcribe_inbox.hashing import hash_file, hash_session, is_hidden_file
from transcribe_inbox.publish import archive_source
from transcribe_inbox.watcher.path_parser import MULTITRACK_MODE, parse_inbox_path
from transcribe_inbox.watcher.stabilization import is_folder_quiescent, wait_for_file_stable

logger = logging.getLogger(__name__)


def enqueue_stable_path(
    conn: psycopg.Connection, inbox_root: Path, *, category: str, mode: str, job_path: Path,
) -> None:
    """Registers a job for an already-stable target (a file for asr/diarize,
    a session folder for asr-multitrack)."""
    if mode == MULTITRACK_MODE:
        tracks = [
            {"path": str(p), "speaker_label": p.stem, "offset_seconds": 0.0}
            for p in sorted(job_path.rglob("*"))
            if p.is_file() and not is_hidden_file(p)
        ]
        job = NewJob(
            source_path=str(job_path), source_hash=hash_session(job_path),
            category=category, processing_mode=mode, tracks=tracks,
        )
    else:
        job = NewJob(
            source_path=str(job_path), source_hash=hash_file(job_path),
            category=category, processing_mode=mode,
        )
    register_job(conn, job)


class InboxEventHandler(FileSystemEventHandler):
    """Single-file targets (asr/diarize) are stabilized and enqueued
    directly on their triggering event. Multitrack session folders cannot
    be judged this way — a quiet period produces no event to re-check
    later — so events only record the session in `_pending_sessions`
    (mapped to the wall-clock time the event was observed), and
    `poll_pending_sessions()` (called periodically from Task 15's main
    loop) re-evaluates elapsed time since that observation.

    `_pending_sessions` is keyed on *observation time*, not re-derived from
    file mtimes, because a file moved into the session folder (a same-volume
    Finder drag is a `mv`) keeps its original mtime — an mtime-based re-check
    could see a just-arrived track as already "old" and register the session
    prematurely with tracks still missing."""

    def __init__(self, conn: psycopg.Connection, inbox_root: Path):
        self._conn = conn
        self._inbox_root = inbox_root
        self._pending_sessions: dict[Path, float] = {}
        self._lock = threading.Lock()

    def on_created(self, event) -> None:
        self._handle(Path(event.src_path))

    def on_modified(self, event) -> None:
        self._handle(Path(event.src_path))

    def on_moved(self, event) -> None:
        # A move *within* inbox (rename, or relocating a session folder)
        # only fires this event, never created/modified -- without it, such
        # a move is invisible until the next daemon restart's startup scan.
        self._handle(Path(event.dest_path))

    def add_pending_session(
        self, path: Path, *, last_event_at: float | None = None, now_fn: Callable[[], float] = time.time,
    ) -> None:
        with self._lock:
            self._pending_sessions[path] = last_event_at if last_event_at is not None else now_fn()

    def poll_pending_sessions(self, *, now_fn=time.time) -> None:
        with self._lock:
            candidates = dict(self._pending_sessions)
        for session_path, last_event_at in candidates.items():
            if not session_path.exists():
                with self._lock:
                    self._pending_sessions.pop(session_path, None)
                continue
            if now_fn() - last_event_at >= FOLDER_QUIESCENCE_SECONDS:
                category = session_path.relative_to(self._inbox_root).parts[0]
                enqueue_stable_path(
                    self._conn, self._inbox_root, category=category, mode=MULTITRACK_MODE, job_path=session_path,
                )
                with self._lock:
                    self._pending_sessions.pop(session_path, None)

    def _handle(self, path: Path) -> None:
        # watchdog's dispatcher thread only catches queue.Empty around this
        # call -- any other exception (a file vanishing mid-stabilization,
        # a DB error) kills the watching thread silently, with the process
        # (and launchd) none the wiser. Never let anything escape this method.
        try:
            self._handle_unsafe(path)
        except Exception:
            logger.exception("Error handling inbox event for %s", path)
            self._conn.rollback()

    def _handle_unsafe(self, path: Path) -> None:
        if path.is_dir() or is_hidden_file(path):
            return
        parsed = parse_inbox_path(self._inbox_root, path)
        if parsed is None:
            logger.warning("Skipping ambiguous inbox path: %s", path)
            return
        if parsed.mode == MULTITRACK_MODE:
            self.add_pending_session(parsed.job_path)  # stamps real "now" -- this event just happened
        elif wait_for_file_stable(parsed.job_path, stable_seconds=FILE_STABILIZATION_SECONDS):
            enqueue_stable_path(self._conn, self._inbox_root, category=parsed.category, mode=parsed.mode, job_path=parsed.job_path)


def run_startup_reconciliation(
    conn: psycopg.Connection, inbox_root: Path, archive_root: Path, handler: InboxEventHandler,
) -> None:
    """Runs on daemon startup (spec §8): requeue/fail stale PROCESSING jobs,
    self-heal COMPLETED jobs whose source never made it to archive, and pick
    up any stable file (or seed any not-yet-quiescent multitrack session)
    that arrived while the daemon was down."""
    reconcile_stale_processing(conn)

    for job in find_completed_jobs_with_source_still_present(conn):
        archive_source(Path(job.source_path), archive_root, job.category, job.processing_mode)

    _scan_for_unregistered_stable_paths(conn, inbox_root, handler)


def _scan_for_unregistered_stable_paths(
    conn: psycopg.Connection, inbox_root: Path, handler: InboxEventHandler,
) -> None:
    seen_job_paths: set[Path] = set()
    for path in inbox_root.rglob("*"):
        if not path.is_file() or is_hidden_file(path):
            continue
        parsed = parse_inbox_path(inbox_root, path)
        if parsed is None:
            logger.warning("Skipping ambiguous inbox path during startup scan: %s", path)
            continue
        if parsed.job_path in seen_job_paths:
            continue
        seen_job_paths.add(parsed.job_path)
        if parsed.mode == MULTITRACK_MODE:
            if is_folder_quiescent(parsed.job_path, quiet_seconds=FOLDER_QUIESCENCE_SECONDS):
                enqueue_stable_path(conn, inbox_root, category=parsed.category, mode=parsed.mode, job_path=parsed.job_path)
            else:
                # No live event history survives a restart, so a file's real
                # mtime is the best available signal here (unlike the live
                # handler path above, which deliberately avoids mtime).
                handler.add_pending_session(parsed.job_path, last_event_at=_latest_mtime(parsed.job_path))
        elif wait_for_file_stable(parsed.job_path, stable_seconds=0.0, poll_interval=0.0):
            enqueue_stable_path(conn, inbox_root, category=parsed.category, mode=parsed.mode, job_path=parsed.job_path)


def _latest_mtime(folder: Path) -> float:
    files = [p for p in folder.rglob("*") if p.is_file() and not is_hidden_file(p)]
    return max((p.stat().st_mtime for p in files), default=0.0)


def start_watching(conn: psycopg.Connection, inbox_root: Path) -> tuple[Observer, InboxEventHandler]:
    handler = InboxEventHandler(conn, inbox_root)
    observer = Observer()
    observer.schedule(handler, str(inbox_root), recursive=True)
    observer.start()
    return observer, handler
