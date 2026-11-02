"""Fetch allowlisted Football.TXT files from the pinned openfootball/england commit.

S01 fetched two files (2024/25, 2026/27) in the "Matchday N" / literal-"v" sub-format.
S02 extends the allowlist to the two remaining historical seasons this project's parser
now also supports (2023/24, 2025/26), each in its own distinct real sub-format — see
reports/S02_FORMAT_AUDIT.md and docs/SOURCE_RIGHTS_AND_PROVENANCE.md section 1b. The
commit is pinned explicitly; there is no "latest"/moving-target fetch, no background
refresh, and no fallback to a mirror or any other source.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import requests

SOURCE_REPO = "openfootball/england"
PINNED_COMMIT = "9ee7a0c351805c99cc334478a9bf04b7d0432fec"
_RAW_BASE = f"https://raw.githubusercontent.com/{SOURCE_REPO}/{PINNED_COMMIT}"

ALLOWLISTED_PATHS: tuple[str, ...] = (
    "2023-24/1-premierleague.txt",
    "2024-25/1-premierleague.txt",
    "2025-26/1-premierleague.txt",
    "2026-27/1-premierleague.txt",
)

DEFAULT_RAW_DIR = Path("data/raw")
DEFAULT_MANIFEST_PATH = Path("reports/s01_source_manifest.json")


class SourceFetchError(RuntimeError):
    """Raised when an allowlisted file cannot be fetched, is empty, or isn't allowlisted."""


@dataclass(frozen=True)
class FetchedFile:
    path: str
    sha256: str
    byte_count: int
    local_path: Path


def _atomic_write(dest: Path, content: bytes) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=dest.parent, prefix=".tmp-", suffix=".part")
    tmp_path = Path(tmp_name)
    try:
        with open(fd, "wb") as handle:
            handle.write(content)
        tmp_path.replace(dest)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise


def fetch_file(
    path: str,
    raw_dir: Path = DEFAULT_RAW_DIR,
    session: requests.Session | None = None,
) -> FetchedFile:
    if path not in ALLOWLISTED_PATHS:
        raise SourceFetchError(f"path not allowlisted for fetch: {path!r}")
    url = f"{_RAW_BASE}/{path}"
    http = session or requests.Session()
    response = http.get(url, timeout=30)
    if response.status_code != 200:
        raise SourceFetchError(f"fetch failed ({response.status_code}) for {url}")
    content = response.content
    if not content:
        raise SourceFetchError(f"fetched file is empty: {url}")
    digest = hashlib.sha256(content).hexdigest()
    dest = raw_dir / path
    _atomic_write(dest, content)
    return FetchedFile(path=path, sha256=digest, byte_count=len(content), local_path=dest)


def fetch_all(raw_dir: Path = DEFAULT_RAW_DIR) -> list[FetchedFile]:
    session = requests.Session()
    return [fetch_file(p, raw_dir=raw_dir, session=session) for p in ALLOWLISTED_PATHS]


def write_manifest(files: list[FetchedFile], manifest_path: Path = DEFAULT_MANIFEST_PATH) -> None:
    manifest = {
        "source_repo": SOURCE_REPO,
        "pinned_commit": PINNED_COMMIT,
        "extracted_at_utc": datetime.now(UTC).isoformat(),
        "files": [{"path": f.path, "sha256": f.sha256, "byte_count": f.byte_count} for f in files],
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> None:
    files = fetch_all()
    write_manifest(files)
    for f in files:
        print(f"{f.path}: {f.byte_count} bytes, sha256={f.sha256}")


if __name__ == "__main__":
    main()
