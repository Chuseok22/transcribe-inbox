from transcribe_inbox.transcript.schema import TranscriptDocument, Segment, Word, SCHEMA_VERSION

def test_to_dict_uses_camel_case_keys():
    doc = TranscriptDocument(
        schema_version=SCHEMA_VERSION,
        pipeline_version="0.1.0",
        engine="whisper.cpp",
        engine_version="1.0.0",
        model="ggml-large-v3",
        language="ko",
        source_filename="2주차.m4a",
        audio_duration_seconds=12.5,
        segments=[Segment(start=0.0, end=5.0, text="안녕하세요", speaker=None)],
        words=[Word(text="안녕하세요", start=0.0, end=5.0, speaker=None)],
    )
    result = doc.to_dict()
    assert result["schemaVersion"] == SCHEMA_VERSION
    assert result["pipelineVersion"] == "0.1.0"
    assert result["audioDurationSeconds"] == 12.5
    assert result["segments"][0]["text"] == "안녕하세요"
    assert result["words"][0]["start"] == 0.0

def test_words_default_to_empty_list():
    doc = TranscriptDocument(
        schema_version=SCHEMA_VERSION, pipeline_version="0.1.0", engine="whisper.cpp",
        engine_version="1.0.0", model="ggml-large-v3", language="ko",
        source_filename="x.m4a", audio_duration_seconds=1.0, segments=[],
    )
    assert doc.words == []
    assert doc.to_dict()["words"] == []
