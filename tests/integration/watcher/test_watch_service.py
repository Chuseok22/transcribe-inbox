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
    (session / "백지훈.m4a").write_bytes(b"a")
    (session / "홍길동.m4a").write_bytes(b"b")

    enqueue_stable_path(conn, inbox, category="캡스톤", mode="asr-multitrack", job_path=session)

    rows = conn.execute(
        "SELECT tracks FROM transcription_job WHERE processing_mode = 'asr-multitrack'"
    ).fetchall()
    assert len(rows) == 1
    tracks = rows[0][0]
    assert {t["path"] for t in tracks} == {str(session / "백지훈.m4a"), str(session / "홍길동.m4a")}


def test_multitrack_session_registers_only_once_polling_shows_quiescence(tmp_path, conn):
    inbox = tmp_path / "inbox"
    session = inbox / "캡스톤" / "asr-multitrack" / "2026-09-08"
    session.mkdir(parents=True)
    track = session / "백지훈.m4a"
    track.write_bytes(b"a")

    handler = InboxEventHandler(conn, inbox)
    # Simulates the watchdog event that fired on track creation, observed at t=1000.0.
    handler.add_pending_session(session, now_fn=lambda: 1000.0)

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
    track = session / "백지훈.m4a"
    track.write_bytes(b"a")
    stale_mtime = time.time() - 10_000  # simulates an mtime preserved from wherever the file came from
    os.utime(track, (stale_mtime, stale_mtime))

    handler = InboxEventHandler(conn, inbox)
    handler.add_pending_session(session, now_fn=lambda: 1000.0)  # watcher observed this "now"

    # The file's own mtime is ancient, but only 10s have passed since the
    # watcher's observation -> must not register (a mtime-based re-check
    # would wrongly say this is already quiescent).
    handler.poll_pending_sessions(now_fn=lambda: 1000.0 + 10.0)
    assert conn.execute("SELECT count(*) FROM transcription_job").fetchone()[0] == 0


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

    inbox = tmp_path / "inbox"
    archive = tmp_path / "archive"
    inbox.mkdir()
    archive.mkdir()

    stale = inbox / "stale.m4a"
    stale.write_bytes(b"x")
    stale_id = register_job(conn, NewJob(str(stale), "hash-stale", "미분류", "asr"))
    claim_next_pending_job(conn)  # -> PROCESSING, simulating a crash mid-job

    left_behind = inbox / "left_behind.m4a"
    left_behind.write_bytes(b"y")
    completed_id = register_job(conn, NewJob(str(left_behind), "hash-completed", "미분류", "asr"))
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


def test_run_startup_reconciliation_seeds_pending_session_for_not_yet_quiescent_multitrack(tmp_path, conn):
    inbox = tmp_path / "inbox"
    archive = tmp_path / "archive"
    inbox.mkdir()
    archive.mkdir()
    session = inbox / "캡스톤" / "asr-multitrack" / "2026-09-08"
    session.mkdir(parents=True)
    (session / "백지훈.m4a").write_bytes(b"a")  # freshly written -> not quiescent

    handler = InboxEventHandler(conn, inbox)
    run_startup_reconciliation(conn, inbox, archive, handler)

    # Not registered yet (too fresh)...
    assert conn.execute("SELECT count(*) FROM transcription_job").fetchone()[0] == 0
    # ...but the startup scan must have seeded it as a pending candidate, so
    # a later poll (once it's actually old enough) can still pick it up.
    handler.poll_pending_sessions(now_fn=lambda: time.time() + 120.0)
    assert conn.execute("SELECT count(*) FROM transcription_job").fetchone()[0] == 1
