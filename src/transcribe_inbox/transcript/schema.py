from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class Word:
    text: str
    start: float
    end: float
    speaker: str | None = None


@dataclass(frozen=True)
class Segment:
    start: float
    end: float
    text: str
    speaker: str | None = None


@dataclass(frozen=True)
class TranscriptDocument:
    schema_version: int
    pipeline_version: str
    engine: str
    engine_version: str
    model: str
    language: str
    source_filename: str
    audio_duration_seconds: float
    segments: list[Segment]
    words: list[Word] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "pipelineVersion": self.pipeline_version,
            "engine": self.engine,
            "engineVersion": self.engine_version,
            "model": self.model,
            "language": self.language,
            "sourceFilename": self.source_filename,
            "audioDurationSeconds": self.audio_duration_seconds,
            "segments": [asdict(s) for s in self.segments],
            "words": [asdict(w) for w in self.words],
        }
