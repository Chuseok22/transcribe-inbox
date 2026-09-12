from unittest.mock import MagicMock
import pytest
from transcribe_inbox.cli import build_parser, retry

def test_retry_subcommand_parses_job_id():
    parser = build_parser()
    args = parser.parse_args(["retry", "abc-123"])
    assert args.command == "retry"
    assert args.job_id == "abc-123"

def test_retry_fails_atomically_if_status_changed_between_select_and_update(tmp_path):
    """The UPDATE must re-check status = 'FAILED' itself (not just trust the
    earlier SELECT) so a concurrent retry/daemon claim can't be silently
    undone -- a zero-row RETURNING means someone else already moved the job
    on, and retry() must roll back and fail instead of reporting success."""
    source = tmp_path / "a.m4a"
    source.write_bytes(b"x")
    conn = MagicMock()
    select_cursor = MagicMock()
    select_cursor.fetchone.return_value = (str(source), "FAILED")
    update_cursor = MagicMock()
    update_cursor.fetchone.return_value = None  # UPDATE matched zero rows
    conn.execute.side_effect = [select_cursor, update_cursor]

    with pytest.raises(SystemExit):
        retry(conn, "some-id")

    conn.rollback.assert_called_once()
    conn.commit.assert_not_called()

def test_retry_commits_when_the_atomic_update_succeeds(tmp_path):
    source = tmp_path / "a.m4a"
    source.write_bytes(b"x")
    conn = MagicMock()
    select_cursor = MagicMock()
    select_cursor.fetchone.return_value = (str(source), "FAILED")
    update_cursor = MagicMock()
    update_cursor.fetchone.return_value = ("some-id",)  # UPDATE matched one row
    conn.execute.side_effect = [select_cursor, update_cursor]

    retry(conn, "some-id")

    conn.commit.assert_called_once()
    conn.rollback.assert_not_called()
