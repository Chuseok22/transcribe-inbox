from __future__ import annotations
from difflib import SequenceMatcher

from transcribe_inbox.transcript.schema import Segment

MIN_REPEAT_RUN = 3
SIMILARITY_THRESHOLD = 0.9
MIN_REPEAT_TEXT_LENGTH = 5


def find_repetition_span(segments: list[Segment]) -> tuple[int, int] | None:
    """Returns the (start_index, end_index) -- both 0-based, inclusive -- of
    the first maximal run of MIN_REPEAT_RUN or more consecutive segments
    whose text is near-identical to its immediate predecessor (SequenceMatcher
    ratio >= SIMILARITY_THRESHOLD), skipping any such run whose repeated text
    is shorter than MIN_REPEAT_TEXT_LENGTH (short acknowledgements like "네"
    repeating 3+ times is normal Q&A, not a hallucination loop). Returns None
    if no qualifying run exists."""
    if len(segments) < MIN_REPEAT_RUN:
        return None

    run_start = 0
    for i in range(1, len(segments)):
        similarity = SequenceMatcher(None, segments[i - 1].text, segments[i].text).ratio()
        if similarity < SIMILARITY_THRESHOLD:
            span = _qualifying_span(segments, run_start, i - 1)
            if span is not None:
                return span
            run_start = i

    return _qualifying_span(segments, run_start, len(segments) - 1)


def _qualifying_span(segments: list[Segment], start: int, end: int) -> tuple[int, int] | None:
    if end - start + 1 < MIN_REPEAT_RUN:
        return None
    if len(segments[start].text) < MIN_REPEAT_TEXT_LENGTH:
        return None
    return (start, end)
