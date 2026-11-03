"""Prohibits reintroducing obsolete normative instructions into the four S01/S02 design
docs, without failing on an accurate, annotated historical mention of the retired field
name or helper (see reports/S03_PROTOCOL_ALIGNMENT.md)."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

_RETIREMENT_MARKERS = ("S01-era", "S01 field", "retired", "S02 note", "no longer")

_DOCS = [
    REPO_ROOT / "README.md",
    REPO_ROOT / "docs" / "FORECASTING_PROTOCOL.md",
    REPO_ROOT / "docs" / "SOURCE_RIGHTS_AND_PROVENANCE.md",
    REPO_ROOT / "docs" / "BACKTEST_INPUT_CONTRACT.md",
]


def _occurrences(content: str, needle: str) -> list[int]:
    positions = []
    start = 0
    while True:
        idx = content.find(needle, start)
        if idx == -1:
            break
        positions.append(idx)
        start = idx + len(needle)
    return positions


def test_every_mention_of_the_retired_field_name_is_annotated_as_historical():
    for doc_path in _DOCS:
        content = doc_path.read_text(encoding="utf-8")
        for idx in _occurrences(content, "current_season_publishable"):
            window = content[max(0, idx - 600) : idx + 600]
            assert any(marker in window for marker in _RETIREMENT_MARKERS), (
                f"{doc_path.name} mentions the retired field 'current_season_publishable' "
                f"near offset {idx} without a nearby retirement/historical-context marker "
                f"{_RETIREMENT_MARKERS} — this reads as live instruction, not history."
            )


def test_as_of_filter_is_never_prescribed_as_the_model_training_input():
    # as_of_filter is status-agnostic and may legitimately be mentioned as "the OTHER
    # helper, which is NOT sufficient" — that is the required, correct framing. It must
    # never appear recommending `as_of_filter` alone as what a model should train on.
    forbidden_phrasings = (
        "train on `as_of_filter`",
        "train on as_of_filter",
        "model input (`chronology.as_of_filter`)",
        "model input (chronology.as_of_filter)",
    )
    for doc_path in _DOCS:
        content = doc_path.read_text(encoding="utf-8")
        for phrase in forbidden_phrasings:
            assert phrase not in content, (
                f"{doc_path.name} prescribes as_of_filter as a model-training input: {phrase!r}"
            )


def test_forecasting_protocol_names_completed_training_results_as_of_as_the_training_helper():
    content = (REPO_ROOT / "docs" / "FORECASTING_PROTOCOL.md").read_text(encoding="utf-8")
    assert "completed_training_results_as_of" in content


def test_forecasting_protocol_states_live_claim_allowed_is_hard_coded_false():
    content = (REPO_ROOT / "docs" / "FORECASTING_PROTOCOL.md").read_text(encoding="utf-8")
    assert "live_claim_allowed" in content
    assert "hard-coded" in content or "hard coded" in content


def test_forecasting_protocol_poisson_baseline_is_honestly_described_as_shrunk():
    content = (REPO_ROOT / "docs" / "FORECASTING_PROTOCOL.md").read_text(encoding="utf-8")
    # The literal phrase "no regularisation" must not appear describing the ACTUAL S03
    # Poisson baseline as implemented — only as part of the honest correction narrative
    # explaining why that original framing was wrong.
    assert "pseudo-match shrinkage" in content or "pseudo matches" in content
    assert "k=5" in content


def test_readme_no_longer_claims_slice_01_data_feasibility_only_as_current_status():
    content = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "Slice 01 — data feasibility only" not in content
