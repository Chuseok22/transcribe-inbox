from __future__ import annotations
import json
import logging
import subprocess
import tempfile
from dataclasses import replace
from pathlib import Path

from transcribe_inbox.engines.base import ProgressCallback, TranscriptionEngine, TranscriptionRequest
from transcribe_inbox.preprocess.ffmpeg import wav_duration_seconds
from transcribe_inbox.preprocess.wav_slice import extract_wav_span
from transcribe_inbox.transcript.repetition import find_repetition_span
from transcribe_inbox.transcript.schema import SCHEMA_VERSION, Segment, TranscriptDocument

logger = logging.getLogger(__name__)

PIPELINE_VERSION = "0.1.0"
MAX_REPETITION_RETRIES = 2
MAX_RETRY_SPAN_SECONDS = 180.0
REPETITION_PLACEHOLDER_PREFIX = "[⚠️ 반복 감지 - 확인 필요] "


class WhisperCppEngine(TranscriptionEngine):
    """Adapter for `whisper-cli --vad`. Trusts the CLI's own `vad_mapping_table`
    to keep segment offsets on the original absolute timeline (spec §9-2).
    Applies `-mc 0` on every call to stop repetition loops from propagating
    across decode windows, and detects/retries any repetition loop that still
    occurs within a single window (spec:
    docs/superpowers/specs/2026-09-14-whisper-repetition-loop-mitigation-design.md)."""

    def __init__(self, binary_path: str, vad_model_path: str, model_path: str, engine_version: str):
        self._binary_path = binary_path
        self._vad_model_path = vad_model_path
        self._model_path = model_path
        self._engine_version = engine_version
        self._current_pid: int | None = None

    @property
    def name(self) -> str:
        return "whisper.cpp"

    @property
    def version(self) -> str:
        return self._engine_version

    def monitoring_pid(self) -> int | None:
        return self._current_pid

    def transcribe(
        self,
        request: TranscriptionRequest,
        *,
        progress_callback: ProgressCallback | None = None,
    ) -> TranscriptDocument:
        extra_args = ["-mc", "0"]
        if request.language:
            extra_args += ["-l", request.language]

        raw = self._run_whisper_cli(request.audio_path, extra_args)
        doc = self._to_transcript_document(raw, request)
        return self._resolve_repetitions(doc, request)

    def _run_whisper_cli(self, audio_path: Path, extra_args: list[str]) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            output_prefix = Path(tmp) / "result"
            args = [
                self._binary_path,
                "--vad",
                "--vad-model", self._vad_model_path,
                "-m", self._model_path,
                "-oj",
                "-of", str(output_prefix),
                "-f", str(audio_path),
                *extra_args,
            ]

            process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self._current_pid = process.pid
            try:
                _, stderr = process.communicate()
            finally:
                self._current_pid = None

            if process.returncode != 0:
                raise RuntimeError(
                    f"whisper-cli exited {process.returncode}: {stderr.decode(errors='replace')}"
                )

            # whisper.cpp's own JSON writer occasionally splits a single
            # multi-byte CJK/Hangul character's tokens across two segments,
            # producing invalid UTF-8 in its own output (upstream bug --
            # ggml-org/whisper.cpp#1798). read_text()'s strict decode turns
            # that one bad character into a hard failure for the whole
            # transcription; decoding leniently instead just swaps the
            # broken character for U+FFFD and keeps everything else intact.
            raw_bytes = output_prefix.with_suffix(".json").read_bytes()
            return json.loads(raw_bytes.decode("utf-8", errors="replace"))

    def _to_transcript_document(self, raw: dict, request: TranscriptionRequest) -> TranscriptDocument:
        return TranscriptDocument(
            schema_version=SCHEMA_VERSION,
            pipeline_version=PIPELINE_VERSION,
            engine=self.name,
            engine_version=self.version,
            model=Path(self._model_path).stem,
            language=raw.get("result", {}).get("language") or request.language or "ko",
            source_filename=request.source_filename,
            # Measured from the WAV header, not segments[-1].end -- VAD
            # trims trailing silence, which would understate RTF (Task 7).
            audio_duration_seconds=wav_duration_seconds(request.audio_path),
            segments=self._segments_from_raw(raw),
        )

    @staticmethod
    def _segments_from_raw(raw: dict, time_offset: float = 0.0) -> list[Segment]:
        return [
            Segment(
                start=time_offset + entry["offsets"]["from"] / 1000.0,
                end=time_offset + entry["offsets"]["to"] / 1000.0,
                text=entry["text"].strip(),
            )
            for entry in raw.get("transcription", [])
        ]

    def _resolve_repetitions(self, doc: TranscriptDocument, request: TranscriptionRequest) -> TranscriptDocument:
        segments = list(doc.segments)
        search_offset = 0
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            while True:
                span = find_repetition_span(segments[search_offset:])
                if span is None:
                    break
                start_idx = search_offset + span[0]
                end_idx = search_offset + span[1]
                fixed = self._retry_span(segments[start_idx:end_idx + 1], request, tmp_path)
                segments = segments[:start_idx] + fixed + segments[end_idx + 1:]
                # Always advances past the just-replaced span, so the search
                # space strictly shrinks every iteration and this loop is
                # guaranteed to terminate regardless of retry outcome.
                search_offset = start_idx + len(fixed)
        return replace(doc, segments=segments)

    def _retry_span(
        self, span_segments: list[Segment], request: TranscriptionRequest, tmp_path: Path,
    ) -> list[Segment]:
        span_start = span_segments[0].start
        span_end = span_segments[-1].end

        placeholder = [Segment(
            start=span_start,
            end=span_end,
            text=f"{REPETITION_PLACEHOLDER_PREFIX}{span_segments[0].text}",
        )]

        logger.info(
            "Repetition span detected: %.1fs-%.1fs (%d segments)",
            span_start, span_end, len(span_segments),
        )

        if span_end - span_start > MAX_RETRY_SPAN_SECONDS:
            logger.warning(
                "Repetition span %.1fs-%.1fs exceeds %.0fs retry cap -- collapsing to placeholder "
                "without retrying (re-decoding would cost more wall-clock than it's likely to fix)",
                span_start, span_end, MAX_RETRY_SPAN_SECONDS,
            )
            return placeholder

        sub_wav = tmp_path / "retry.wav"
        absolute_offset = extract_wav_span(request.audio_path, span_start, span_end, sub_wav)

        # Attempt 1: re-decode the isolated (padded) span as-is -- the shifted
        # window boundary alone often breaks the loop. Attempt 2: also raise
        # the entropy-fallback threshold and force a non-zero start
        # temperature, so whisper-cli's own fallback ladder actually engages.
        perturbations: list[list[str]] = [[], ["-et", "2.6", "-tp", "0.5"]]
        for attempt_num, attempt_args in enumerate(perturbations[:MAX_REPETITION_RETRIES], start=1):
            extra_args = ["-mc", "0", *attempt_args]
            if request.language:
                extra_args += ["-l", request.language]

            try:
                raw = self._run_whisper_cli(sub_wav, extra_args)
            except Exception:
                # A retry decode itself failing (bad audio, whisper-cli crash) must
                # not take down an otherwise-successful transcription -- treat it
                # exactly like a still-repeating attempt and keep going.
                logger.warning(
                    "Repetition retry attempt %d/%d failed to decode for span %.1fs-%.1fs",
                    attempt_num, MAX_REPETITION_RETRIES, span_start, span_end, exc_info=True,
                )
                continue

            retried_segments = self._segments_from_raw(raw, time_offset=absolute_offset)

            # An empty result (e.g. the padded span decoded to silence) is a
            # failed attempt, not "no repetition" -- otherwise the span's
            # content would be silently dropped instead of falling through
            # to the placeholder below.
            if retried_segments and find_repetition_span(retried_segments) is None:
                logger.info(
                    "Repetition retry attempt %d/%d resolved span %.1fs-%.1fs",
                    attempt_num, MAX_REPETITION_RETRIES, span_start, span_end,
                )
                return retried_segments

            logger.info(
                "Repetition retry attempt %d/%d still looping for span %.1fs-%.1fs",
                attempt_num, MAX_REPETITION_RETRIES, span_start, span_end,
            )

        logger.warning(
            "Repetition span %.1fs-%.1fs unresolved after %d attempts -- collapsing to placeholder",
            span_start, span_end, MAX_REPETITION_RETRIES,
        )
        return placeholder
