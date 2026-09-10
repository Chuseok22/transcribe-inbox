import json
from pathlib import Path
from transcribe_inbox.transcript.schema import TranscriptDocument, Segment, SCHEMA_VERSION
from transcribe_inbox.publish import write_transcript_bundle, publish_atomically, archive_source


def _doc():
    return TranscriptDocument(
        schema_version=SCHEMA_VERSION, pipeline_version="0.1.0", engine="whisper.cpp",
        engine_version="1.0.0", model="ggml-large-v3", language="ko",
        source_filename="2주차.m4a", audio_duration_seconds=10.0,
        segments=[Segment(start=0.0, end=5.0, text="안녕하세요", speaker=None)],
    )


def test_write_transcript_bundle_creates_all_four_formats(tmp_path):
    staging = tmp_path / "staging"
    write_transcript_bundle(_doc(), staging)
    assert (staging / "transcript.json").exists()
    assert (staging / "transcript.md").exists()
    assert (staging / "transcript.txt").exists()
    assert (staging / "transcript.srt").exists()
    saved = json.loads((staging / "transcript.json").read_text())
    assert saved["schemaVersion"] == SCHEMA_VERSION


def test_publish_atomically_moves_staging_into_place(tmp_path):
    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "transcript.json").write_text("{}")
    final_dir = tmp_path / "Transcripts" / "컴퓨터네트워크" / "2주차"

    publish_atomically(staging, final_dir)

    assert not staging.exists()
    assert (final_dir / "transcript.json").exists()


def test_publish_atomically_replaces_an_existing_final_dir(tmp_path):
    final_dir = tmp_path / "Transcripts" / "컴퓨터네트워크" / "2주차"
    final_dir.mkdir(parents=True)
    (final_dir / "old.txt").write_text("stale")

    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "transcript.json").write_text("{}")

    publish_atomically(staging, final_dir)

    assert (final_dir / "transcript.json").exists()
    assert not (final_dir / "old.txt").exists()


def test_archive_source_mirrors_category_and_mode(tmp_path):
    inbox_file = tmp_path / "inbox" / "컴퓨터네트워크" / "2주차.m4a"
    inbox_file.parent.mkdir(parents=True)
    inbox_file.write_bytes(b"audio")
    archive_root = tmp_path / "archive"

    destination = archive_source(inbox_file, archive_root, category="컴퓨터네트워크", mode="asr")

    assert destination == archive_root / "컴퓨터네트워크" / "asr" / "2주차.m4a"
    assert destination.exists()
    assert not inbox_file.exists()


def test_archive_source_disambiguates_on_existing_destination(tmp_path):
    inbox_file = tmp_path / "inbox" / "x" / "a.m4a"
    inbox_file.parent.mkdir(parents=True)
    inbox_file.write_bytes(b"new")

    existing_dest = tmp_path / "archive" / "x" / "asr" / "a.m4a"
    existing_dest.parent.mkdir(parents=True)
    existing_dest.write_bytes(b"old")

    destination = archive_source(inbox_file, tmp_path / "archive", category="x", mode="asr")

    # The previously archived original must be left untouched...
    assert existing_dest.read_bytes() == b"old"
    # ...and the new file archived elsewhere, discoverable via the return value.
    assert destination != existing_dest
    assert destination.parent == existing_dest.parent
    assert destination.exists()
    assert destination.read_bytes() == b"new"
    assert not inbox_file.exists()
