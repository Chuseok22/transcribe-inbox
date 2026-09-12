# src/transcribe_inbox/watcher/watch_service.py
from __future__ import annotations
import logging
import threading
import time
from typing import Callable, NamedTuple
from pathlib import Path

import psycopg
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from transcribe_inbox.config import FILE_STABILIZATION_SECONDS, FOLDER_QUIESCENCE_SECONDS
from transcribe_inbox.db.jobs import (
    NewJob, register_job, reconcile_stale_processing, find_completed_jobs_with_source_still_present,
    find_status_by_hash,
)
from transcribe_inbox.hashing import hash_file, hash_session, is_hidden_file
from transcribe_inbox.publish import archive_source
from transcribe_inbox.watcher.path_parser import MULTITRACK_MODE, parse_inbox_path
from transcribe_inbox.watcher.stabilization import is_folder_quiescent, wait_for_file_stable

logger = logging.getLogger(__name__)


def _compute_source_hash(mode: str, job_path: Path) -> str:
    return hash_session(job_path) if mode == MULTITRACK_MODE else hash_file(job_path)


def enqueue_stable_path(
    conn: psycopg.Connection, inbox_root: Path, *, category: str, mode: str, job_path: Path,
    source_hash: str | None = None,
) -> None:
    """Registers a job for an already-stable target (a file for asr/diarize,
    a session folder for asr-multitrack). `source_hash` may be passed
    precomputed -- the startup scan already needs it for its own FAILED-
    status pre-check (Fix 5) and passes it through here to avoid hashing the
    same (possibly large) file/session twice."""
    if source_hash is None:
        source_hash = _compute_source_hash(mode, job_path)
    if mode == MULTITRACK_MODE:
        tracks = [
            {"path": str(p), "speaker_label": p.stem, "offset_seconds": 0.0}
            for p in sorted(job_path.rglob("*"))
            if p.is_file() and not is_hidden_file(p)
        ]
        job = NewJob(
            source_path=str(job_path), source_hash=source_hash,
            category=category, processing_mode=mode, tracks=tracks,
        )
    else:
        job = NewJob(
            source_path=str(job_path), source_hash=source_hash,
            category=category, processing_mode=mode,
        )
    if register_job(conn, job) is None:
        # A PENDING/PROCESSING/COMPLETED job for this exact content already
        # exists -- register_job's documented idempotent skip. Benign (e.g.
        # watchdog coalescing duplicate events for the same drop), but
        # otherwise completely silent, so log it for anyone looking.
        logger.info(
            "Skipped enqueuing %s: a job for this content hash already exists", job_path,
        )


class PendingSession(NamedTuple):
    """A multitrack session candidate awaiting quiescence: the wall-clock
    time the watcher last observed activity for it, and the category it
    resolved to (via `parse_inbox_path`) when first seeded -- so a later
    poll never has to re-derive the category from the path itself."""
    last_event_at: float
    category: str


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
        self._pending_sessions: dict[Path, PendingSession] = {}
        # Paths currently being stabilized+enqueued by _handle_unsafe's
        # single-file branch -- lets a re-entrant event for the same path
        # (FSEvents coalesces a large copy into a `modified` roughly every
        # ~1s) skip straight through instead of blocking the one watchdog
        # dispatch thread behind a redundant full wait+re-hash.
        self._in_flight: set[Path] = set()
        self._lock = threading.Lock()
        # Separate from `_lock` above (which only ever protects the
        # in-memory `_pending_sessions`/`_in_flight` bookkeeping): this one
        # gives mutual exclusion over every use of `self._conn` that commits
        # or rolls back. psycopg's own internal connection lock only
        # serializes individual statements, not whole execute-then-commit
        # sequences, so without a real mutex here one thread's rollback
        # (fired by an unrelated exception) could land between another
        # thread's execute() and its own subsequent commit() on this shared
        # connection, discarding a row that thread already believed it
        # successfully registered. Kept separate from `_lock` so a slow DB
        # operation on one thread never blocks the other thread's unrelated
        # in-memory bookkeeping (e.g. `add_pending_session`).
        self._conn_lock = threading.Lock()

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
        self, path: Path, category: str, *, last_event_at: float | None = None, now_fn: Callable[[], float] = time.time,
    ) -> None:
        with self._lock:
            self._pending_sessions[path] = PendingSession(
                last_event_at if last_event_at is not None else now_fn(), category,
            )

    def poll_pending_sessions(self, *, now_fn=time.time) -> None:
        with self._lock:
            candidates = dict(self._pending_sessions)
        for session_path, pending in candidates.items():
            if not session_path.exists():
                with self._lock:
                    self._pending_sessions.pop(session_path, None)
                continue
            if now_fn() - pending.last_event_at >= FOLDER_QUIESCENCE_SECONDS:
                with self._lock:
                    # A track can arrive (refreshing this entry) in the gap
                    # between the `candidates` snapshot at the top of this
                    # method and reaching this point -- re-check right before
                    # the (slow, since it hashes every file) hash+register
                    # call below, not just after it (see the pop-guard at the
                    # end of this branch), so a session that just gained a
                    # new track is never hashed/registered with an
                    # incomplete/stale track list. Skip; a later poll will
                    # re-evaluate the refreshed entry.
                    if self._pending_sessions.get(session_path) != pending:
                        continue
                # Isolated per-candidate: a vanished track, a hashing error,
                # or a DB error registering this one session must not stop
                # the remaining candidates in this poll from being processed,
                # and must not leave the connection in a failed-transaction
                # state for the caller (Task 15's main loop).
                try:
                    with self._conn_lock:
                        enqueue_stable_path(
                            self._conn, self._inbox_root,
                            category=pending.category, mode=MULTITRACK_MODE, job_path=session_path,
                        )
                except Exception:
                    logger.exception("Error enqueuing pending multitrack session %s", session_path)
                    self._safe_rollback()
                    continue
                with self._lock:
                    # Only pop the entry we actually acted on -- if a new
                    # event refreshed it (a track arrived) while we were
                    # hashing outside the lock, that fresh entry must survive
                    # so a future poll re-evaluates it instead of losing it.
                    if self._pending_sessions.get(session_path) == pending:
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
            self._safe_rollback()

    def _safe_rollback(self) -> None:
        # If the connection is already broken (the same error that got us
        # here may have broken it), rollback() itself can raise -- swallow
        # that too, since there's nothing left to roll back to.
        try:
            with self._conn_lock:
                self._conn.rollback()
        except Exception:
            logger.exception("Error rolling back connection after a previous error")

    def _handle_unsafe(self, path: Path) -> None:
        if is_hidden_file(path):
            return
        if path.is_dir():
            self._handle_moved_directory(path)
            return
        parsed = parse_inbox_path(self._inbox_root, path)
        if parsed is None:
            logger.warning("Skipping ambiguous inbox path: %s", path)
            return
        if parsed.mode == MULTITRACK_MODE:
            self.add_pending_session(parsed.job_path, parsed.category)  # stamps real "now" -- this event just happened
            return

        with self._lock:
            if parsed.job_path in self._in_flight:
                return  # already being stabilized+enqueued by an earlier, still-in-flight event
            self._in_flight.add(parsed.job_path)
        try:
            if wait_for_file_stable(parsed.job_path, stable_seconds=FILE_STABILIZATION_SECONDS):
                with self._conn_lock:
                    enqueue_stable_path(self._conn, self._inbox_root, category=parsed.category, mode=parsed.mode, job_path=parsed.job_path)
        finally:
            with self._lock:
                self._in_flight.discard(parsed.job_path)

    def _handle_moved_directory(self, path: Path) -> None:
        """A moved/renamed directory only fires a single on_moved event for
        the destination directory itself -- no per-file event follows, so an
        asr-multitrack session folder moved (or renamed) as a whole would
        otherwise never be registered until the next daemon restart's
        startup scan. Resolve it via one representative file inside it and
        seed it into `_pending_sessions` exactly like a live per-file event
        would (review finding)."""
        representative_files = sorted(p for p in path.rglob("*") if p.is_file() and not is_hidden_file(p))
        if not representative_files:
            return
        parsed = parse_inbox_path(self._inbox_root, representative_files[0])
        if parsed is None or parsed.mode != MULTITRACK_MODE:
            return
        self.add_pending_session(parsed.job_path, parsed.category)


def run_startup_reconciliation(
    conn: psycopg.Connection, inbox_root: Path, archive_root: Path, handler: InboxEventHandler,
) -> None:
    """Runs on daemon startup (spec §8): requeue/fail stale PROCESSING jobs,
    self-heal COMPLETED jobs whose source never made it to archive, and pick
    up any stable file (or seed any not-yet-quiescent multitrack session)
    that arrived while the daemon was down."""
    reconcile_stale_processing(conn)

    for job in find_completed_jobs_with_source_still_present(conn):
        source_path = Path(job.source_path)
        # A persistently-failing hash or move here (permissions, a dangling
        # path, a file vanishing mid-check) must not escape and kill the
        # daemon before it ever starts watching -- launchd would just restart
        # into the same failure forever, permanently blocking the self-heal
        # this loop exists for.
        try:
            current_hash = hash_session(source_path) if job.processing_mode == MULTITRACK_MODE else hash_file(source_path)
            if current_hash != job.source_hash:
                # Different content now sits at this path than when the job
                # completed -- archiving it here would silently treat
                # brand-new, never-transcribed content as this old job's
                # leftover source. Leave it for the normal startup scan below
                # to register as its own job.
                logger.warning(
                    "Startup reconciliation: skipping archive for job %s -- "
                    "content at %s no longer matches the completed job's source_hash",
                    job.id, source_path,
                )
                continue
            archive_source(source_path, archive_root, job.category, job.processing_mode)
        except Exception:
            logger.exception("Startup reconciliation: failed to archive already-completed job %s", job.id)

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
                _enqueue_unless_previously_failed(conn, inbox_root, parsed.category, parsed.mode, parsed.job_path)
            else:
                # No live event history survives a restart, so a file's real
                # mtime is the best available signal here (unlike the live
                # handler path above, which deliberately avoids mtime).
                handler.add_pending_session(
                    parsed.job_path, parsed.category, last_event_at=_latest_mtime(parsed.job_path),
                )
        # stable_seconds=0.0 would return True on the very first size sample
        # (nothing to compare it against yet) -- a real, if short, window is
        # needed so a daemon restart landing mid-copy doesn't register a
        # truncated file as complete. Startup isn't latency-sensitive, but
        # shouldn't hang forever either.
        elif wait_for_file_stable(parsed.job_path, stable_seconds=2.0, poll_interval=0.5):
            _enqueue_unless_previously_failed(conn, inbox_root, parsed.category, parsed.mode, parsed.job_path)


def _enqueue_unless_previously_failed(
    conn: psycopg.Connection, inbox_root: Path, category: str, mode: str, job_path: Path,
) -> None:
    """Startup-scan-only wrapper around enqueue_stable_path: a FAILED job for
    this exact content must not be silently reactivated on every daemon
    restart (potentially tens of minutes of GPU time re-trying a
    permanently-broken file) -- that reactivation is reserved for a genuine
    re-drop via the live watcher, or the explicit `retry` CLI command, both
    of which still go through register_job's normal atomic upsert unchanged."""
    source_hash = _compute_source_hash(mode, job_path)
    existing_status = find_status_by_hash(conn, source_hash)
    if existing_status == "FAILED":
        logger.info(
            "Startup scan: skipping previously-failed job for %s (source_hash=%s) -- "
            "use `transcribe-inbox retry` to reactivate it explicitly", job_path, source_hash,
        )
        return
    enqueue_stable_path(conn, inbox_root, category=category, mode=mode, job_path=job_path, source_hash=source_hash)


def _latest_mtime(folder: Path) -> float:
    files = [p for p in folder.rglob("*") if p.is_file() and not is_hidden_file(p)]
    return max((p.stat().st_mtime for p in files), default=0.0)


def start_watching(conn: psycopg.Connection, inbox_root: Path) -> tuple[Observer, InboxEventHandler]:
    handler = InboxEventHandler(conn, inbox_root)
    observer = Observer()
    observer.schedule(handler, str(inbox_root), recursive=True)
    observer.start()
    return observer, handler
