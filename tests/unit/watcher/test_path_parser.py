from pathlib import Path
import pytest
from transcribe_inbox.watcher.path_parser import parse_inbox_path, VALID_MODES, DEFAULT_MODE

INBOX = Path("/home/user/Transcribe/inbox")

def test_no_category_defaults_to_uncategorized():
    result = parse_inbox_path(INBOX, INBOX / "2주차.m4a")
    assert result.category == "미분류"
    assert result.mode == DEFAULT_MODE
    assert result.job_path == INBOX / "2주차.m4a"

def test_category_only_defaults_to_asr_mode():
    result = parse_inbox_path(INBOX, INBOX / "컴퓨터네트워크" / "2주차.m4a")
    assert result.category == "컴퓨터네트워크"
    assert result.mode == "asr"
    assert result.job_path == INBOX / "컴퓨터네트워크" / "2주차.m4a"

def test_explicit_diarize_mode():
    path = INBOX / "캡스톤" / "diarize" / "2026-09-08.m4a"
    result = parse_inbox_path(INBOX, path)
    assert result.category == "캡스톤"
    assert result.mode == "diarize"
    assert result.job_path == path

def test_asr_multitrack_job_path_is_the_session_folder_not_the_track_file():
    track = INBOX / "캡스톤" / "asr-multitrack" / "2026-09-08" / "백지훈.m4a"
    result = parse_inbox_path(INBOX, track)
    assert result.category == "캡스톤"
    assert result.mode == "asr-multitrack"
    assert result.job_path == INBOX / "캡스톤" / "asr-multitrack" / "2026-09-08"

def test_unrecognized_second_segment_is_ambiguous_and_skipped():
    # "3장" is not a valid mode name -> ambiguous depth, must not guess.
    path = INBOX / "컴퓨터네트워크" / "3장" / "2주차.m4a"
    assert parse_inbox_path(INBOX, path) is None

def test_asr_multitrack_without_session_subfolder_is_ambiguous():
    path = INBOX / "캡스톤" / "asr-multitrack" / "직접파일.m4a"
    assert parse_inbox_path(INBOX, path) is None

def test_too_deep_structure_is_ambiguous():
    path = INBOX / "캡스톤" / "asr-multitrack" / "2026-09-08" / "sub" / "x.m4a"
    assert parse_inbox_path(INBOX, path) is None

def test_valid_modes_contract():
    assert VALID_MODES == frozenset({"asr", "asr-multitrack", "diarize"})
