from __future__ import annotations
import importlib.metadata
import logging
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from transcribe_inbox.config import ARCHIVE_ROOT, output_dir_for
from transcribe_inbox.db.jobs import mark_completed, mark_failed
from transcribe_inbox.engines.base import TranscriptionEngine, TranscriptionRequest
from transcribe_inbox.engines.whisper_cpp_engine import WhisperCppEngine
from transcribe_inbox.engines.whisper_mlx_engine import WhisperMlxEngine
from transcribe_inbox.notify import notify_completed, notify_failed, notify_started
from transcribe_inbox.observability.job_monitor import JobMonitor
from transcribe_inbox.observability.stall import Heartbeat
from transcribe_inbox.preprocess.ffmpeg import normalize_to_wav
from transcribe_inbox.publish import archive_source, publish_atomically, write_transcript_bundle
from transcribe_inbox.transcript.schema import SCHEMA_VERSION, Segment, TranscriptDocument

logger = logging.getLogger(__name__)

DIARIZE_MODE = "diarize"
MULTITRACK_MODE = "asr-multitrack"
PIPELINE_VERSION = "0.1.0"
STALL_WARNING_SECONDS = 1800.0
FOOTPRINT_SAMPLE_INTERVAL_SECONDS = 30.0


def _whispermlx_version() -> str:
    # Auto-detected from the installed package is more trustworthy than a
    # possibly-stale env var, so prefer it whenever it succeeds; the env var
    # (default "unknown") is only the fallback for the should-never-happen
    # case where metadata lookup fails for a hard dependency.
    try:
        return importlib.metadata.version("whispermlx")
    except Exception:
        return os.environ.get("WHISPERMLX_VERSION", "unknown")


def _whisper_cpp_version(binary_path: str) -> str:
    # Same precedence as _whispermlx_version: prefer the binary's own
    # reported version over a possibly-stale env var. whisper-cli's
    # `--version` behavior is unverified on this machine (binary absent), so
    # this must fail safe on absolutely anything -- missing binary, non-zero
    # exit, timeout, or unexpected output all fall back to the env var.
    try:
        result = subprocess.run(
            [binary_path, "--version"], capture_output=True, text=True, timeout=5, check=True,
        )
        version = result.stdout.strip()
        if version:
            return version
    except Exception:
        pass
    return os.environ.get("WHISPER_CPP_VERSION", "unknown")


def engine_for_mode(mode: str) -> TranscriptionEngine:
    if mode == DIARIZE_MODE:
        return WhisperMlxEngine(
            model_path=os.environ["WHISPER_MLX_MODEL_PATH"],
            engine_version=_whispermlx_version(),
            hf_token=os.environ["HUGGINGFACE_TOKEN"],
        )
    binary_path = os.environ.get("WHISPER_CLI_BINARY", "/opt/homebrew/bin/whisper-cli")
    return WhisperCppEngine(
        binary_path=binary_path,
        vad_model_path=os.environ["WHISPER_VAD_MODEL_PATH"],
        model_path=os.environ["WHISPER_ASR_MODEL_PATH"],
        engine_version=_whisper_cpp_version(binary_path),
    )


def process_one_job(conn, job, staging_root: Path) -> None:
    staging_root.mkdir(parents=True, exist_ok=True)
    source_path = Path(job.source_path)
    staging_dir: Path | None = None

    try:
        notify_started(job.category, source_path.name)
    except Exception:
        logger.exception("Job %s: notify_started failed", job.id)

    try:
        engine = engine_for_mode(job.processing_mode)

        if job.processing_mode == MULTITRACK_MODE:
            doc, metrics = _transcribe_multitrack_session(job, engine)
        else:
            doc, metrics = _transcribe_single_file(job, source_path, engine)

        staging_dir = Path(tempfile.mkdtemp(dir=staging_root))
        write_transcript_bundle(doc, staging_dir)
        # asr-multitrack's source_path is the session *directory* -- use its
        # full name (spec §3: "출력 디렉터리명 = 세션 폴더명 그대로"), not
        # .stem, which would silently truncate a folder name containing a
        # dot. Single-file modes keep .stem to drop the audio extension.
        output_label = source_path.name if job.processing_mode == MULTITRACK_MODE else source_path.stem
        final_dir = output_dir_for(job.category, output_label)
        publish_atomically(staging_dir, final_dir)
        staging_dir = None  # ownership moved to final_dir; nothing left to clean up

        mark_completed(
            conn, job.id, engine=doc.engine, engine_version=doc.engine_version,
            model_name=doc.model, metrics=metrics,
        )
    except Exception as exc:
        logger.exception("Job %s failed", job.id)
        mark_failed(conn, job.id, error_message=str(exc))
        notify_failed(job.category, source_path.name, str(exc))
        return
    finally:
        if staging_dir is not None and staging_dir.exists():
            shutil.rmtree(staging_dir)

    # The job is already COMPLETED at this point -- a failure in archiving
    # the source or sending a notification must NOT flip the status back to
    # FAILED (Task 11's mark_failed has no WHERE-status guard, so it would
    # silently overwrite an already-successful completion). The transcript
    # is already published and usable; leaving the source in the inbox with
    # status=COMPLETED lets run_startup_reconciliation's self-heal
    # (find_completed_jobs_with_source_still_present, Task 11/14) retry the
    # archive move on the next daemon restart.
    try:
        notify_completed(job.category, source_path.name)
        archive_source(source_path, ARCHIVE_ROOT, job.category, job.processing_mode)
    except Exception:
        logger.exception("Job %s completed but post-completion archive/notify failed", job.id)


def _run_with_monitoring(engine: TranscriptionEngine, request: TranscriptionRequest) -> tuple[TranscriptDocument, dict]:
    """Wraps a single (blocking) `engine.transcribe()` call with a
    concurrently-running JobMonitor -- a footprint sample taken only after
    transcribe() returns could never see a peak during a 60-90 minute call."""
    heartbeat = Heartbeat(last_progress_at=time.time())
    monitor = JobMonitor(
        engine.monitoring_pid, heartbeat,
        sample_interval_seconds=FOOTPRINT_SAMPLE_INTERVAL_SECONDS,
        stall_warning_seconds=STALL_WARNING_SECONDS,
        on_stall_warning=lambda: logger.warning(
            "No transcription progress for %.0fs (stage=%s)", STALL_WARNING_SECONDS, heartbeat.current_stage,
        ),
    )
    monitor.start()
    started = time.monotonic()
    try:
        doc = engine.transcribe(request, progress_callback=heartbeat.update)
    finally:
        monitor.stop()
    elapsed = time.monotonic() - started

    metrics = {
        "audioDurationSeconds": doc.audio_duration_seconds,
        "processingDurationSeconds": elapsed,
        "realTimeFactor": (elapsed / doc.audio_duration_seconds) if doc.audio_duration_seconds else None,
        "processFootprintStartBytes": monitor.footprint_start_bytes,
        "processFootprintPeakBytes": monitor.footprint_peak_bytes,
        "processFootprintEndBytes": monitor.footprint_end_bytes,
        "minimumSystemAvailableMemoryBytes": monitor.minimum_available_memory_bytes,
        "swapOutDeltaBytes": monitor.swap_out_delta_bytes,
    }
    return doc, metrics


def _transcribe_single_file(job, source_path: Path, engine: TranscriptionEngine) -> tuple[TranscriptDocument, dict]:
    normalized_wav = normalize_to_wav(source_path)
    try:
        request = TranscriptionRequest(
            audio_path=normalized_wav,
            language="ko",
            alignment_enabled=(job.processing_mode == DIARIZE_MODE),
            diarization_enabled=(job.processing_mode == DIARIZE_MODE),
            source_filename=source_path.name,
        )
        return _run_with_monitoring(engine, request)
    finally:
        normalized_wav.unlink(missing_ok=True)


def _transcribe_multitrack_session(job, engine: TranscriptionEngine) -> tuple[TranscriptDocument, dict]:
    """Each track is a pre-separated single speaker's audio (spec §6) -- no
    alignment/diarization. Transcribe every track independently through the
    same engine, tag each resulting segment with that track's speaker
    label, shift by offset_seconds, and merge into one segment list sorted
    by start time. `metrics` here is an aggregate across all track calls,
    not a single JobMonitor run -- deliberately a different shape from
    `_transcribe_single_file`'s, since it is still observation-only jsonb."""
    all_segments: list[Segment] = []
    total_audio_seconds = 0.0
    total_elapsed_seconds = 0.0
    peak_footprint_bytes: int | None = None
    minimum_available_bytes: int | None = None
    model_name = "unknown"
    language = "ko"

    for track in job.tracks:
        track_path = Path(track["path"])
        speaker_label = track["speaker_label"]
        offset_seconds = track.get("offset_seconds", 0.0)

        normalized_wav = normalize_to_wav(track_path)
        try:
            request = TranscriptionRequest(
                audio_path=normalized_wav, language=language, alignment_enabled=False,
                diarization_enabled=False, source_filename=track_path.name,
            )
            doc, metrics = _run_with_monitoring(engine, request)
        finally:
            normalized_wav.unlink(missing_ok=True)

        model_name = doc.model
        total_audio_seconds = max(total_audio_seconds, doc.audio_duration_seconds + offset_seconds)
        total_elapsed_seconds += metrics["processingDurationSeconds"]
        if metrics["processFootprintPeakBytes"] is not None:
            peak_footprint_bytes = max(peak_footprint_bytes or 0, metrics["processFootprintPeakBytes"])
        if metrics["minimumSystemAvailableMemoryBytes"] is not None:
            if minimum_available_bytes is None or metrics["minimumSystemAvailableMemoryBytes"] < minimum_available_bytes:
                minimum_available_bytes = metrics["minimumSystemAvailableMemoryBytes"]

        for seg in doc.segments:
            all_segments.append(Segment(
                start=seg.start + offset_seconds, end=seg.end + offset_seconds,
                text=seg.text, speaker=speaker_label,
            ))

    all_segments.sort(key=lambda s: s.start)
    document = TranscriptDocument(
        schema_version=SCHEMA_VERSION,
        pipeline_version=PIPELINE_VERSION,
        engine=engine.name,
        engine_version=engine.version,
        model=model_name,
        language=language,
        source_filename=Path(job.source_path).name,
        audio_duration_seconds=total_audio_seconds,
        segments=all_segments,
    )
    metrics = {
        "audioDurationSeconds": total_audio_seconds,
        "processingDurationSeconds": total_elapsed_seconds,
        "realTimeFactor": (total_elapsed_seconds / total_audio_seconds) if total_audio_seconds else None,
        "processFootprintPeakBytes": peak_footprint_bytes,
        "minimumSystemAvailableMemoryBytes": minimum_available_bytes,
        "trackCount": len(job.tracks),
    }
    return document, metrics
