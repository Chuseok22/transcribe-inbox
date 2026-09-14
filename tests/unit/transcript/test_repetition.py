from transcribe_inbox.transcript.repetition import find_repetition_span
from transcribe_inbox.transcript.schema import Segment


def _segment(start: float, text: str) -> Segment:
    return Segment(start=start, end=start + 1.0, text=text)


def test_returns_none_for_empty_list():
    assert find_repetition_span([]) is None


def test_returns_none_when_fewer_than_minimum_run_length():
    segments = [_segment(0.0, "같은 말"), _segment(1.0, "같은 말")]
    assert find_repetition_span(segments) is None


def test_returns_none_when_all_segments_are_distinct():
    segments = [
        _segment(0.0, "오늘 날씨가 좋네요"),
        _segment(2.0, "점심 메뉴는 무엇인가요"),
        _segment(4.0, "회의는 세시에 시작합니다"),
        _segment(6.0, "이번 주 안에 끝내야 해요"),
    ]
    assert find_repetition_span(segments) is None


def test_detects_exactly_three_identical_consecutive_segments():
    segments = [
        _segment(0.0, "오늘 날씨가 좋네요"),
        _segment(2.0, "rfc에 디파인이 되어있는"),
        _segment(4.0, "rfc에 디파인이 되어있는"),
        _segment(6.0, "rfc에 디파인이 되어있는"),
    ]
    assert find_repetition_span(segments) == (1, 3)


def test_extends_span_to_cover_the_full_repetition_run_not_just_the_first_three():
    segments = [
        _segment(0.0, "rfc에 디파인이 되어있는"),
        _segment(2.0, "rfc에 디파인이 되어있는"),
        _segment(4.0, "rfc에 디파인이 되어있는"),
        _segment(6.0, "rfc에 디파인이 되어있는"),
        _segment(8.0, "rfc에 디파인이 되어있는"),
    ]
    assert find_repetition_span(segments) == (0, 4)


def test_detects_near_identical_segments_above_similarity_threshold():
    segments = [
        _segment(0.0, "rfc에 디파인이 되어있는"),
        _segment(2.0, "rfc에 디파인이 되어있는"),
        _segment(4.0, "rfc에 디파인이 되어있는요"),
    ]
    assert find_repetition_span(segments) == (0, 2)


def test_ignores_a_run_shorter_than_the_minimum():
    segments = [
        _segment(0.0, "같은 말"),
        _segment(2.0, "같은 말"),
        _segment(4.0, "완전히 다른 이야기 하나"),
        _segment(6.0, "또 다른 별개의 이야기"),
    ]
    assert find_repetition_span(segments) is None


def test_finds_repetition_run_starting_mid_list():
    segments = [
        _segment(0.0, "오늘 날씨가 좋네요"),
        _segment(2.0, "점심 메뉴는 무엇인가요"),
        _segment(4.0, "rfc에 디파인이 되어있는"),
        _segment(6.0, "rfc에 디파인이 되어있는"),
        _segment(8.0, "rfc에 디파인이 되어있는"),
        _segment(10.0, "rfc에 디파인이 되어있는"),
    ]
    assert find_repetition_span(segments) == (2, 5)


def test_returns_first_run_when_multiple_runs_exist():
    segments = [
        _segment(0.0, "가나다라마바"),
        _segment(1.0, "가나다라마바"),
        _segment(2.0, "가나다라마바"),
        _segment(3.0, "완전히 다른 내용의 문장"),
        _segment(4.0, "자차카타파하"),
        _segment(5.0, "자차카타파하"),
        _segment(6.0, "자차카타파하"),
    ]
    assert find_repetition_span(segments) == (0, 2)


def test_ignores_short_repeated_acknowledgements():
    """Real short back-and-forth ("네", "그렇죠") is common in Korean lecture
    Q&A and must not be folded into a repetition placeholder."""
    segments = [
        _segment(0.0, "네"),
        _segment(1.0, "네"),
        _segment(2.0, "네"),
        _segment(3.0, "그렇죠"),
    ]
    assert find_repetition_span(segments) is None


def test_finds_long_repetition_even_when_a_short_repeated_run_precedes_it():
    segments = [
        _segment(0.0, "네"),
        _segment(1.0, "네"),
        _segment(2.0, "네"),
        _segment(3.0, "rfc에 디파인이 되어있는"),
        _segment(5.0, "rfc에 디파인이 되어있는"),
        _segment(7.0, "rfc에 디파인이 되어있는"),
    ]
    assert find_repetition_span(segments) == (3, 5)
