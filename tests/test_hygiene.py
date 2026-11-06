"""Release-hygiene checks against the tracked file list itself (via `git ls-files`),
plus sanity checks that the rights audit actually states a decision for every named
source rather than silently treating an unclear one as cleared."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    )
    return [line for line in result.stdout.splitlines() if line]


def _is_git_repo() -> bool:
    # A clean, .git-free export of this project (exactly what Stage E ships) is not a
    # git work tree at all — these specific checks must then skip honestly rather than
    # error, since `git ls-files`/`git remote -v` have nothing to operate on.
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        return result.returncode == 0 and result.stdout.strip() == "true"
    except OSError:
        return False


requires_git_repo = pytest.mark.skipif(
    not _is_git_repo(),
    reason="not a git work tree (e.g. a clean exported snapshot) — skipping honestly",
)


@requires_git_repo
def test_no_raw_source_files_or_private_markers_are_tracked():
    tracked = _tracked_files()
    for path in tracked:
        lower = path.lower()
        assert not lower.startswith("data/raw/"), f"raw source file tracked: {path}"
        assert "_private" not in lower, f"private-marked file tracked: {path}"
        assert not lower.endswith(".csv"), f"raw tabular data tracked: {path}"


# This file itself legitimately contains the literal forbidden strings below (as the
# detector's own fixture data), so it is excluded from the two scans that use them —
# not because it's exempt from the hygiene rule, but because it's the rule itself.
_SELF_PATH = "tests/test_hygiene.py"


@requires_git_repo
def test_no_personal_local_filesystem_paths_in_tracked_text_files():
    # Author attribution (e.g. in pyproject.toml) is expected and fine; what must never
    # leak is an actual local machine path, which would reveal this machine's directory
    # layout rather than just the author's name.
    tracked = _tracked_files()
    forbidden_fragments = ("C:\\Users\\", "/home/", "/Users/Aiden", "AppData\\Local\\Temp")
    text_suffixes = {".py", ".md", ".toml", ".json", ".txt", ".cfg", ".ini"}
    for path in tracked:
        if path == _SELF_PATH or Path(path).suffix not in text_suffixes:
            continue
        full_path = REPO_ROOT / path
        content = full_path.read_text(encoding="utf-8", errors="ignore")
        for fragment in forbidden_fragments:
            assert fragment not in content, (
                f"{path} contains a personal path fragment: {fragment!r}"
            )


@requires_git_repo
def test_no_sibling_project_names_appear_in_tracked_files():
    # This project must never reference or embed sibling-project data.
    tracked = _tracked_files()
    forbidden = (
        "expected-goals-lab",
        "opposition-intelligence",
        "scouting-recruitment-intelligence",
    )
    for path in tracked:
        if path == _SELF_PATH or Path(path).suffix not in {".py", ".md", ".toml", ".json"}:
            continue
        content = (REPO_ROOT / path).read_text(encoding="utf-8", errors="ignore")
        for name in forbidden:
            assert name not in content, f"{path} references sibling project {name!r}"


@requires_git_repo
def test_remote_if_configured_points_only_at_the_expected_public_repo():
    """Before the public launch, this test asserted NO remote was ever configured — a
    safety net for the private-development phase, to catch an accidental premature push.
    That phase is over: this project was deliberately published to
    https://github.com/aiden-poswell/matchweek-intelligence with the owner's explicit
    go-live approval. The invariant this guards is now narrower but still real: whatever
    remote(s) exist must point at that same expected repository, never an unexpected host
    or a different owner/repo added by accident or by a local clone under another name."""
    result = subprocess.run(
        ["git", "remote", "-v"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    )
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    for line in lines:
        assert "github.com/aiden-poswell/matchweek-intelligence" in line, (
            f"unexpected remote configured: {line!r}"
        )


def test_source_rights_doc_states_an_explicit_decision_for_every_candidate_source():
    doc = (REPO_ROOT / "docs" / "SOURCE_RIGHTS_AND_PROVENANCE.md").read_text(encoding="utf-8")
    for source_name, expected_decisions in {
        "openfootball/england": ("ACCEPT",),
        "openfootball/football.json": ("REJECT",),
        "footballcsv/england": ("REJECT",),
        "oladeeayo/open-matchday": ("REJECT",),
    }.items():
        assert source_name in doc, f"{source_name} not mentioned in the rights audit at all"
        # A decision must appear within 500 characters of AT LEAST ONE mention of the
        # source name (its dedicated section heading or its row in the comparison
        # table) — not borrowed from an unrelated part of the document.
        found_nearby_decision = False
        search_from = 0
        while True:
            idx = doc.find(source_name, search_from)
            if idx == -1:
                break
            window = doc[max(0, idx - 500) : idx + 500]
            if any(decision in window for decision in expected_decisions):
                found_nearby_decision = True
                break
            search_from = idx + len(source_name)
        assert found_nearby_decision, (
            f"no explicit decision found near any mention of {source_name}"
        )


def test_source_decision_memo_never_claims_the_current_season_is_publishable():
    memo = (REPO_ROOT / "reports" / "S01_SOURCE_DECISION.md").read_text(encoding="utf-8")
    assert "BLOCKED" in memo
    assert "current_season_publishable" in memo or "BLOCKED for any public/live claim" in memo


def test_no_model_dashboard_or_pdf_claim_in_tracked_docs():
    forbidden_claims = (
        "the model predicts",
        "forecast probability",
        "our dashboard shows",
    )
    for doc_path in (REPO_ROOT / "docs").glob("*.md"):
        content = doc_path.read_text(encoding="utf-8").lower()
        for claim in forbidden_claims:
            assert claim not in content, (
                f"{doc_path.name} appears to assert a real model/forecast result"
            )
