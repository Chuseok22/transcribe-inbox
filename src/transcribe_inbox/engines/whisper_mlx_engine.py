from __future__ import annotations
import os
from pathlib import Path

from transcribe_inbox.engines.base import ProgressCallback, TranscriptionEngine, TranscriptionRequest
from transcribe_inbox.preprocess.ffmpeg import wav_duration_seconds
from transcribe_inbox.transcript.resegment import speaker_aware_resegment
from transcribe_inbox.transcript.schema import SCHEMA_VERSION, TranscriptDocument, Word

PIPELINE_VERSION = "0.1.0"


class WhisperMlxEngine(TranscriptionEngine):
    """Adapter for whispermlx: MLX ASR -> wav2vec2 alignment (MPS) ->
    pyannote diarization (MPS) -> speaker-aware re-segmentation (spec §9-4)."""

    def __init__(self, model_path: str, engine_version: str, hf_token: str):
        self._model_path = model_path
        self._engine_version = engine_version
        self._hf_token = hf_token

    @property
    def name(self) -> str:
        return "whispermlx"

    @property
    def version(self) -> str:
        return self._engine_version

    def monitoring_pid(self) -> int | None:
        return os.getpid()

    def transcribe(
        self,
        request: TranscriptionRequest,
        *,
        progress_callback: ProgressCallback | None = None,
    ) -> TranscriptDocument:
        import whispermlx
        from whispermlx.diarize import DiarizationPipeline

        def report(stage):
            return (lambda pct: progress_callback(pct, stage)) if progress_callback else None

        # `device` here configures whispermlx's internal VAD torch model, not
        # MLX acceleration — ASR always runs on MLX regardless of this value,
        # and "mlx" is not a valid torch device string (verified against
        # KalebJS/whispermlx source).
        model = whispermlx.load_model(self._model_path, device="cpu")
        asr_result = model.transcribe(
            str(request.audio_path), language=request.language, progress_callback=report("TRANSCRIBING"),
        )

        align_model, align_metadata = whispermlx.load_align_model(
            language_code=asr_result["language"], device="mps",
        )
        aligned = whispermlx.align(
            asr_result["segments"], align_model, align_metadata, str(request.audio_path),
            device="mps", progress_callback=report("ALIGNING"),
        )

        diarize = DiarizationPipeline(token=self._hf_token, device="mps")
        diarization_df = diarize(str(request.audio_path), progress_callback=report("DIARIZING"))
        # DiarizationPipeline.__call__ returns a pandas.DataFrame directly —
        # there is no `.speaker_diarization` attribute to unwrap.
        result_with_speakers = whispermlx.assign_word_speakers(diarization_df, aligned)

        words = [
            Word(text=w["word"], start=w["start"], end=w["end"], speaker=w.get("speaker"))
            for seg in result_with_speakers["segments"]
            for w in seg.get("words", [])
        ]
        segments = speaker_aware_resegment(words)

        return TranscriptDocument(
            schema_version=SCHEMA_VERSION,
            pipeline_version=PIPELINE_VERSION,
            engine=self.name,
            engine_version=self.version,
            model=Path(self._model_path).stem,
            language=asr_result["language"],
            source_filename=request.source_filename,
            audio_duration_seconds=wav_duration_seconds(request.audio_path),
            segments=segments,
            words=words,
        )
