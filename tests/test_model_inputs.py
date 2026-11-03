"""model_inputs.py tests: fail-closed behaviour (poisoned manifest hash, missing
cached input, unmapped team, duplicate fixture) and canonical-identity stability under
row-order/alias shuffling. Entirely synthetic (tmp_path) — never touches the real cache."""

from __future__ import annotations

import hashlib
import json
from datetime import timedelta
from pathlib import Path

import pytest
from conftest import FULL_SEASON_START, build_full_double_round_robin_text

from matchweek_intelligence.fetch import PINNED_COMMIT, SOURCE_REPO
from matchweek_intelligence.model_inputs import (
    ELIGIBLE_SEASONS,
    ModelInputError,
    load_eligible_historical_records,
)


def _manifest_files(raw_dir: Path, entries: list[tuple[str, str]]) -> list[dict]:
    files = []
    for path, text in entries:
        content = text.encode("utf-8")
        full_path = raw_dir / path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_bytes(content)
        files.append(
            {
                "path": path,
                "sha256": hashlib.sha256(content).hexdigest(),
                "byte_count": len(content),
            }
        )
    return files


def _write_manifest(
    raw_dir: Path,
    manifest_path: Path,
    entries: list[tuple[str, str]],
    source_repo: str = SOURCE_REPO,
    pinned_commit: str = PINNED_COMMIT,
) -> None:
    files = _manifest_files(raw_dir, entries)
    manifest_path.write_text(
        json.dumps({"source_repo": source_repo, "pinned_commit": pinned_commit, "files": files}),
        encoding="utf-8",
    )


def _three_season_texts() -> dict[str, str]:
    texts = {}
    start = FULL_SEASON_START
    for season_label, path in [
        ("2023/24", "2023-24/1-premierleague.txt"),
        ("2024/25", "2024-25/1-premierleague.txt"),
        ("2025/26", "2025-26/1-premierleague.txt"),
    ]:
        texts[path] = build_full_double_round_robin_text(season_label, start)
        start = start + timedelta(days=400)
    return texts


def test_loads_exactly_1140_fixtures_380_per_eligible_season(tmp_path):
    raw_dir, manifest_path = tmp_path / "raw", tmp_path / "manifest.json"
    _write_manifest(raw_dir, manifest_path, list(_three_season_texts().items()))
    records = load_eligible_historical_records(raw_dir=raw_dir, manifest_path=manifest_path)
    assert len(records) == 1140
    for season in ELIGIBLE_SEASONS:
        assert sum(1 for r in records if r.season == season) == 380


def test_records_are_sorted_by_date_then_canonical_teams_not_source_order(tmp_path):
    raw_dir, manifest_path = tmp_path / "raw", tmp_path / "manifest.json"
    _write_manifest(raw_dir, manifest_path, list(_three_season_texts().items()))
    records = load_eligible_historical_records(raw_dir=raw_dir, manifest_path=manifest_path)
    keys = [(r.match_date, r.home_team, r.away_team) for r in records]
    assert keys == sorted(keys)


def test_fails_closed_on_missing_manifest(tmp_path):
    with pytest.raises(ModelInputError, match="manifest not found"):
        load_eligible_historical_records(
            raw_dir=tmp_path / "raw", manifest_path=tmp_path / "nope.json"
        )


def test_fails_closed_on_missing_cached_file(tmp_path):
    raw_dir, manifest_path = tmp_path / "raw", tmp_path / "manifest.json"
    entries = list(_three_season_texts().items())
    _write_manifest(raw_dir, manifest_path, entries)
    (raw_dir / entries[0][0]).unlink()
    with pytest.raises(ModelInputError, match="missing on disk"):
        load_eligible_historical_records(raw_dir=raw_dir, manifest_path=manifest_path)


def test_fails_closed_on_poisoned_manifest_hash(tmp_path):
    raw_dir, manifest_path = tmp_path / "raw", tmp_path / "manifest.json"
    entries = list(_three_season_texts().items())
    _write_manifest(raw_dir, manifest_path, entries)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"][0]["sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ModelInputError, match="integrity check failed"):
        load_eligible_historical_records(raw_dir=raw_dir, manifest_path=manifest_path)


def test_fails_closed_on_unmapped_team_name(tmp_path):
    from conftest import REAL_CANONICAL_NAMES

    raw_dir, manifest_path = tmp_path / "raw", tmp_path / "manifest.json"
    texts = _three_season_texts()
    bad_teams = REAL_CANONICAL_NAMES[:-1] + ["Totally Unmapped FC"]
    texts["2024-25/1-premierleague.txt"] = build_full_double_round_robin_text(
        "2024/25", FULL_SEASON_START + timedelta(days=400), teams=bad_teams
    )
    _write_manifest(raw_dir, manifest_path, list(texts.items()))
    with pytest.raises(ModelInputError, match="Totally Unmapped FC"):
        load_eligible_historical_records(raw_dir=raw_dir, manifest_path=manifest_path)


def test_fails_closed_on_duplicate_fixture_even_with_380_total(tmp_path):
    raw_dir, manifest_path = tmp_path / "raw", tmp_path / "manifest.json"
    texts = _three_season_texts()
    text_2425 = texts["2024-25/1-premierleague.txt"]
    lines = text_2425.splitlines()
    duplicated = "\n".join(lines[:-2] + lines[7:9]) + "\n"
    texts["2024-25/1-premierleague.txt"] = duplicated
    _write_manifest(raw_dir, manifest_path, list(texts.items()))
    with pytest.raises(ModelInputError, match="round-robin violation"):
        load_eligible_historical_records(raw_dir=raw_dir, manifest_path=manifest_path)


def test_fails_closed_when_an_eligible_season_is_absent_from_the_manifest(tmp_path):
    raw_dir, manifest_path = tmp_path / "raw", tmp_path / "manifest.json"
    texts = _three_season_texts()
    del texts["2025-26/1-premierleague.txt"]
    _write_manifest(raw_dir, manifest_path, list(texts.items()))
    with pytest.raises(ModelInputError, match="2025-26"):
        load_eligible_historical_records(raw_dir=raw_dir, manifest_path=manifest_path)


def test_2026_27_is_never_loaded_even_if_present_in_the_manifest(tmp_path):
    raw_dir, manifest_path = tmp_path / "raw", tmp_path / "manifest.json"
    texts = _three_season_texts()
    texts["2026-27/1-premierleague.txt"] = build_full_double_round_robin_text(
        "2026/27", FULL_SEASON_START + timedelta(days=1200)
    )
    _write_manifest(raw_dir, manifest_path, list(texts.items()))
    records = load_eligible_historical_records(raw_dir=raw_dir, manifest_path=manifest_path)
    assert all(r.season != "2026-27" for r in records)
    assert len(records) == 1140  # unaffected by the extra, ignored file


def test_row_order_shuffle_in_the_source_file_does_not_change_the_loaded_corpus(tmp_path):
    raw_dir, manifest_path = tmp_path / "raw", tmp_path / "manifest.json"
    texts = _three_season_texts()
    _write_manifest(raw_dir, manifest_path, list(texts.items()))
    baseline = load_eligible_historical_records(raw_dir=raw_dir, manifest_path=manifest_path)

    # Re-fetch with headers in a different manifest file order (simulating source-file
    # listing order differing) — the loader must still sort deterministically.
    raw_dir2, manifest_path2 = tmp_path / "raw2", tmp_path / "manifest2.json"
    reordered_entries = list(reversed(list(texts.items())))
    _write_manifest(raw_dir2, manifest_path2, reordered_entries)
    reordered = load_eligible_historical_records(raw_dir=raw_dir2, manifest_path=manifest_path2)

    baseline_keys = [
        (r.match_date, r.home_team, r.away_team, r.home_score, r.away_score) for r in baseline
    ]
    reordered_keys = [
        (r.match_date, r.home_team, r.away_team, r.home_score, r.away_score) for r in reordered
    ]
    assert baseline_keys == reordered_keys


# --- S04 Stage A1: source identity lock ---------------------------------------------
#
# Independent review found that a manifest with CORRECT per-file hashes but a WRONG
# source_repo or pinned_commit was accepted — matching hashes alone only prove the
# cached bytes match what the manifest claims, not that the manifest describes this
# project's actual approved source. These tests prove the gap is closed.


def test_a1_rejects_a_manifest_with_valid_files_but_wrong_source_repo(tmp_path):
    raw_dir, manifest_path = tmp_path / "raw", tmp_path / "manifest.json"
    entries = list(_three_season_texts().items())
    _write_manifest(raw_dir, manifest_path, entries, source_repo="some-other/repo")
    with pytest.raises(ModelInputError, match="source_repo mismatch"):
        load_eligible_historical_records(raw_dir=raw_dir, manifest_path=manifest_path)


def test_a1_rejects_a_manifest_with_valid_files_but_wrong_pinned_commit(tmp_path):
    raw_dir, manifest_path = tmp_path / "raw", tmp_path / "manifest.json"
    entries = list(_three_season_texts().items())
    _write_manifest(raw_dir, manifest_path, entries, pinned_commit="0" * 40)
    with pytest.raises(ModelInputError, match="pinned_commit mismatch"):
        load_eligible_historical_records(raw_dir=raw_dir, manifest_path=manifest_path)


def test_a1_rejects_a_manifest_missing_source_identity_fields_entirely(tmp_path):
    raw_dir, manifest_path = tmp_path / "raw", tmp_path / "manifest.json"
    entries = list(_three_season_texts().items())
    files = _manifest_files(raw_dir, entries)
    manifest_path.write_text(json.dumps({"files": files}), encoding="utf-8")
    with pytest.raises(ModelInputError, match="source_repo mismatch"):
        load_eligible_historical_records(raw_dir=raw_dir, manifest_path=manifest_path)


def test_a1_rejects_a_manifest_that_is_not_a_json_object(tmp_path):
    raw_dir, manifest_path = tmp_path / "raw", tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    with pytest.raises(ModelInputError, match="not a JSON object"):
        load_eligible_historical_records(raw_dir=raw_dir, manifest_path=manifest_path)


def test_a1_rejects_a_manifest_whose_files_field_is_not_a_list(tmp_path):
    raw_dir, manifest_path = tmp_path / "raw", tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps({"source_repo": SOURCE_REPO, "pinned_commit": PINNED_COMMIT, "files": "oops"}),
        encoding="utf-8",
    )
    with pytest.raises(ModelInputError, match="non-empty list"):
        load_eligible_historical_records(raw_dir=raw_dir, manifest_path=manifest_path)


def test_a1_rejects_a_malformed_file_entry_missing_required_fields(tmp_path):
    raw_dir, manifest_path = tmp_path / "raw", tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "source_repo": SOURCE_REPO,
                "pinned_commit": PINNED_COMMIT,
                "files": [{"path": "2023-24/1-premierleague.txt"}],  # missing sha256/byte_count
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ModelInputError, match="malformed sha256"):
        load_eligible_historical_records(raw_dir=raw_dir, manifest_path=manifest_path)


def test_a1_rejects_a_file_entry_with_a_path_traversal_attempt(tmp_path):
    raw_dir, manifest_path = tmp_path / "raw", tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "source_repo": SOURCE_REPO,
                "pinned_commit": PINNED_COMMIT,
                "files": [
                    {
                        "path": "../../../../etc/passwd",
                        "sha256": "0" * 64,
                        "byte_count": 10,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ModelInputError, match="unrecognised path"):
        load_eligible_historical_records(raw_dir=raw_dir, manifest_path=manifest_path)


def test_a1_rejects_a_file_entry_with_a_non_string_path(tmp_path):
    raw_dir, manifest_path = tmp_path / "raw", tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "source_repo": SOURCE_REPO,
                "pinned_commit": PINNED_COMMIT,
                "files": [{"path": 12345, "sha256": "0" * 64, "byte_count": 10}],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ModelInputError, match="unrecognised path"):
        load_eligible_historical_records(raw_dir=raw_dir, manifest_path=manifest_path)


def test_a1_existing_valid_manifest_still_passes_unchanged(tmp_path):
    # The positive control: a correctly-identified, correctly-hashed manifest must
    # continue to pass exactly as before this guard was added.
    raw_dir, manifest_path = tmp_path / "raw", tmp_path / "manifest.json"
    entries = list(_three_season_texts().items())
    _write_manifest(raw_dir, manifest_path, entries)  # real SOURCE_REPO/PINNED_COMMIT
    records = load_eligible_historical_records(raw_dir=raw_dir, manifest_path=manifest_path)
    assert len(records) == 1140
