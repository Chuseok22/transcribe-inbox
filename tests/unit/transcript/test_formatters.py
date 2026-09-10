from transcribe_inbox.transcript.schema import TranscriptDocument, Segment, SCHEMA_VERSION
from transcribe_inbox.transcript.formatters import to_markdown, to_plain_text, to_srt

def _doc(segments):
    return TranscriptDocument(
        schema_version=SCHEMA_VERSION, pipeline_version="0.1.0", engine="whisper.cpp",
        engine_version="1.0.0", model="ggml-large-v3", language="ko",
        source_filename="x.m4a", audio_duration_seconds=70.0, segments=segments,
    )

def test_markdown_format_matches_spec_pattern():
    doc = _doc([Segment(start=65.0, end=70.0, text="시험에 나옵니다", speaker=None)])
    md = to_markdown(doc)
    assert md == "[00:01:05] 시험에 나옵니다\n"

def test_markdown_includes_speaker_when_present():
    doc = _doc([Segment(start=0.0, end=1.0, text="안녕하세요", speaker="SPEAKER_00")])
    md = to_markdown(doc)
    assert md == "[00:00:00] SPEAKER_00: 안녕하세요\n"

def test_plain_text_has_no_timestamps():
    doc = _doc([
        Segment(start=0.0, end=1.0, text="첫 문장", speaker=None),
        Segment(start=1.0, end=2.0, text="둘째 문장", speaker=None),
    ])
    assert to_plain_text(doc) == "첫 문장\n둘째 문장\n"

def test_srt_format_has_index_and_comma_millis():
    doc = _doc([Segment(start=1.5, end=3.25, text="테스트", speaker=None)])
    srt = to_srt(doc)
    assert srt == "1\n00:00:01,500 --> 00:00:03,250\n테스트\n"

def test_srt_blocks_are_separated_by_a_blank_line():
    # SRT requires a blank line between blocks -- without it, most players
    # fail to parse every block after the first. A single-segment fixture
    # can't catch this (there's nothing to separate), so this needs two.
    doc = _doc([
        Segment(start=0.0, end=1.0, text="첫", speaker=None),
        Segment(start=1.0, end=2.0, text="둘째", speaker=None),
    ])
    srt = to_srt(doc)
    assert srt == (
        "1\n00:00:00,000 --> 00:00:01,000\n첫\n"
        "\n"
        "2\n00:00:01,000 --> 00:00:02,000\n둘째\n"
    )
