"""Prosopographic disambiguation engine.

Scores DPRR person candidates against contextual evidence (filiation,
career, geography, temporal overlap) using weighted linear combination.
"""

from __future__ import annotations

from dataclasses import dataclass, field


WEIGHTS = {
    "filiation": 0.4,
    "career": 0.3,
    "geography": 0.2,
    "temporal": 0.1,
}

# Cursus honorum minimum ages (approximate)
_MIN_AGE_FOR_OFFICE = {
    "consul": 35,
    "praetor": 33,
    "aedilis": 30,
    "tribunus plebis": 27,
    "quaestor": 25,
    "legatus": 25,
    "proconsul": 35,
    "propraetor": 33,
}
_MAX_AGE = 80  # No one holds office after ~80


@dataclass
class PersonContext:
    name: str
    normalized_name: str
    praenomen: str | None = None
    nomen: str | None = None
    cognomen: str | None = None
    filiation: str | None = None
    office: str | None = None
    date_start: int | None = None
    date_end: int | None = None
    findspot_uri: str | None = None
    source_uri: str | None = None


@dataclass
class SignalResult:
    score: float        # 0.0–1.0
    weight: float       # from WEIGHTS dict
    explanation: str
    is_absent: bool     # True if signal has no data (weight redistributed)


@dataclass
class CandidateMatch:
    dprr_uri: str
    dprr_label: str
    score: float
    confidence: str  # "strong", "probable", "ambiguous"
    signals: dict[str, SignalResult] = field(default_factory=dict)


def score_temporal(
    era_from: int | None,
    era_to: int | None,
    date_start: int | None,
    date_end: int | None,
) -> tuple[float, str, bool]:
    """Score temporal overlap between DPRR era and inscription dates.
    Returns (score, explanation, is_absent).
    """
    if era_from is None and era_to is None:
        return 0.0, "no DPRR era data", True
    if date_start is None and date_end is None:
        return 0.0, "no inscription date", True

    # Use midpoint of inscription date range
    if date_start is not None and date_end is not None:
        mid = (date_start + date_end) / 2
    elif date_start is not None:
        mid = date_start
    else:
        mid = date_end  # type: ignore[assignment]

    e_from = era_from if era_from is not None else -500
    e_to = era_to if era_to is not None else 100

    if e_from <= mid <= e_to:
        return 1.0, f"inscription date {mid:.0f} within era {e_from}..{e_to}", False
    elif (date_start is not None and date_end is not None and
          not (date_end < e_from or date_start > e_to)):
        return 0.5, f"partial overlap: inscription {date_start}..{date_end}, era {e_from}..{e_to}", False
    else:
        return 0.0, f"no overlap: inscription ~{mid:.0f}, era {e_from}..{e_to}", False


def score_career(
    dprr_offices: list[dict],
    era_from: int | None,
    office: str | None,
    date: int | None,
) -> tuple[float, str, bool]:
    """Score career/office match between DPRR person and inscription evidence.
    Returns (score, explanation, is_absent).
    """
    if office is None:
        return 0.0, "no office in inscription", True

    # Check cursus age constraint
    if era_from is not None and date is not None:
        age_at_date = date - era_from  # positive = person alive; negative = office before birth
        if age_at_date < 0:
            return 0.0, f"impossible: office at {date} before birth ~{era_from}", False
        min_age = _MIN_AGE_FOR_OFFICE.get(office, 25)
        if age_at_date < min_age:
            return 0.0, f"cursus violation: age {age_at_date} at {date}, min {min_age} for {office}", False
        if age_at_date > _MAX_AGE:
            return 0.0, f"implausible: age {age_at_date} at {date}", False

    # Check if DPRR person held this office
    held_offices = [o for o in dprr_offices if office in o.get("office", "").lower()]
    if not held_offices:
        # Office not held — but if they held a higher office, career level is plausible
        any_offices = len(dprr_offices) > 0
        if any_offices:
            return 0.3, f"{office} not held, but career active", False
        return 0.0, "no offices recorded", False

    # Office held — check date proximity
    if date is None:
        return 0.5, f"{office} held (no inscription date to compare)", False

    closest = min(held_offices, key=lambda o: abs((o.get("date_start") or 0) - date))
    closest_date = closest.get("date_start")
    if closest_date is None:
        return 0.5, f"{office} held (no DPRR date to compare)", False

    gap = abs(closest_date - date)
    if gap <= 5:
        return 1.0, f"{office} held in {closest_date}, inscription {date} (±{gap}yr)", False
    elif gap <= 10:
        return 0.7, f"{office} held in {closest_date}, inscription {date} (±{gap}yr)", False
    elif gap <= 20:
        return 0.5, f"{office} held in {closest_date}, inscription {date} (±{gap}yr)", False
    else:
        return 0.3, f"{office} held in {closest_date}, inscription {date} (±{gap}yr, distant)", False


def score_filiation(
    dprr_family: dict[str, str | None],
    inscription_filiation: dict[str, str],
) -> tuple[float, str, bool]:
    """Score filiation match between DPRR family data and inscription filiation.
    Returns (score, explanation, is_absent).

    dprr_family: {"father_praenomen": "marcus", "grandfather_praenomen": "gnaeus"}
    inscription_filiation: {"father": "marcus", "grandfather": "gnaeus"} (from parse_filiation)
    """
    if not inscription_filiation:
        return 0.0, "no filiation in inscription", True
    if not dprr_family:
        return 0.0, "no family data in DPRR", True

    insc_father = inscription_filiation.get("father")
    insc_grandfather = inscription_filiation.get("grandfather")
    dprr_father = dprr_family.get("father_praenomen")
    dprr_grandfather = dprr_family.get("grandfather_praenomen")

    if not insc_father:
        return 0.0, "no father in filiation", True

    if not dprr_father:
        return 0.0, "DPRR father unknown", True

    if insc_father != dprr_father:
        return 0.0, f"father mismatch: inscription {insc_father}, DPRR {dprr_father}", False

    # Father matches
    if insc_grandfather and dprr_grandfather:
        if insc_grandfather == dprr_grandfather:
            return 1.0, f"father ({insc_father}) + grandfather ({insc_grandfather}) match", False
        else:
            return 0.0, f"grandfather mismatch: inscription {insc_grandfather}, DPRR {dprr_grandfather}", False

    return 0.5, f"father matches ({insc_father}), grandfather not verifiable", False
