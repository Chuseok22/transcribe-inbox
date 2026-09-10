from __future__ import annotations
from transcribe_inbox.transcript.schema import Segment, Word

MAX_PAUSE_SECONDS = 2.0


def speaker_aware_resegment(words: list[Word]) -> list[Segment]:
    """A new segment starts whenever the speaker changes, or the pause since
    the previous word exceeds MAX_PAUSE_SECONDS (spec §6)."""
    if not words:
        return []

    segments: list[Segment] = []
    current: list[Word] = [words[0]]
    for word in words[1:]:
        previous = current[-1]
        speaker_changed = word.speaker != previous.speaker
        pause_too_long = (word.start - previous.end) > MAX_PAUSE_SECONDS
        if speaker_changed or pause_too_long:
            segments.append(_to_segment(current))
            current = [word]
        else:
            current.append(word)
    segments.append(_to_segment(current))
    return segments


def _to_segment(words: list[Word]) -> Segment:
    return Segment(
        start=words[0].start,
        end=words[-1].end,
        text=" ".join(w.text for w in words).strip(),
        speaker=words[0].speaker,
    )
