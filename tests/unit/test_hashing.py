from transcribe_inbox.hashing import is_hidden_file, hash_file, hash_session
from pathlib import Path

def test_is_hidden_file():
    assert is_hidden_file(Path("/a/b/.DS_Store")) is True
    assert is_hidden_file(Path("/a/b/2주차.m4a")) is False

def test_hash_file_is_deterministic(tmp_path):
    f = tmp_path / "a.m4a"
    f.write_bytes(b"hello world")
    assert hash_file(f) == hash_file(f)
    assert len(hash_file(f)) == 64  # sha256 hex digest

def test_hash_file_changes_with_content(tmp_path):
    f = tmp_path / "a.m4a"
    f.write_bytes(b"hello")
    first = hash_file(f)
    f.write_bytes(b"world")
    assert hash_file(f) != first

def test_hash_session_ignores_dotfiles_and_order(tmp_path):
    session = tmp_path / "2026-09-08"
    session.mkdir()
    (session / "백지훈.m4a").write_bytes(b"a")
    (session / "홍길동.m4a").write_bytes(b"b")
    (session / ".DS_Store").write_bytes(b"junk")

    # Building the same content in a different filesystem creation order
    # must still hash identically (sorted by relative path internally).
    other = tmp_path / "2026-09-08-reordered"
    other.mkdir()
    (other / "홍길동.m4a").write_bytes(b"b")
    (other / "백지훈.m4a").write_bytes(b"a")

    assert hash_session(session) == hash_session(other)

def test_hash_session_changes_when_track_added(tmp_path):
    session = tmp_path / "s"
    session.mkdir()
    (session / "백지훈.m4a").write_bytes(b"a")
    before = hash_session(session)
    (session / "김철수.m4a").write_bytes(b"c")
    assert hash_session(session) != before
