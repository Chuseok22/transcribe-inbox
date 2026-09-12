from __future__ import annotations
import logging
import os
import wave
from pathlib import Path

import numpy as np

from transcribe_inbox.engines.base import ProgressCallback, TranscriptionEngine, TranscriptionRequest
from transcribe_inbox.preprocess.ffmpeg import wav_duration_seconds
from transcribe_inbox.transcript.resegment import speaker_aware_resegment
from transcribe_inbox.transcript.schema import SCHEMA_VERSION, TranscriptDocument, Word

PIPELINE_VERSION = "0.1.0"

logger = logging.getLogger(__name__)


def _read_wav_as_float32(wav_path: Path) -> np.ndarray:
    """Reads an already-normalized 16kHz mono 16-bit PCM WAV (normalize_to_wav
    guarantees this format upstream in worker.py) into a float32 array in
    [-1, 1]. Matches whispermlx's own `audio.load_audio` conversion exactly
    (`np.frombuffer(pcm_s16le, np.int16).astype(np.float32) / 32768.0`) so
    passing this array in place of a path produces sample-identical input."""
    with wave.open(str(wav_path), "rb") as f:
        raw = f.readframes(f.getnframes())
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


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

        # Read the audio once ourselves and pass the array (not a path
        # string) to every whispermlx call below. whispermlx's own
        # `audio.load_audio` shells out to a bare `ffmpeg` on PATH with no
        # absolute path -- under launchd (no PATH set), that raises
        # FileNotFoundError. Reading the already-normalized WAV here also
        # avoids decoding the same file three separate times.
        audio_array = _read_wav_as_float32(request.audio_path)

        # `device` here configures whispermlx's internal VAD torch model, not
        # MLX acceleration — ASR always runs on MLX regardless of this value,
        # and "mlx" is not a valid torch device string (verified against
        # KalebJS/whispermlx source).
        model = whispermlx.load_model(self._model_path, device="cpu")
        asr_result = model.transcribe(
            audio_array, language=request.language, progress_callback=report("TRANSCRIBING"),
        )

        aligned = self._align_with_mps_fallback(whispermlx, asr_result, audio_array, report)
        diarization_df = self._diarize_with_mps_fallback(DiarizationPipeline, audio_array, report)
        # DiarizationPipeline.__call__ returns a pandas.DataFrame directly —
        # there is no `.speaker_diarization` attribute to unwrap.
        result_with_speakers = whispermlx.assign_word_speakers(diarization_df, aligned)

        # `doc.words` (the raw word-level output) must only ever contain real
        # aligned words -- `all_words` is the separate chronological list
        # (real aligned words plus synthetic fallback words) fed into a
        # single `speaker_aware_resegment` call below to build `doc.segments`.
        words: list[Word] = []
        all_words: list[Word] = []
        for seg in result_with_speakers["segments"]:
            seg_words = seg.get("words") or []
            if seg_words:
                segment_words = [
                    Word(text=w["word"], start=w["start"], end=w["end"], speaker=w.get("speaker"))
                    for w in seg_words
                ]
                words.extend(segment_words)
                all_words.extend(segment_words)
            elif seg["text"].strip():
                # whispermlx's own alignment fallback (no alignable
                # characters, segment start past audio duration, or a failed
                # backtrack -- see whispermlx/alignment.py) leaves `words`
                # empty but keeps the segment-level start/end/text intact.
                # `assign_word_speakers` still assigns a segment-level
                # `speaker` in this case. A single synthetic Word built from
                # those fields keeps this stretch of the transcript instead
                # of silently dropping it, while still flowing through the
                # same resegmentation pass as everything else.
                all_words.append(Word(
                    text=seg["text"], start=seg["start"], end=seg["end"], speaker=seg.get("speaker"),
                ))
            # else: no word-level alignment AND empty/whitespace-only text --
            # a no-speech/noise VAD chunk. Contributes nothing to the
            # document; emitting it would leak a blank segment/line into
            # every output format, none of which filter empty text.

        # whispermlx emits segments in time order, but a synthetic word
        # interleaved out of order would break speaker_aware_resegment's
        # pause/speaker-change logic, which assumes chronological input --
        # sort defensively rather than assume.
        all_words.sort(key=lambda w: w.start)
        segments = speaker_aware_resegment(all_words)

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

    def _align_with_mps_fallback(self, whispermlx_module, asr_result, audio_array, report):
        try:
            align_model, align_metadata = whispermlx_module.load_align_model(
                language_code=asr_result["language"], device="mps",
            )
            return whispermlx_module.align(
                asr_result["segments"], align_model, align_metadata, audio_array,
                device="mps", progress_callback=report("ALIGNING"),
            )
        except Exception:
            logger.warning("whispermlx alignment failed on device=mps, falling back to cpu", exc_info=True)
            align_model, align_metadata = whispermlx_module.load_align_model(
                language_code=asr_result["language"], device="cpu",
            )
            return whispermlx_module.align(
                asr_result["segments"], align_model, align_metadata, audio_array,
                device="cpu", progress_callback=report("ALIGNING"),
            )

    def _diarize_with_mps_fallback(self, diarization_pipeline_cls, audio_array, report):
        try:
            diarize = diarization_pipeline_cls(token=self._hf_token, device="mps")
            return diarize(audio_array, progress_callback=report("DIARIZING"))
        except Exception:
            logger.warning("whispermlx diarization failed on device=mps, falling back to cpu", exc_info=True)
            diarize = diarization_pipeline_cls(token=self._hf_token, device="cpu")
            return diarize(audio_array, progress_callback=report("DIARIZING"))
