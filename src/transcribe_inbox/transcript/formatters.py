from __future__ import annotations
from transcribe_inbox.transcript.schema import TranscriptDocument


def to_markdown(doc: TranscriptDocument) -> str:
    lines = []
    for seg in doc.segments:
        prefix = f"{seg.speaker}: " if seg.speaker else ""
        lines.append(f"[{_format_hhmmss(seg.start)}] {prefix}{seg.text}")
    return "\n".join(lines) + "\n"


def to_plain_text(doc: TranscriptDocument) -> str:
    return "\n".join(seg.text for seg in doc.segments) + "\n"


def to_srt(doc: TranscriptDocument) -> str:
    blocks = []
    for index, seg in enumerate(doc.segments, start=1):
        prefix = f"{seg.speaker}: " if seg.speaker else ""
        blocks.append(
            f"{index}\n{_format_srt_timestamp(seg.start)} --> {_format_srt_timestamp(seg.end)}\n{prefix}{seg.text}\n"
        )
    # SRT blocks must be separated by a blank line -- "\n\n".join, not "\n".join,
    # or every block after the first fails to parse in most players.
    return "\n".join(blocks)


def _format_hhmmss(seconds: float) -> str:
    total = int(seconds)
    hh, remainder = divmod(total, 3600)
    mm, ss = divmod(remainder, 60)
    return f"{hh:02d}:{mm:02d}:{ss:02d}"


def _format_srt_timestamp(seconds: float) -> str:
    total_ms = int(round(seconds * 1000))
    hh, remainder = divmod(total_ms, 3_600_000)
    mm, remainder = divmod(remainder, 60_000)
    ss, ms = divmod(remainder, 1000)
    return f"{hh:02d}:{mm:02d}:{ss:02d},{ms:03d}"
