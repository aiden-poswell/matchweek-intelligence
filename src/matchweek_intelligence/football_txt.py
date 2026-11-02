"""Parsers for the three real Football.TXT sub-formats this project supports.

Direct inspection of `1-premierleague.txt` across four consecutive seasons at pinned
commit 9ee7a0c351805c99cc334478a9bf04b7d0432fec (see
docs/SOURCE_RIGHTS_AND_PROVENANCE.md section 1b and reports/S02_FORMAT_AUDIT.md) found
three distinct real sub-formats:

- `matchday_v_literal` (2024/25, 2026/27): `▪ Matchday N` headers; fixture lines use a
  literal " v " separator, with the score (if any) appended after the away team.
- `matchday_score_between_no_v` (2023/24): `▪ Matchday N` headers; fixture lines have NO
  literal " v " — the score sits directly between the home and away team names, and
  every fixture in this file is already scored (the season is complete).
- `regular_season_score_between_scorer_annotated` (2025/26): `▪ Regular Season - N`
  headers; same score-between-teams shape as the format above, but each scored fixture
  may be followed by one or more scorer-annotation lines wrapped in parentheses
  (sometimes spanning more than one physical line). Scorer annotations are informational
  only: they never contribute a fixture, a score, or any other feature to this project,
  and they are consumed and discarded before fixture-line parsing is attempted, so a
  scorer line's own digits can never be mistaken for — or override — the fixture's
  displayed full-time score.

Any OTHER sub-format is detected and rejected with `UnsupportedFootballTxtFormatError`
rather than guessed at.

Grain and status rules (see docs/DATA_CONTRACT.md for the authoritative statement):
- The match grain is (competition, season, match_date, home_team_raw, away_team_raw) —
  NOT the source's round/matchday label, which is carried through only as an untrusted,
  informational field. Real files were directly confirmed to reuse a round label more
  than once, out of chronological order, for rearranged fixtures (see provenance doc
  section 1c) — in EVERY one of the three sub-formats, not just one.
- A fixture's status is derived strictly from whether a score is present and how the
  match date compares to the caller-supplied `as_of_date` — never from calendar date
  alone, and a missing score is never turned into a 0-0 draw.
- Year inference is bounded by the file's own declared season span (the
  `# Date(s) <start> - <end>` header) and is re-anchored whenever the source states an
  explicit year on a date line (observed at the real Dec->Jan boundary in three of the
  four files; 2023/24 never restates the year at all, so its rollover is inferred purely
  from a month decreasing without a stated year — see reports/S02_FORMAT_AUDIT.md).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

SUBFORMAT_MATCHDAY_V_LITERAL = "matchday_v_literal"
SUBFORMAT_MATCHDAY_SCORE_BETWEEN = "matchday_score_between_no_v"
SUBFORMAT_REGULAR_SEASON_SCORE_BETWEEN = "regular_season_score_between_scorer_annotated"

SUPPORTED_SUBFORMATS = frozenset(
    {
        SUBFORMAT_MATCHDAY_V_LITERAL,
        SUBFORMAT_MATCHDAY_SCORE_BETWEEN,
        SUBFORMAT_REGULAR_SEASON_SCORE_BETWEEN,
    }
)

# Retained for backward compatibility with S01 callers/tests: the original slice only
# ever supported this one sub-format under this name.
SUPPORTED_SUBFORMAT = SUBFORMAT_MATCHDAY_V_LITERAL

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
    r"^#\s*Dates?\s+\w+\s+(\w{3})\s+(\d{1,2})\s+(\d{4})\s*-\s*\w+\s+(\w{3})\s+(\d{1,2})\s+(\d{4})",
    re.MULTILINE,
)
_DATE_LINE_RE = re.compile(
    r"^\s*(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+(\w{3})\s+(\d{1,2})(?:\s+(\d{4}))?\s*$"
)
_TRAILING_SCORE_RE = re.compile(r"(\d+)-(\d+)(?:\s+\((\d+)-(\d+)\))?\s*$")
_EMBEDDED_SCORE_RE = re.compile(r"(\d+)-(\d+)(?:\s+\((\d+)-(\d+)\))?")
_LEADING_TIME_RE = re.compile(r"^\s*(?:(\d{1,2}:\d{2})\s+)?(.*)$")


class UnsupportedFootballTxtFormatError(RuntimeError):
    """Raised when a file's fixture sub-format is not one this parser supports."""

    def __init__(self, detected_subformat: str):
        self.detected_subformat = detected_subformat
        super().__init__(
            f"unsupported Football.TXT sub-format: {detected_subformat!r} "
            f"(supported: {sorted(SUPPORTED_SUBFORMATS)})"
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
    season_start_date: date | None = None
    season_end_date: date | None = None


def detect_subformat(text: str) -> str:
    headers = _HEADER_RE.findall(text)
    if not headers:
        return "unknown"
    if any(h.startswith("Regular Season") for h in headers):
        return SUBFORMAT_REGULAR_SEASON_SCORE_BETWEEN
    if any(h.startswith("Matchday") for h in headers):
        return SUBFORMAT_MATCHDAY_V_LITERAL if " v " in text else SUBFORMAT_MATCHDAY_SCORE_BETWEEN
    return "unknown"


def _parse_season_span(text: str) -> tuple[date, date]:
    m = _SEASON_SPAN_RE.search(text)
    if not m:
        raise UnsupportedFootballTxtFormatError("missing '# Date(s) <start> - <end>' header line")
    start_month_abbr, start_day, start_year, end_month_abbr, end_day, end_year = m.groups()
    start_month = _MONTHS.get(start_month_abbr)
    end_month = _MONTHS.get(end_month_abbr)
    if start_month is None or end_month is None:
        raise UnsupportedFootballTxtFormatError(
            f"unrecognised month in season span header: {m.group(0)!r}"
        )
    return (
        date(int(start_year), start_month, int(start_day)),
        date(int(end_year), end_month, int(end_day)),
    )


def parse_football_txt(
    text: str,
    competition: str,
    season: str,
    as_of_date: date,
) -> ParseResult:
    """Parse Football.TXT content, dispatching on its detected real sub-format.

    Raises UnsupportedFootballTxtFormatError if the text is not one of the three real
    sub-formats this module supports — callers should not rely on silent guessing.
    """
    subformat = detect_subformat(text)
    if subformat not in SUPPORTED_SUBFORMATS:
        raise UnsupportedFootballTxtFormatError(subformat)

    season_start, season_end = _parse_season_span(text)

    if subformat == SUBFORMAT_MATCHDAY_V_LITERAL:
        records, quarantined = _parse_v_literal(
            text, competition, season, as_of_date, season_start, season_end
        )
    else:
        records, quarantined = _parse_score_between(
            text, competition, season, as_of_date, season_start, season_end
        )

    return ParseResult(
        subformat=subformat,
        records=records,
        quarantined=quarantined,
        season_start_date=season_start,
        season_end_date=season_end,
    )


class _YearTracker:
    """Tracks the current calendar year across date lines that may omit it.

    Bounded by the file's own declared season-end year: a rollover is applied at most
    once, triggered either by an explicit year appearing on a date line (the real,
    observed convention in three of the four files) or, failing that, by the month
    sequence decreasing (2023/24's real convention — it never restates the year at all,
    not even at the Dec->Jan boundary).
    """

    def __init__(self, start_year: int, end_year: int):
        self._current_year = start_year
        self._end_year = end_year
        self._rolled_over = False
        self._previous_month: int | None = None

    def resolve(self, month: int, explicit_year: int | None) -> int:
        if explicit_year is not None:
            self._current_year = explicit_year
            self._rolled_over = True  # an explicit year is authoritative either way
        elif (
            self._previous_month is not None
            and month < self._previous_month
            and not self._rolled_over
        ):
            self._current_year = self._end_year
            self._rolled_over = True
        self._previous_month = month
        return self._current_year


def _parse_v_literal(
    text: str,
    competition: str,
    season: str,
    as_of_date: date,
    season_start: date,
    season_end: date,
) -> tuple[list[MatchRecord], list[QuarantinedLine]]:
    year_tracker = _YearTracker(season_start.year, season_end.year)
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
            current_date, problem = _resolve_date_line(date_m, year_tracker)
            if problem:
                quarantined.append(QuarantinedLine(line_no, raw_line, problem))
                current_date = None
            continue

        if " v " in line:
            if current_date is None:
                quarantined.append(
                    QuarantinedLine(line_no, raw_line, "fixture line before any date header")
                )
                continue
            record = _parse_v_literal_fixture_line(
                line, line_no, competition, season, current_date, current_round_label, as_of_date
            )
            if record is None:
                quarantined.append(QuarantinedLine(line_no, raw_line, "fixture line did not parse"))
            else:
                records.append(record)
            continue

        quarantined.append(QuarantinedLine(line_no, raw_line, "unmatched line"))

    return records, quarantined


def _resolve_date_line(date_m: re.Match, year_tracker: _YearTracker) -> tuple[date | None, str]:
    month_abbr, day_str, year_str = date_m.groups()
    month = _MONTHS.get(month_abbr)
    if month is None:
        return None, f"unrecognised month {month_abbr!r}"
    year = year_tracker.resolve(month, int(year_str) if year_str else None)
    try:
        return date(year, month, int(day_str)), ""
    except ValueError as exc:
        return None, f"invalid date: {exc}"


def _parse_v_literal_fixture_line(
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

    status = _derive_status(home_score, match_date, as_of_date)
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


def _derive_status(home_score: int | None, match_date: date, as_of_date: date) -> str:
    if home_score is not None:
        return "played_with_score"
    if match_date < as_of_date:
        return "result_missing"
    return "scheduled_future"


# --- score-between-teams sub-formats (2023/24, 2025/26) ----------------------------


def _parse_score_between(
    text: str,
    competition: str,
    season: str,
    as_of_date: date,
    season_start: date,
    season_end: date,
) -> tuple[list[MatchRecord], list[QuarantinedLine]]:
    year_tracker = _YearTracker(season_start.year, season_end.year)
    current_date: date | None = None
    current_round_label = ""
    records: list[MatchRecord] = []
    quarantined: list[QuarantinedLine] = []

    lines = text.splitlines()
    line_no = 0
    n = len(lines)
    while line_no < n:
        raw_line = lines[line_no]
        line_no += 1
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
            current_date, problem = _resolve_date_line(date_m, year_tracker)
            if problem:
                quarantined.append(QuarantinedLine(line_no, raw_line, problem))
                current_date = None
            continue

        if stripped.startswith("("):
            # A scorer-annotation block: consume this line and, if the parentheses are
            # not yet balanced, every following line until they are. These lines never
            # produce a fixture, a score, or any other feature.
            balance = stripped.count("(") - stripped.count(")")
            block_start = line_no
            while balance > 0 and line_no < n:
                next_line = lines[line_no]
                line_no += 1
                balance += next_line.count("(") - next_line.count(")")
            if balance != 0:
                quarantined.append(
                    QuarantinedLine(block_start, raw_line, "unterminated scorer-annotation block")
                )
            continue

        if _EMBEDDED_SCORE_RE.search(stripped):
            if current_date is None:
                quarantined.append(
                    QuarantinedLine(line_no, raw_line, "fixture line before any date header")
                )
                continue
            record = _parse_score_between_fixture_line(
                line, line_no, competition, season, current_date, current_round_label, as_of_date
            )
            if record is None:
                quarantined.append(QuarantinedLine(line_no, raw_line, "fixture line did not parse"))
            else:
                records.append(record)
            continue

        quarantined.append(QuarantinedLine(line_no, raw_line, "unmatched line"))

    return records, quarantined


def _parse_score_between_fixture_line(
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

    score_m = _EMBEDDED_SCORE_RE.search(rest)
    if not score_m:
        return None
    home_raw = rest[: score_m.start()].strip()
    away_raw = rest[score_m.end() :].strip()
    if not home_raw or not away_raw:
        return None

    home_score, away_score = int(score_m.group(1)), int(score_m.group(2))
    home_ht = int(score_m.group(3)) if score_m.group(3) is not None else None
    away_ht = int(score_m.group(4)) if score_m.group(4) is not None else None

    status = _derive_status(home_score, match_date, as_of_date)
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
