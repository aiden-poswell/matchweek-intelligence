"""Parser for the Football.TXT "Matchday N" / literal-"v" fixture sub-format.

Direct inspection of the real source (docs/SOURCE_RIGHTS_AND_PROVENANCE.md section 1b)
found THREE distinct sub-formats of the nominally-same `1-premierleague.txt` file across
four consecutive seasons. This module parses only the sub-format shared by 2024/25 and
2026/27 (bullet-prefixed "Matchday N" headers; fixture lines using a literal " v "
separator). Any other sub-format is detected and rejected with
`UnsupportedFootballTxtFormatError` rather than guessed at.

Grain and status rules (see docs/DATA_CONTRACT.md for the authoritative statement):
- The match grain is (competition, season, match_date, home_team_raw, away_team_raw) —
  NOT the source's round/matchday label, which is carried through only as an untrusted,
  informational field. Real files were directly confirmed to reuse a round label more
  than once for rearranged fixtures (see provenance doc section 1c).
- A fixture's status is derived strictly from whether a score is present and how the
  match date compares to the caller-supplied `as_of_date` — never from calendar date
  alone, and a missing score is never turned into a 0-0 draw.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

SUPPORTED_SUBFORMAT = "matchday_v_literal"

_MONTHS = {
    "Jan": 1,
    "Feb": 2,
    "Mar": 3,
    "Apr": 4,
    "May": 5,
    "Jun": 6,
    "Jul": 7,
    "Aug": 8,
    "Sep": 9,
    "Oct": 10,
    "Nov": 11,
    "Dec": 12,
}

_HEADER_RE = re.compile(r"^▪\s*(.+?)\s*$", re.MULTILINE)
_SEASON_SPAN_RE = re.compile(
    r"^#\s*Dates?\s+\w+\s+(\w{3})\s+\d{1,2}\s+(\d{4})\s*-\s*\w+\s+(\w{3})\s+\d{1,2}\s+(\d{4})",
    re.MULTILINE,
)
_DATE_LINE_RE = re.compile(
    r"^\s*(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+(\w{3})\s+(\d{1,2})(?:\s+(\d{4}))?\s*$"
)
_TRAILING_SCORE_RE = re.compile(r"(\d+)-(\d+)(?:\s+\((\d+)-(\d+)\))?\s*$")
_LEADING_TIME_RE = re.compile(r"^\s*(?:(\d{1,2}:\d{2})\s+)?(.*)$")


class UnsupportedFootballTxtFormatError(RuntimeError):
    """Raised when a file's fixture sub-format is not the one this parser supports."""

    def __init__(self, detected_subformat: str):
        self.detected_subformat = detected_subformat
        super().__init__(
            f"unsupported Football.TXT sub-format: {detected_subformat!r} "
            f"(only {SUPPORTED_SUBFORMAT!r} is parsed by this module)"
        )


@dataclass(frozen=True)
class MatchRecord:
    competition: str
    season: str
    match_date: date
    raw_round_label: str
    home_team_raw: str
    away_team_raw: str
    home_score: int | None
    away_score: int | None
    home_score_ht: int | None
    away_score_ht: int | None
    status: str  # "played_with_score" | "result_missing" | "scheduled_future"
    source_line_no: int


@dataclass(frozen=True)
class QuarantinedLine:
    line_no: int
    raw_text: str
    reason: str


@dataclass(frozen=True)
class ParseResult:
    subformat: str
    records: list[MatchRecord] = field(default_factory=list)
    quarantined: list[QuarantinedLine] = field(default_factory=list)


def detect_subformat(text: str) -> str:
    headers = _HEADER_RE.findall(text)
    if not headers:
        return "unknown"
    if any(h.startswith("Regular Season") for h in headers):
        return "regular_season_scorer_annotated"
    if any(h.startswith("Matchday") for h in headers):
        return SUPPORTED_SUBFORMAT if " v " in text else "matchday_no_v_literal"
    return "unknown"


def _parse_season_span(text: str) -> tuple[int, int]:
    m = _SEASON_SPAN_RE.search(text)
    if not m:
        raise UnsupportedFootballTxtFormatError("missing '# Date <start> - <end>' header line")
    return int(m.group(2)), int(m.group(4))


def parse_football_txt(
    text: str,
    competition: str,
    season: str,
    as_of_date: date,
) -> ParseResult:
    """Parse Football.TXT content already confirmed to be SUPPORTED_SUBFORMAT.

    Raises UnsupportedFootballTxtFormatError if the text is not actually that
    sub-format — callers should not rely on silent guessing.
    """
    subformat = detect_subformat(text)
    if subformat != SUPPORTED_SUBFORMAT:
        raise UnsupportedFootballTxtFormatError(subformat)

    start_year, end_year = _parse_season_span(text)
    current_year = start_year
    rolled_over = False
    previous_month: int | None = None
    current_date: date | None = None
    current_round_label = ""

    records: list[MatchRecord] = []
    quarantined: list[QuarantinedLine] = []

    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.rstrip()
        stripped = line.strip()

        if not stripped or stripped.startswith("=") or stripped.startswith("#"):
            continue

        header_m = _HEADER_RE.match(line)
        if header_m:
            current_round_label = header_m.group(1)
            continue

        date_m = _DATE_LINE_RE.match(line)
        if date_m:
            month_abbr, day_str, year_str = date_m.groups()
            month = _MONTHS.get(month_abbr)
            if month is None:
                quarantined.append(
                    QuarantinedLine(line_no, raw_line, f"unrecognised month {month_abbr!r}")
                )
                continue
            if year_str:
                current_year = int(year_str)
            elif previous_month is not None and month < previous_month and not rolled_over:
                current_year = end_year
                rolled_over = True
            previous_month = month
            try:
                current_date = date(current_year, month, int(day_str))
            except ValueError as exc:
                quarantined.append(QuarantinedLine(line_no, raw_line, f"invalid date: {exc}"))
                current_date = None
            continue

        if " v " in line:
            if current_date is None:
                quarantined.append(
                    QuarantinedLine(line_no, raw_line, "fixture line before any date header")
                )
                continue
            record = _parse_fixture_line(
                line, line_no, competition, season, current_date, current_round_label, as_of_date
            )
            if record is None:
                quarantined.append(QuarantinedLine(line_no, raw_line, "fixture line did not parse"))
            else:
                records.append(record)
            continue

        quarantined.append(QuarantinedLine(line_no, raw_line, "unmatched line"))

    return ParseResult(subformat=subformat, records=records, quarantined=quarantined)


def _parse_fixture_line(
    line: str,
    line_no: int,
    competition: str,
    season: str,
    match_date: date,
    round_label: str,
    as_of_date: date,
) -> MatchRecord | None:
    time_m = _LEADING_TIME_RE.match(line)
    rest = time_m.group(2) if time_m else line

    home_score = away_score = home_ht = away_ht = None
    score_m = _TRAILING_SCORE_RE.search(rest)
    if score_m:
        home_score, away_score = int(score_m.group(1)), int(score_m.group(2))
        if score_m.group(3) is not None:
            home_ht, away_ht = int(score_m.group(3)), int(score_m.group(4))
        rest = rest[: score_m.start()].rstrip()

    parts = re.split(r"\s+v\s+", rest, maxsplit=1)
    if len(parts) != 2:
        return None
    home_raw, away_raw = parts[0].strip(), parts[1].strip()
    if not home_raw or not away_raw:
        return None

    if home_score is not None:
        status = "played_with_score"
    elif match_date < as_of_date:
        status = "result_missing"
    else:
        status = "scheduled_future"

    return MatchRecord(
        competition=competition,
        season=season,
        match_date=match_date,
        raw_round_label=round_label,
        home_team_raw=home_raw,
        away_team_raw=away_raw,
        home_score=home_score,
        away_score=away_score,
        home_score_ht=home_ht,
        away_score_ht=away_ht,
        status=status,
        source_line_no=line_no,
    )
