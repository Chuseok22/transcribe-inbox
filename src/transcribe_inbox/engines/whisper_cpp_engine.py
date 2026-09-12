from __future__ import annotations
import json
import subprocess
import tempfile
from pathlib import Path

from transcribe_inbox.engines.base import ProgressCallback, TranscriptionEngine, TranscriptionRequest
from transcribe_inbox.preprocess.ffmpeg import wav_duration_seconds
from transcribe_inbox.transcript.schema import SCHEMA_VERSION, Segment, TranscriptDocument

PIPELINE_VERSION = "0.1.0"


class WhisperCppEngine(TranscriptionEngine):
    """Adapter for `whisper-cli --vad`. Trusts the CLI's own `vad_mapping_table`
    to keep segment offsets on the original absolute timeline (spec §9-2)."""

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
        with tempfile.TemporaryDirectory() as tmp:
            output_prefix = Path(tmp) / "result"
            args = [
                self._binary_path,
                "--vad",
                "--vad-model", self._vad_model_path,
                "-m", self._model_path,
                "-oj",
                "-of", str(output_prefix),
                "-f", str(request.audio_path),
            ]
            if request.language:
                args += ["-l", request.language]

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

            raw = json.loads(output_prefix.with_suffix(".json").read_text())

        return self._to_transcript_document(raw, request)

    def _to_transcript_document(self, raw: dict, request: TranscriptionRequest) -> TranscriptDocument:
        segments = [
            Segment(
                start=entry["offsets"]["from"] / 1000.0,
                end=entry["offsets"]["to"] / 1000.0,
                text=entry["text"].strip(),
            )
            for entry in raw.get("transcription", [])
        ]
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
            segments=segments,
        )
