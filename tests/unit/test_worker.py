import json
from pathlib import Path
from transcribe_inbox.db.jobs import Job
from transcribe_inbox.transcript.schema import TranscriptDocument, Segment, SCHEMA_VERSION
from transcribe_inbox.worker import process_one_job


class FakeEngine:
    name = "whisper.cpp"
    version = "1.0.0"

    def monitoring_pid(self):
        return 999

    def transcribe(self, request, *, progress_callback=None):
        if progress_callback:
            progress_callback(100.0, "TRANSCRIBING")
        return TranscriptDocument(
            schema_version=SCHEMA_VERSION, pipeline_version="0.1.0", engine=self.name,
            engine_version=self.version, model="ggml-large-v3", language="ko",
            source_filename=request.source_filename, audio_duration_seconds=5.0,
            segments=[Segment(start=0.0, end=5.0, text="안녕하세요", speaker=None)],
        )


class FakeJobMonitor:
    """Replaces the real thread/subprocess-backed JobMonitor in unit tests —
    a real one would shell out to `/usr/bin/footprint` on every test run,
    which is slow, macOS-only, and not what these tests are checking."""
    footprint_start_bytes = 1000
    footprint_peak_bytes = 1500
    footprint_end_bytes = 1200
    minimum_available_memory_bytes = 2000
    swap_out_delta_bytes = 0

    def __init__(self, pid_provider, heartbeat, **kwargs):
        pass

    def start(self):
        pass

    def stop(self):
        pass


def test_process_one_job_publishes_and_marks_completed(tmp_path, monkeypatch):
    source = tmp_path / "inbox" / "컴퓨터네트워크" / "2주차.m4a"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"audio")
    job = Job(id="job-1", source_path=str(source), category="컴퓨터네트워크", processing_mode="asr", tracks=None)

    monkeypatch.setattr("transcribe_inbox.worker.engine_for_mode", lambda mode: FakeEngine())
    monkeypatch.setattr(
        "transcribe_inbox.worker.normalize_to_wav",
        lambda path, **kwargs: tmp_path / "normalized.wav",
    )
    (tmp_path / "normalized.wav").write_bytes(b"wav")
    output_root = tmp_path / "Transcripts"
    monkeypatch.setattr(
        "transcribe_inbox.worker.output_dir_for", lambda category, label: output_root / category / label,
    )

    marks = {"completed": None, "failed": None}
    monkeypatch.setattr(
        "transcribe_inbox.worker.mark_completed",
        lambda conn, job_id, **kwargs: marks.__setitem__("completed", (job_id, kwargs)),
    )
    monkeypatch.setattr(
        "transcribe_inbox.worker.mark_failed",
        lambda conn, job_id, **kwargs: marks.__setitem__("failed", (job_id, kwargs)),
    )
    notified = []
    monkeypatch.setattr("transcribe_inbox.worker.notify_completed", lambda *a: notified.append(a))
    monkeypatch.setattr("transcribe_inbox.worker.archive_source", lambda *a, **kw: tmp_path / "archived.m4a")
    # Replaces the real thread/subprocess-backed JobMonitor -- see its
    # definition above for why a real one has no place in a unit test.
    monkeypatch.setattr("transcribe_inbox.worker.JobMonitor", FakeJobMonitor)

    staging_root = tmp_path / "staging"
    process_one_job(conn=None, job=job, staging_root=staging_root)

    assert marks["completed"] is not None
    assert marks["completed"][1]["metrics"]["audioDurationSeconds"] == 5.0
    assert marks["completed"][1]["metrics"]["processFootprintPeakBytes"] == 1500
    assert marks["failed"] is None
    assert notified == [("컴퓨터네트워크", "2주차.m4a")]
    assert (output_root / "컴퓨터네트워크" / "2주차" / "transcript.json").exists()


def test_process_one_job_marks_failed_on_engine_error(tmp_path, monkeypatch):
    source = tmp_path / "inbox" / "x.m4a"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"audio")
    job = Job(id="job-2", source_path=str(source), category="미분류", processing_mode="asr", tracks=None)

    class BrokenEngine(FakeEngine):
        def transcribe(self, request, *, progress_callback=None):
            raise RuntimeError("model crashed")

    monkeypatch.setattr("transcribe_inbox.worker.engine_for_mode", lambda mode: BrokenEngine())
    monkeypatch.setattr(
        "transcribe_inbox.worker.normalize_to_wav",
        lambda path, **kwargs: tmp_path / "normalized.wav",
    )
    (tmp_path / "normalized.wav").write_bytes(b"wav")
    monkeypatch.setattr("transcribe_inbox.worker.JobMonitor", FakeJobMonitor)

    marks = {"failed": None}
    monkeypatch.setattr(
        "transcribe_inbox.worker.mark_failed",
        lambda conn, job_id, **kwargs: marks.__setitem__("failed", (job_id, kwargs)),
    )
    notified = []
    monkeypatch.setattr("transcribe_inbox.worker.notify_failed", lambda *a: notified.append(a))

    process_one_job(conn=None, job=job, staging_root=tmp_path / "staging")

    assert marks["failed"] is not None
    assert "model crashed" in marks["failed"][1]["error_message"]
    assert notified[0][:2] == ("미분류", "x.m4a")


def test_process_one_job_cleans_up_staging_dir_when_publish_fails(tmp_path, monkeypatch):
    source = tmp_path / "inbox" / "x.m4a"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"audio")
    job = Job(id="job-4", source_path=str(source), category="미분류", processing_mode="asr", tracks=None)

    monkeypatch.setattr("transcribe_inbox.worker.engine_for_mode", lambda mode: FakeEngine())
    monkeypatch.setattr(
        "transcribe_inbox.worker.normalize_to_wav",
        lambda path, **kwargs: tmp_path / "normalized.wav",
    )
    (tmp_path / "normalized.wav").write_bytes(b"wav")
    monkeypatch.setattr("transcribe_inbox.worker.JobMonitor", FakeJobMonitor)
    monkeypatch.setattr(
        "transcribe_inbox.worker.publish_atomically",
        lambda staging_dir, final_dir: (_ for _ in ()).throw(OSError("disk full")),
    )
    monkeypatch.setattr("transcribe_inbox.worker.mark_failed", lambda *a, **kw: None)
    monkeypatch.setattr("transcribe_inbox.worker.notify_failed", lambda *a: None)

    staging_root = tmp_path / "staging"
    process_one_job(conn=None, job=job, staging_root=staging_root)

    assert list(staging_root.iterdir()) == []  # no leftover partial staging directories


def test_process_one_job_handles_asr_multitrack_session(tmp_path, monkeypatch):
    session = tmp_path / "inbox" / "캡스톤" / "asr-multitrack" / "2026-09-08"
    session.mkdir(parents=True)
    track_a = session / "백지훈.m4a"
    track_b = session / "홍길동.m4a"
    track_a.write_bytes(b"a")
    track_b.write_bytes(b"b")
    job = Job(
        id="job-3", source_path=str(session), category="캡스톤", processing_mode="asr-multitrack",
        tracks=[
            {"path": str(track_a), "speaker_label": "백지훈", "offset_seconds": 0.0},
            {"path": str(track_b), "speaker_label": "홍길동", "offset_seconds": 0.0},
        ],
    )

    monkeypatch.setattr("transcribe_inbox.worker.engine_for_mode", lambda mode: FakeEngine())
    monkeypatch.setattr(
        "transcribe_inbox.worker.normalize_to_wav",
        lambda path, **kwargs: tmp_path / f"normalized-{Path(path).stem}.wav",
    )
    for track in (track_a, track_b):
        (tmp_path / f"normalized-{track.stem}.wav").write_bytes(b"wav")
    output_root = tmp_path / "Transcripts"
    monkeypatch.setattr(
        "transcribe_inbox.worker.output_dir_for", lambda category, label: output_root / category / label,
    )
    monkeypatch.setattr("transcribe_inbox.worker.notify_completed", lambda *a: None)
    monkeypatch.setattr("transcribe_inbox.worker.archive_source", lambda *a, **kw: tmp_path / "archived")
    monkeypatch.setattr("transcribe_inbox.worker.JobMonitor", FakeJobMonitor)

    marks = {"completed": None}
    monkeypatch.setattr(
        "transcribe_inbox.worker.mark_completed",
        lambda conn, job_id, **kwargs: marks.__setitem__("completed", (job_id, kwargs)),
    )

    process_one_job(conn=None, job=job, staging_root=tmp_path / "staging")

    assert marks["completed"] is not None
    assert marks["completed"][1]["metrics"]["trackCount"] == 2
    published_json = output_root / "캡스톤" / "2026-09-08" / "transcript.json"
    assert published_json.exists()
    speakers = {seg["speaker"] for seg in json.loads(published_json.read_text())["segments"]}
    assert speakers == {"백지훈", "홍길동"}


def test_process_one_job_keeps_completed_status_when_archive_fails(tmp_path, monkeypatch):
    """Controller-required regression test: mark_completed() has already
    committed COMPLETED status by the time archive_source() runs. If
    archive_source() raises (e.g. a disk error moving the source file), that
    must NOT flip the job back to FAILED -- mark_failed's SQL has no
    WHERE-status guard, so it would silently overwrite an already-successful
    completion. The transcript is already published and usable; the source
    stays in the inbox with status=COMPLETED so run_startup_reconciliation's
    self-heal (find_completed_jobs_with_source_still_present) can retry the
    archive move on the next daemon restart."""
    source = tmp_path / "inbox" / "컴퓨터네트워크" / "2주차.m4a"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"audio")
    job = Job(id="job-5", source_path=str(source), category="컴퓨터네트워크", processing_mode="asr", tracks=None)

    monkeypatch.setattr("transcribe_inbox.worker.engine_for_mode", lambda mode: FakeEngine())
    monkeypatch.setattr(
        "transcribe_inbox.worker.normalize_to_wav",
        lambda path, **kwargs: tmp_path / "normalized.wav",
    )
    (tmp_path / "normalized.wav").write_bytes(b"wav")
    output_root = tmp_path / "Transcripts"
    monkeypatch.setattr(
        "transcribe_inbox.worker.output_dir_for", lambda category, label: output_root / category / label,
    )
    monkeypatch.setattr("transcribe_inbox.worker.JobMonitor", FakeJobMonitor)

    marks = {"completed": None, "failed": None}
    monkeypatch.setattr(
        "transcribe_inbox.worker.mark_completed",
        lambda conn, job_id, **kwargs: marks.__setitem__("completed", (job_id, kwargs)),
    )
    monkeypatch.setattr(
        "transcribe_inbox.worker.mark_failed",
        lambda conn, job_id, **kwargs: marks.__setitem__("failed", (job_id, kwargs)),
    )

    def _raise_archive(*a, **kw):
        raise OSError("disk full")

    monkeypatch.setattr("transcribe_inbox.worker.archive_source", _raise_archive)
    notified_failed = []
    notified_completed = []
    monkeypatch.setattr("transcribe_inbox.worker.notify_failed", lambda *a: notified_failed.append(a))
    monkeypatch.setattr("transcribe_inbox.worker.notify_completed", lambda *a: notified_completed.append(a))

    # Must not raise -- the exception from archive_source is caught and
    # logged, not propagated.
    process_one_job(conn=None, job=job, staging_root=tmp_path / "staging")

    assert marks["completed"] is not None
    assert marks["failed"] is None
    assert notified_failed == []
