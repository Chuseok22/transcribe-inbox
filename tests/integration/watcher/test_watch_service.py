# tests/integration/watcher/test_watch_service.py
import os
import time
from types import SimpleNamespace
import pytest
import psycopg

from transcribe_inbox.watcher.watch_service import InboxEventHandler, run_startup_reconciliation, enqueue_stable_path

pytestmark = pytest.mark.integration
DSN = os.environ.get("TEST_DATABASE_URL", "postgresql://localhost/transcribe_inbox_test")


@pytest.fixture
def conn():
    connection = psycopg.connect(DSN, autocommit=False)
    connection.execute("TRUNCATE transcription_job")
    connection.commit()
    yield connection
    connection.close()


def test_enqueue_stable_path_registers_single_file_job(tmp_path, conn):
    inbox = tmp_path / "inbox"
    (inbox / "컴퓨터네트워크").mkdir(parents=True)
    audio = inbox / "컴퓨터네트워크" / "2주차.m4a"
    audio.write_bytes(b"audio-bytes")

    enqueue_stable_path(conn, inbox, category="컴퓨터네트워크", mode="asr", job_path=audio)

    row = conn.execute(
        "SELECT category, processing_mode, source_path FROM transcription_job WHERE category = %s",
        ("컴퓨터네트워크",),
    ).fetchone()
    assert row == ("컴퓨터네트워크", "asr", str(audio))


def test_enqueue_stable_path_registers_multitrack_session_once(tmp_path, conn):
    inbox = tmp_path / "inbox"
    session = inbox / "캡스톤" / "asr-multitrack" / "2026-09-08"
    session.mkdir(parents=True)
    (session / "김철수.m4a").write_bytes(b"a")
    (session / "홍길동.m4a").write_bytes(b"b")

    enqueue_stable_path(conn, inbox, category="캡스톤", mode="asr-multitrack", job_path=session)

    rows = conn.execute(
        "SELECT tracks FROM transcription_job WHERE processing_mode = 'asr-multitrack'"
    ).fetchall()
    assert len(rows) == 1
    tracks = rows[0][0]
    assert {t["path"] for t in tracks} == {str(session / "김철수.m4a"), str(session / "홍길동.m4a")}


def test_multitrack_session_registers_only_once_polling_shows_quiescence(tmp_path, conn):
    inbox = tmp_path / "inbox"
    session = inbox / "캡스톤" / "asr-multitrack" / "2026-09-08"
    session.mkdir(parents=True)
    track = session / "김철수.m4a"
    track.write_bytes(b"a")

    handler = InboxEventHandler(conn, inbox)
    # Simulates the watchdog event that fired on track creation, observed at t=1000.0.
    handler.add_pending_session(session, "캡스톤", now_fn=lambda: 1000.0)

    # Only 10s have passed since that observation -> not quiescent yet, no job.
    handler.poll_pending_sessions(now_fn=lambda: 1000.0 + 10.0)
    assert conn.execute("SELECT count(*) FROM transcription_job").fetchone()[0] == 0

    # 61s later, still no new activity observed -> quiescent -> registers exactly one job.
    handler.poll_pending_sessions(now_fn=lambda: 1000.0 + 61.0)
    row = conn.execute("SELECT category, processing_mode FROM transcription_job").fetchone()
    assert row == ("캡스톤", "asr-multitrack")

    # Already registered -> a further poll must not create a duplicate.
    handler.poll_pending_sessions(now_fn=lambda: 1000.0 + 120.0)
    assert conn.execute("SELECT count(*) FROM transcription_job").fetchone()[0] == 1


def test_multitrack_session_uses_event_observation_time_not_stale_file_mtime(tmp_path, conn):
    """A file moved into the session folder (a same-volume Finder drag is a
    `mv`, not a copy) keeps its *original* mtime -- if quiescence were
    re-derived from file mtimes on every poll, a dragged-in track could look
    instantly "60s old" and register the session with only one track
    present. Quiescence must instead be judged from when the watcher itself
    last observed activity for this session."""
    inbox = tmp_path / "inbox"
    session = inbox / "캡스톤" / "asr-multitrack" / "2026-09-08"
    session.mkdir(parents=True)
    track = session / "김철수.m4a"
    track.write_bytes(b"a")
    stale_mtime = time.time() - 10_000  # simulates an mtime preserved from wherever the file came from
    os.utime(track, (stale_mtime, stale_mtime))

    handler = InboxEventHandler(conn, inbox)
    handler.add_pending_session(session, "캡스톤", now_fn=lambda: 1000.0)  # watcher observed this "now"

    # The file's own mtime is ancient, but only 10s have passed since the
    # watcher's observation -> must not register (a mtime-based re-check
    # would wrongly say this is already quiescent).
    handler.poll_pending_sessions(now_fn=lambda: 1000.0 + 10.0)
    assert conn.execute("SELECT count(*) FROM transcription_job").fetchone()[0] == 0


def test_poll_pending_sessions_uses_stored_category_not_path_derived_one(tmp_path, conn):
    """poll_pending_sessions must register with the category captured at
    seed time (via parse_inbox_path, from wherever the candidate was first
    added), never re-derive it by slicing the session path -- otherwise the
    two derivations can diverge. Seeding a category that intentionally
    differs from the path's own first segment proves the stored value wins."""
    inbox = tmp_path / "inbox"
    session = inbox / "캡스톤" / "asr-multitrack" / "2026-09-08"
    session.mkdir(parents=True)
    (session / "김철수.m4a").write_bytes(b"a")

    handler = InboxEventHandler(conn, inbox)
    handler.add_pending_session(session, "다른카테고리", now_fn=lambda: 1000.0)
    handler.poll_pending_sessions(now_fn=lambda: 1000.0 + 120.0)

    row = conn.execute("SELECT category FROM transcription_job").fetchone()
    assert row == ("다른카테고리",)


def test_poll_pending_sessions_isolates_exceptions_per_candidate(tmp_path, conn, monkeypatch):
    """A candidate that fails to enqueue (a vanished track, a DB error) must
    not stop the remaining candidates in the same poll from being processed,
    and must not let the exception escape -- unlike `_handle`, nothing calls
    poll_pending_sessions with its own guard (Task 15's main loop)."""
    inbox = tmp_path / "inbox"
    failing_session = inbox / "캡스톤" / "asr-multitrack" / "2026-09-08"
    failing_session.mkdir(parents=True)
    (failing_session / "a.m4a").write_bytes(b"a")
    ok_session = inbox / "캡스톤" / "asr-multitrack" / "2026-09-09"
    ok_session.mkdir(parents=True)
    (ok_session / "b.m4a").write_bytes(b"b")

    handler = InboxEventHandler(conn, inbox)
    handler.add_pending_session(failing_session, "캡스톤", now_fn=lambda: 1000.0)
    handler.add_pending_session(ok_session, "캡스톤", now_fn=lambda: 1000.0)

    real_enqueue = enqueue_stable_path

    def flaky_enqueue(conn_, inbox_root, *, category, mode, job_path):
        if job_path == failing_session:
            raise RuntimeError("disk error")
        return real_enqueue(conn_, inbox_root, category=category, mode=mode, job_path=job_path)

    monkeypatch.setattr("transcribe_inbox.watcher.watch_service.enqueue_stable_path", flaky_enqueue)

    handler.poll_pending_sessions(now_fn=lambda: 1000.0 + 120.0)  # must not raise

    rows = conn.execute("SELECT source_path FROM transcription_job").fetchall()
    assert [r[0] for r in rows] == [str(ok_session)]
    # The failing candidate stays pending so a future poll can retry it.
    assert failing_session in handler._pending_sessions


def test_poll_pending_sessions_preserves_entry_refreshed_mid_enqueue(tmp_path, conn, monkeypatch):
    """If a new track arrives (refreshing the pending entry) while
    enqueue_stable_path is in flight for that same session -- hashing takes
    time, and the lock is released during it -- popping the candidate
    unconditionally afterward would silently drop that fresh entry. That's
    the exact "multitrack session registers with tracks missing" failure
    class `_pending_sessions` exists to prevent, reached via a different
    path. Only the exact snapshot acted on may be popped."""
    inbox = tmp_path / "inbox"
    session = inbox / "캡스톤" / "asr-multitrack" / "2026-09-08"
    session.mkdir(parents=True)
    (session / "김철수.m4a").write_bytes(b"a")

    handler = InboxEventHandler(conn, inbox)
    handler.add_pending_session(session, "캡스톤", now_fn=lambda: 1000.0)

    real_enqueue = enqueue_stable_path

    def enqueue_then_refresh(conn_, inbox_root, *, category, mode, job_path):
        result = real_enqueue(conn_, inbox_root, category=category, mode=mode, job_path=job_path)
        # Simulates the watchdog thread observing a new track for this same
        # session while this enqueue call was still in flight.
        handler.add_pending_session(job_path, category, now_fn=lambda: 2000.0)
        return result

    monkeypatch.setattr("transcribe_inbox.watcher.watch_service.enqueue_stable_path", enqueue_then_refresh)

    handler.poll_pending_sessions(now_fn=lambda: 1000.0 + 120.0)

    assert conn.execute("SELECT count(*) FROM transcription_job").fetchone()[0] == 1
    # The freshly-refreshed pending entry must survive, not be dropped.
    assert session in handler._pending_sessions
    assert handler._pending_sessions[session].last_event_at == 2000.0


def test_poll_pending_sessions_skips_a_candidate_refreshed_after_the_snapshot(tmp_path, conn):
    """A track can arrive (refreshing the pending entry) in the gap between
    the `candidates` snapshot at the top of poll_pending_sessions and this
    specific candidate's turn in the loop. Without re-checking right before
    the (slow, since it hashes every file) hash+register call, the session
    would be hashed/registered with a stale/incomplete track list -- a
    subtly different failure than the entry merely being dropped afterward
    (already covered by the mid-enqueue-refresh test above), since here the
    bad registration happens before any pop-guard even runs."""
    inbox = tmp_path / "inbox"
    session = inbox / "캡스톤" / "asr-multitrack" / "2026-09-08"
    session.mkdir(parents=True)
    (session / "김철수.m4a").write_bytes(b"a")

    handler = InboxEventHandler(conn, inbox)
    handler.add_pending_session(session, "캡스톤", now_fn=lambda: 1000.0)

    def now_fn_that_refreshes_mid_poll():
        # First (and only, for this single candidate) call: the top-level
        # quiescence check. Its side effect simulates a new track arriving
        # concurrently, exactly like a live watchdog event would, between
        # the snapshot taken at the top of poll_pending_sessions and this
        # candidate's processing.
        handler.add_pending_session(session, "캡스톤", now_fn=lambda: 5000.0)
        return 1000.0 + 120.0  # satisfies quiescence for the snapshot's own timestamp

    handler.poll_pending_sessions(now_fn=now_fn_that_refreshes_mid_poll)

    assert conn.execute("SELECT count(*) FROM transcription_job").fetchone()[0] == 0
    assert session in handler._pending_sessions
    assert handler._pending_sessions[session].last_event_at == 5000.0


def test_handle_swallows_rollback_failure_too(tmp_path, conn, monkeypatch):
    """If rollback() itself raises (e.g. the connection was already broken
    by the same error that made _handle_unsafe raise), that must not escape
    _handle either -- otherwise wrapping _handle_unsafe defeats its own
    purpose in exactly the scenario it exists to handle."""
    inbox = tmp_path / "inbox"
    (inbox / "컴퓨터네트워크").mkdir(parents=True)
    audio = inbox / "컴퓨터네트워크" / "2주차.m4a"
    audio.write_bytes(b"audio-bytes")

    handler = InboxEventHandler(conn, inbox)
    monkeypatch.setattr(
        "transcribe_inbox.watcher.watch_service.wait_for_file_stable",
        lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("disk error")),
    )

    def broken_rollback():
        raise psycopg.OperationalError("connection closed")

    monkeypatch.setattr(conn, "rollback", broken_rollback)

    handler.on_created(SimpleNamespace(src_path=str(audio)))  # must not raise


def test_on_moved_registers_a_relocated_multitrack_session_directory(tmp_path, conn):
    """watchdog fires a single `moved` event carrying the *directory's* own
    dest_path when a whole asr-multitrack session folder is renamed/moved --
    no per-file event follows. Without resolving this via a representative
    file inside it, the session would never be registered until the next
    daemon restart's startup scan (review finding)."""
    inbox = tmp_path / "inbox"
    old_session = inbox / "캡스톤" / "asr-multitrack" / "old-name"
    old_session.mkdir(parents=True)
    (old_session / "김철수.m4a").write_bytes(b"a")
    new_session = inbox / "캡스톤" / "asr-multitrack" / "new-name"
    old_session.rename(new_session)

    handler = InboxEventHandler(conn, inbox)
    handler.on_moved(SimpleNamespace(dest_path=str(new_session)))

    assert new_session in handler._pending_sessions
    assert handler._pending_sessions[new_session].category == "캡스톤"


def test_on_moved_ignores_a_moved_non_multitrack_directory(tmp_path, conn):
    """A moved directory that isn't an asr-multitrack session (e.g. an
    unrelated subfolder a user drops into the inbox) must not be registered
    as a pending session."""
    inbox = tmp_path / "inbox"
    unrelated = inbox / "컴퓨터네트워크" / "실습자료"
    unrelated.mkdir(parents=True)
    (unrelated / "notes.txt").write_bytes(b"x")

    handler = InboxEventHandler(conn, inbox)
    handler.on_moved(SimpleNamespace(dest_path=str(unrelated)))

    assert handler._pending_sessions == {}


def test_on_moved_handles_a_file_relocated_within_inbox(tmp_path, conn):
    # watchdog fires `moved`, never `created`/`modified`, for a rename or a
    # move within the watched tree -- without on_moved, this is invisible
    # until the next daemon restart's startup scan.
    inbox = tmp_path / "inbox"
    (inbox / "컴퓨터네트워크").mkdir(parents=True)
    audio = inbox / "컴퓨터네트워크" / "2주차.m4a"
    audio.write_bytes(b"audio-bytes")

    handler = InboxEventHandler(conn, inbox)
    handler.on_moved(SimpleNamespace(dest_path=str(audio)))

    row = conn.execute(
        "SELECT category, processing_mode FROM transcription_job WHERE category = %s",
        ("컴퓨터네트워크",),
    ).fetchone()
    assert row == ("컴퓨터네트워크", "asr")


def test_handle_swallows_exceptions_and_rolls_back_instead_of_killing_the_watch_thread(tmp_path, conn, monkeypatch):
    # watchdog's dispatcher only catches queue.Empty around event callbacks
    # -- anything else escaping _handle silently kills the watching thread
    # while the process (and launchd) stay up, none the wiser.
    inbox = tmp_path / "inbox"
    (inbox / "컴퓨터네트워크").mkdir(parents=True)
    audio = inbox / "컴퓨터네트워크" / "2주차.m4a"
    audio.write_bytes(b"audio-bytes")

    handler = InboxEventHandler(conn, inbox)
    monkeypatch.setattr(
        "transcribe_inbox.watcher.watch_service.wait_for_file_stable",
        lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("disk error")),
    )
    rollback_calls = []
    monkeypatch.setattr(conn, "rollback", lambda: rollback_calls.append(1))

    handler.on_created(SimpleNamespace(src_path=str(audio)))  # must not raise

    assert rollback_calls == [1]


def test_run_startup_reconciliation_requeues_and_self_heals(tmp_path, conn):
    from transcribe_inbox.db.jobs import register_job, NewJob, claim_next_pending_job, mark_completed
    from transcribe_inbox.hashing import hash_file

    inbox = tmp_path / "inbox"
    archive = tmp_path / "archive"
    inbox.mkdir()
    archive.mkdir()

    stale = inbox / "stale.m4a"
    stale.write_bytes(b"x")
    # source_hash must be the *real* content hash -- reconcile_stale_processing
    # (called by run_startup_reconciliation) now recomputes and compares it
    # (Fix 4) before requeuing.
    stale_id = register_job(conn, NewJob(str(stale), hash_file(stale), "미분류", "asr"))
    claim_next_pending_job(conn)  # -> PROCESSING, simulating a crash mid-job

    left_behind = inbox / "left_behind.m4a"
    left_behind.write_bytes(b"y")
    # Same requirement here -- the self-heal archive step now verifies
    # left_behind's content still matches source_hash before archiving it.
    completed_id = register_job(conn, NewJob(str(left_behind), hash_file(left_behind), "미분류", "asr"))
    claim_next_pending_job(conn)
    mark_completed(conn, completed_id, engine="whisper.cpp", engine_version="1.0.0", model_name="large-v3", metrics={})

    handler = InboxEventHandler(conn, inbox)
    run_startup_reconciliation(conn, inbox, archive, handler)

    stale_status = conn.execute(
        "SELECT status FROM transcription_job WHERE id = %s", (stale_id,)
    ).fetchone()[0]
    assert stale_status == "PENDING"
    assert not left_behind.exists()
    assert (archive / "미분류" / "asr" / "left_behind.m4a").exists()


def test_run_startup_reconciliation_skips_archiving_completed_job_when_content_changed(tmp_path, conn):
    """If different content now sits at a COMPLETED job's source_path than
    when it finished (Fix 2's old overwrite bug made this reachable, but
    it's a real risk independent of that too), the self-heal step must not
    archive it as that old job's leftover source -- it must leave it alone
    so the normal startup scan picks it up as its own new job."""
    from transcribe_inbox.db.jobs import register_job, NewJob, claim_next_pending_job, mark_completed
    from transcribe_inbox.hashing import hash_file

    inbox = tmp_path / "inbox"
    archive = tmp_path / "archive"
    inbox.mkdir()
    archive.mkdir()

    source = inbox / "left_behind.m4a"
    source.write_bytes(b"original")
    completed_id = register_job(conn, NewJob(str(source), hash_file(source), "미분류", "asr"))
    claim_next_pending_job(conn)
    mark_completed(conn, completed_id, engine="whisper.cpp", engine_version="1.0.0", model_name="large-v3", metrics={})

    source.write_bytes(b"brand new unrelated content")  # a fresh drop landed at the same path

    handler = InboxEventHandler(conn, inbox)
    run_startup_reconciliation(conn, inbox, archive, handler)

    # Not archived under the old job's identity...
    assert source.exists()
    assert not (archive / "미분류" / "asr" / "left_behind.m4a").exists()
    # ...but the startup scan (which run_startup_reconciliation also runs)
    # picks it up as a brand-new job of its own.
    rows = conn.execute(
        "SELECT status FROM transcription_job WHERE source_hash = %s", (hash_file(source),),
    ).fetchall()
    assert [r[0] for r in rows] == ["PENDING"]


def test_startup_scan_skips_a_previously_failed_file_instead_of_reactivating_it(tmp_path, conn):
    """The startup scan must not reactivate a FAILED job for a file still
    sitting in the inbox on every daemon restart (Fix 5) -- that would waste
    GPU time retrying a permanently-broken file forever. Reactivation stays
    reserved for a genuine re-drop via the live watcher or the explicit
    `retry` CLI command."""
    from transcribe_inbox.db.jobs import register_job, NewJob, mark_failed
    from transcribe_inbox.hashing import hash_file

    inbox = tmp_path / "inbox"
    archive = tmp_path / "archive"
    (inbox / "미분류").mkdir(parents=True)
    archive.mkdir()

    broken = inbox / "미분류" / "broken.m4a"
    broken.write_bytes(b"corrupt-audio")
    job_id = register_job(conn, NewJob(str(broken), hash_file(broken), "미분류", "asr"))
    mark_failed(conn, job_id, error_message="unsupported codec")

    handler = InboxEventHandler(conn, inbox)
    run_startup_reconciliation(conn, inbox, archive, handler)

    row = conn.execute(
        "SELECT status, retry_count FROM transcription_job WHERE id = %s", (job_id,)
    ).fetchone()
    assert row == ("FAILED", 0)  # untouched, not reactivated to PENDING


def test_run_startup_reconciliation_seeds_pending_session_for_not_yet_quiescent_multitrack(tmp_path, conn):
    inbox = tmp_path / "inbox"
    archive = tmp_path / "archive"
    inbox.mkdir()
    archive.mkdir()
    session = inbox / "캡스톤" / "asr-multitrack" / "2026-09-08"
    session.mkdir(parents=True)
    (session / "김철수.m4a").write_bytes(b"a")  # freshly written -> not quiescent

    handler = InboxEventHandler(conn, inbox)
    run_startup_reconciliation(conn, inbox, archive, handler)

    # Not registered yet (too fresh)...
    assert conn.execute("SELECT count(*) FROM transcription_job").fetchone()[0] == 0
    # ...but the startup scan must have seeded it as a pending candidate, so
    # a later poll (once it's actually old enough) can still pick it up.
    handler.poll_pending_sessions(now_fn=lambda: time.time() + 120.0)
    assert conn.execute("SELECT count(*) FROM transcription_job").fetchone()[0] == 1
