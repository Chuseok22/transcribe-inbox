from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from transcribe_inbox.transcript.schema import TranscriptDocument

ProgressCallback = Callable[[float, str], None]


@dataclass(frozen=True)
class TranscriptionRequest:
    audio_path: Path
    language: str | None
    alignment_enabled: bool
    diarization_enabled: bool
    source_filename: str


class TranscriptionEngine(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def version(self) -> str: ...

    @abstractmethod
    def transcribe(
        self,
        request: TranscriptionRequest,
        *,
        progress_callback: ProgressCallback | None = None,
    ) -> TranscriptDocument: ...

    @abstractmethod
    def monitoring_pid(self) -> int | None:
        """PID of the process doing the heavy lifting for footprint sampling
        (spec §9-5) — the whisper-cli child for WhisperCppEngine, this
        process itself for WhisperMlxEngine. None when idle."""
        ...
