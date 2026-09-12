from transcribe_inbox.transcript.schema import Word
from transcribe_inbox.transcript.resegment import speaker_aware_resegment


def test_empty_words_gives_empty_segments():
    assert speaker_aware_resegment([]) == []


def test_same_speaker_short_pause_merges_into_one_segment():
    words = [
        Word(text="안녕", start=0.0, end=0.5, speaker="SPEAKER_00"),
        Word(text="하세요", start=1.5, end=2.0, speaker="SPEAKER_00"),  # 1s pause
    ]
    segments = speaker_aware_resegment(words)
    assert len(segments) == 1
    assert segments[0].text == "안녕 하세요"
    assert segments[0].start == 0.0 and segments[0].end == 2.0


def test_speaker_change_always_starts_new_segment_even_with_no_pause():
    words = [
        Word(text="안녕하세요", start=0.0, end=1.0, speaker="SPEAKER_00"),
        Word(text="반갑습니다", start=1.0, end=2.0, speaker="SPEAKER_01"),
    ]
    segments = speaker_aware_resegment(words)
    assert len(segments) == 2
    assert segments[0].speaker == "SPEAKER_00"
    assert segments[1].speaker == "SPEAKER_01"


def test_pause_exactly_at_max_threshold_merges_not_splits():
    words = [
        Word(text="첫문장", start=0.0, end=1.0, speaker="SPEAKER_00"),
        Word(text="둘째문장", start=3.0, end=4.0, speaker="SPEAKER_00"),  # exactly 2.0s pause
    ]
    segments = speaker_aware_resegment(words)
    assert len(segments) == 1


def test_long_pause_with_same_speaker_starts_new_segment():
    words = [
        Word(text="첫문장", start=0.0, end=1.0, speaker="SPEAKER_00"),
        Word(text="둘째문장", start=4.0, end=5.0, speaker="SPEAKER_00"),  # 3s pause > 2s max
    ]
    segments = speaker_aware_resegment(words)
    assert len(segments) == 2


def test_three_speaker_turns():
    words = [
        Word(text="안녕하세요", start=0.0, end=1.0, speaker="SPEAKER_00"),
        Word(text="반갑습니다", start=1.0, end=2.0, speaker="SPEAKER_01"),
        Word(text="오늘", start=2.0, end=2.5, speaker="SPEAKER_00"),
        Word(text="회의는", start=2.5, end=3.0, speaker="SPEAKER_00"),
    ]
    segments = speaker_aware_resegment(words)
    assert [s.speaker for s in segments] == ["SPEAKER_00", "SPEAKER_01", "SPEAKER_00"]
    assert segments[2].text == "오늘 회의는"
