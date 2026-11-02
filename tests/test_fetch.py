"""Fetch tests use a fake HTTP session — no real network call in the unit suite.
A separate, honestly-skipped real-network test lives at the bottom of this file."""

from __future__ import annotations

import json

import pytest

from matchweek_intelligence import fetch


class _FakeResponse:
    def __init__(self, status_code: int, content: bytes):
        self.status_code = status_code
        self.content = content


class _FakeSession:
    def __init__(self, responses: dict[str, _FakeResponse]):
        self._responses = responses
        self.requested_urls: list[str] = []

    def get(self, url: str, timeout: int) -> _FakeResponse:
        self.requested_urls.append(url)
        return self._responses[url]


def test_rejects_a_path_that_is_not_allowlisted(tmp_path):
    with pytest.raises(fetch.SourceFetchError, match="not allowlisted"):
        fetch.fetch_file("2026-27/2-championship.txt", raw_dir=tmp_path)


def test_fetches_an_allowlisted_path_and_writes_it_atomically(tmp_path):
    path = fetch.ALLOWLISTED_PATHS[0]
    url = f"{fetch._RAW_BASE}/{path}"
    session = _FakeSession({url: _FakeResponse(200, b"some real-looking fixture text")})

    result = fetch.fetch_file(path, raw_dir=tmp_path, session=session)

    assert result.byte_count == len(b"some real-looking fixture text")
    assert result.local_path.read_bytes() == b"some real-looking fixture text"
    assert len(result.sha256) == 64
    # No leftover temp file from the atomic-write dance.
    leftovers = list((tmp_path / path).parent.glob(".tmp-*"))
    assert leftovers == []


def test_raises_on_non_200_response(tmp_path):
    path = fetch.ALLOWLISTED_PATHS[0]
    url = f"{fetch._RAW_BASE}/{path}"
    session = _FakeSession({url: _FakeResponse(404, b"")})

    with pytest.raises(fetch.SourceFetchError, match="404"):
        fetch.fetch_file(path, raw_dir=tmp_path, session=session)


def test_raises_on_empty_response(tmp_path):
    path = fetch.ALLOWLISTED_PATHS[0]
    url = f"{fetch._RAW_BASE}/{path}"
    session = _FakeSession({url: _FakeResponse(200, b"")})

    with pytest.raises(fetch.SourceFetchError, match="empty"):
        fetch.fetch_file(path, raw_dir=tmp_path, session=session)


def test_manifest_records_pinned_commit_and_every_file_hash(tmp_path):
    files = [
        fetch.FetchedFile(
            path="a.txt", sha256="abc123", byte_count=10, local_path=tmp_path / "a.txt"
        ),
        fetch.FetchedFile(
            path="b.txt", sha256="def456", byte_count=20, local_path=tmp_path / "b.txt"
        ),
    ]
    manifest_path = tmp_path / "manifest.json"
    fetch.write_manifest(files, manifest_path=manifest_path)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["pinned_commit"] == fetch.PINNED_COMMIT
    assert manifest["source_repo"] == fetch.SOURCE_REPO
    assert {f["path"]: f["sha256"] for f in manifest["files"]} == {
        "a.txt": "abc123",
        "b.txt": "def456",
    }
    assert "extracted_at_utc" in manifest


@pytest.mark.skipif(
    __import__("os").environ.get("MI_ALLOW_NETWORK_TESTS") != "1",
    reason="real network fetch against the pinned GitHub commit — opt-in only",
)
def test_real_network_fetch_matches_the_recorded_byte_counts(tmp_path):
    files = fetch.fetch_all(raw_dir=tmp_path)
    by_path = {f.path: f.byte_count for f in files}
    # 2024/25 is a completed, archived season at a pinned commit — exact byte count is
    # expected to be stable. 2026/27 is a current, live-updating file at the SAME pinned
    # commit, so it is also expected to be exactly this size as long as the pin holds;
    # a differing size here would mean the pinned commit itself changed underneath us.
    assert by_path["2024-25/1-premierleague.txt"] == 30316
    assert by_path["2026-27/1-premierleague.txt"] == 22800
