# Prosopographic Disambiguator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a weighted-scoring disambiguation engine that resolves ambiguous DPRR↔EDH person matches using filiation, career, geography, and temporal signals, exposed as an MCP tool and batch script.

**Architecture:** A core module `disambiguate.py` extracts context from EDH persons (name, filiation, office, dates, findspot), finds DPRR candidates by nomen, and scores each on 4 signals with weighted linear combination. Name parsing and Greek transliteration are extracted from existing scripts into a shared `onomastics.py` module. The server exposes a `disambiguate` tool; a batch script processes the 819 existing ambiguous candidates.

**Tech Stack:** pyoxigraph (SPARQL), pyyaml (linkage files), existing linked-past core modules (linkage, registry, store).

---

## File Structure

```
packages/linked-past/linked_past/core/
  onomastics.py          ← NEW: name parsing, Greek transliteration, praenomen maps (extracted from scripts/)
  disambiguate.py        ← NEW: PersonContext, PersonDisambiguator, extract_context(), 4 signal scorers
  server.py              ← MODIFY: register disambiguate tool

packages/linked-past/tests/
  test_onomastics.py     ← NEW: unit tests for name parsing + transliteration
  test_disambiguate.py   ← NEW: unit tests for signal scorers + integration test

scripts/
  match_dprr_edh.py      ← MODIFY: import from onomastics instead of inline definitions
  batch_disambiguate_edh.py ← NEW: batch process 819 ambiguous candidates
```

---

### Task 1: Extract name parsing into `onomastics.py`

**Files:**
- Create: `packages/linked-past/linked_past/core/onomastics.py`
- Create: `packages/linked-past/tests/test_onomastics.py`

- [ ] **Step 1: Write failing tests for name parsing and transliteration**

```python
"""Tests for Roman onomastics: name parsing, praenomen normalization, Greek transliteration."""

import pytest
from linked_past.core.onomastics import (
    normalize_praenomen,
    parse_roman_name,
    transliterate_greek,
    is_greek,
    parse_filiation,
    parse_office,
)


class TestNormalizePraenomen:
    def test_latin_abbreviated(self):
        assert normalize_praenomen("C.") == "gaius"
        assert normalize_praenomen("Cn.") == "gnaeus"
        assert normalize_praenomen("M'.") == "manius"

    def test_latin_without_dot(self):
        assert normalize_praenomen("L") == "lucius"

    def test_greek_full(self):
        assert normalize_praenomen("Γάιος") == "gaius"
        assert normalize_praenomen("Λεύκιος") == "lucius"
        assert normalize_praenomen("Κόιντος") == "quintus"

    def test_unknown_returns_none(self):
        assert normalize_praenomen("Flavius") is None


class TestParseRomanName:
    def test_tria_nomina(self):
        result = parse_roman_name("P. Cornelius Scipio")
        assert result["praenomen"] == "publius"
        assert result["nomen"] == "Cornelius"
        assert result["cognomen"] == "Scipio"

    def test_nomen_only(self):
        result = parse_roman_name("Cornelius")
        assert result.get("praenomen") is None
        assert result["nomen"] == "Cornelius"

    def test_with_filiation_skipped(self):
        result = parse_roman_name("L. Aquillius M. f. M. n. Florus")
        assert result["praenomen"] == "lucius"
        assert result["nomen"] == "Aquillius"
        assert result["cognomen"] == "Florus"

    def test_dprr_label_format(self):
        result = parse_roman_name("AQUI1614 M'. Aquillius (10) M'. f. M'. n.", is_dprr=True)
        assert result["praenomen"] == "manius"
        assert result["nomen"] == "Aquillius"


class TestTransliterateGreek:
    def test_basic(self):
        assert transliterate_greek("Μάρκος") == "marcus"

    def test_kappa_to_c(self):
        result = transliterate_greek("Κόιντος")
        assert result.startswith("c")  # κ → c

    def test_aquillius(self):
        result = transliterate_greek("Ἀκύλλιος")
        assert "acull" in result or "aqull" in result  # κυ → cu, λλ → ll

    def test_latin_passthrough(self):
        assert transliterate_greek("P. Cornelius") == "P. Cornelius"

    def test_not_greek(self):
        assert not is_greek("Cornelius Scipio")

    def test_is_greek(self):
        assert is_greek("Κορνήλιος")


class TestParseFiliation:
    def test_father_and_grandfather(self):
        result = parse_filiation("M. f. Cn. n.")
        assert result == {"father": "marcus", "grandfather": "gnaeus"}

    def test_father_only(self):
        result = parse_filiation("L. f.")
        assert result == {"father": "lucius"}

    def test_manius_filiation(self):
        result = parse_filiation("M'. f. M'. n.")
        assert result == {"father": "manius", "grandfather": "manius"}

    def test_no_filiation(self):
        result = parse_filiation("consul designatus")
        assert result == {}

    def test_from_inscription_text(self):
        text = "L. Aquillius M'. f. M'. n. Florus q. restituit"
        result = parse_filiation(text)
        assert result["father"] == "manius"


class TestParseOffice:
    def test_consul(self):
        assert parse_office("M. Aquillius cos.") == "consul"

    def test_praetor(self):
        assert parse_office("C. Sempronius pr.") == "praetor"

    def test_quaestor(self):
        assert parse_office("L. Aquillius q. restituit") == "quaestor"

    def test_tribunus_plebis(self):
        assert parse_office("tr. pl.") == "tribunus plebis"

    def test_proconsul(self):
        assert parse_office("procos.") == "proconsul"

    def test_no_office(self):
        assert parse_office("L. Aquillius Florus") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/linked-past/tests/test_onomastics.py -v`
Expected: FAIL — module `linked_past.core.onomastics` does not exist.

- [ ] **Step 3: Implement `onomastics.py`**

Create `packages/linked-past/linked_past/core/onomastics.py`. Extract and consolidate the following from `scripts/match_dprr_edh.py`:
- `_PRAENOMEN_MAP` → `PRAENOMEN_MAP` (public)
- `_GREEK_PRAENOMINA` → `GREEK_PRAENOMINA` (public)
- `_GREEK_DIGRAPHS`, `_GREEK_SINGLE`, `_GREEK_ENDINGS` → module-level constants
- `transliterate_greek()`, `_is_greek()` → `transliterate_greek()`, `is_greek()` (public)
- `_strip_accents()` → `strip_accents()` (public)
- `_parse_roman_name()` → `parse_roman_name()` (public, with `is_dprr` parameter)

Add two new functions:

```python
def normalize_praenomen(token: str) -> str | None:
    """Normalize a praenomen token (Latin or Greek) to canonical lowercase form."""
    token_lower = token.lower().rstrip(".")
    token_with_dot = token.lower()
    # Try Latin map
    result = PRAENOMEN_MAP.get(token_with_dot) or PRAENOMEN_MAP.get(token_lower)
    if result:
        return result
    # Try Greek map (strip accents first)
    stripped = strip_accents(token_lower)
    return GREEK_PRAENOMINA.get(stripped) or GREEK_PRAENOMINA.get(token_lower)


def parse_filiation(text: str) -> dict[str, str]:
    """Extract filiation from inscription text. Returns {father: praenomen, grandfather: praenomen}."""
    result = {}
    # Match "X. f." or "X'. f." for father
    father_match = re.search(r"(\w+['.]*)\.\s*f\.", text)
    if father_match:
        prae = normalize_praenomen(father_match.group(1) + ".")
        if prae:
            result["father"] = prae
    # Match "X. n." or "X'. n." for grandfather
    grandfather_match = re.search(r"(\w+['.]*)\.\s*n\.", text)
    if grandfather_match:
        prae = normalize_praenomen(grandfather_match.group(1) + ".")
        if prae:
            result["grandfather"] = prae
    return result


def parse_office(text: str) -> str | None:
    """Extract the highest office mentioned in inscription text."""
    patterns = [
        (r"\bcos\b\.?", "consul"),
        (r"\bprocos\b\.?", "proconsul"),
        (r"\bpr\b\.(?!\s*q)", "praetor"),  # pr. but not pr. q. (proquaestor)
        (r"\btr\.\s*pl\b\.?", "tribunus plebis"),
        (r"\baed\b\.?", "aedilis"),
        (r"(?<!\w)q\.\s*(?:restituit|designat|pro\b|urbana)", "quaestor"),  # q. followed by role context
        (r"\bquaestor\b", "quaestor"),  # full word
        (r"\bleg\b\.?", "legatus"),
        (r"\bpropr\b\.?", "propraetor"),
    ]
    for pattern, office in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return office
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/linked-past/tests/test_onomastics.py -v`
Expected: All tests PASS.

- [ ] **Step 5: Update `match_dprr_edh.py` to import from onomastics**

Replace the inline `_PRAENOMEN_MAP`, `_GREEK_PRAENOMINA`, `_GREEK_DIGRAPHS`, `_GREEK_SINGLE`, `_GREEK_ENDINGS`, `transliterate_greek`, `_is_greek`, `_strip_accents`, `_parse_roman_name`, `_normalize_edh_name` definitions in `scripts/match_dprr_edh.py` with imports from `linked_past.core.onomastics`. Keep the matching logic in the script; only the name-handling utilities move.

- [ ] **Step 6: Run existing tests + lint**

Run: `uv run pytest && uv run ruff check .`
Expected: All pass, no lint errors.

- [ ] **Step 7: Commit**

```bash
git add packages/linked-past/linked_past/core/onomastics.py packages/linked-past/tests/test_onomastics.py scripts/match_dprr_edh.py
git commit -m "refactor: extract name parsing + Greek transliteration into core onomastics module"
```

---

### Task 2: Implement temporal and career signal scorers

**Files:**
- Create: `packages/linked-past/linked_past/core/disambiguate.py`
- Create: `packages/linked-past/tests/test_disambiguate.py`

- [ ] **Step 1: Write failing tests for temporal and career scoring**

```python
"""Tests for prosopographic disambiguation signals."""

import pytest
from linked_past.core.disambiguate import (
    PersonContext,
    CandidateMatch,
    score_temporal,
    score_career,
)


class TestScoreTemporal:
    def test_midpoint_within_era(self):
        score, explanation, is_absent = score_temporal(era_from=-185, era_to=-129, date_start=-150, date_end=-140)
        assert score == 1.0
        assert not is_absent

    def test_partial_overlap(self):
        score, explanation, is_absent = score_temporal(era_from=-100, era_to=0, date_start=0, date_end=50)
        assert score == 0.5
        assert not is_absent

    def test_no_overlap(self):
        score, explanation, is_absent = score_temporal(era_from=-300, era_to=-200, date_start=100, date_end=150)
        assert score == 0.0
        assert not is_absent

    def test_no_inscription_date(self):
        score, explanation, is_absent = score_temporal(era_from=-185, era_to=-129, date_start=None, date_end=None)
        assert score == 0.0
        assert is_absent

    def test_no_era_data(self):
        score, explanation, is_absent = score_temporal(era_from=None, era_to=None, date_start=-147, date_end=-140)
        assert score == 0.0
        assert is_absent


class TestScoreCareer:
    def test_exact_office_and_date(self):
        offices = [{"office": "Office: consul", "date_start": -147}]
        score, explanation, is_absent = score_career(offices, era_from=-185, office="consul", date=-147)
        assert score == 1.0
        assert not is_absent

    def test_office_match_close_date(self):
        offices = [{"office": "Office: consul", "date_start": -147}]
        score, explanation, is_absent = score_career(offices, era_from=-185, office="consul", date=-140)
        assert score == 0.7

    def test_office_match_no_date(self):
        offices = [{"office": "Office: consul", "date_start": -147}]
        score, explanation, is_absent = score_career(offices, era_from=-185, office="consul", date=None)
        assert score == 0.5

    def test_office_not_held(self):
        offices = [{"office": "Office: praetor", "date_start": -150}]
        score, explanation, is_absent = score_career(offices, era_from=-185, office="consul", date=-147)
        assert score == 0.3

    def test_cursus_age_violation(self):
        offices = [{"office": "Office: consul", "date_start": -130}]
        score, explanation, is_absent = score_career(offices, era_from=-150, office="consul", date=-130)
        assert score == 0.0

    def test_office_before_birth(self):
        offices = [{"office": "Office: consul", "date_start": -200}]
        score, explanation, is_absent = score_career(offices, era_from=-150, office="consul", date=-200)
        assert score == 0.0
        assert "before birth" in explanation or "impossible" in explanation

    def test_no_office_in_inscription(self):
        offices = [{"office": "Office: consul", "date_start": -147}]
        score, explanation, is_absent = score_career(offices, era_from=-185, office=None, date=None)
        assert score == 0.0
        assert is_absent

    def test_no_dprr_offices(self):
        score, explanation, is_absent = score_career([], era_from=-185, office="consul", date=-147)
        assert score == 0.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/linked-past/tests/test_disambiguate.py::TestScoreTemporal -v`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement dataclasses and temporal/career scorers**

Create `packages/linked-past/linked_past/core/disambiguate.py`:

```python
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
        mid = date_end

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

    # Normalize office name for comparison
    office_label = f"Office: {office}"

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
        return 0.0, f"no offices recorded", False

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/linked-past/tests/test_disambiguate.py -v`
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/linked-past/linked_past/core/disambiguate.py packages/linked-past/tests/test_disambiguate.py
git commit -m "feat: add PersonContext, temporal and career signal scorers"
```

---

### Task 3: Implement filiation signal scorer

**Files:**
- Modify: `packages/linked-past/linked_past/core/disambiguate.py`
- Modify: `packages/linked-past/tests/test_disambiguate.py`

- [ ] **Step 1: Write failing test for filiation scoring**

Add to `test_disambiguate.py`:

```python
from linked_past.core.disambiguate import score_filiation


class TestScoreFiliation:
    def test_father_and_grandfather_match(self):
        family = {"father_praenomen": "manius", "grandfather_praenomen": "manius"}
        score, explanation, is_absent = score_filiation(family, {"father": "manius", "grandfather": "manius"})
        assert score == 1.0
        assert not is_absent

    def test_father_match_only(self):
        family = {"father_praenomen": "lucius", "grandfather_praenomen": None}
        score, explanation, is_absent = score_filiation(family, {"father": "lucius"})
        assert score == 0.5

    def test_father_mismatch(self):
        family = {"father_praenomen": "marcus", "grandfather_praenomen": None}
        score, explanation, is_absent = score_filiation(family, {"father": "lucius"})
        assert score == 0.0
        assert not is_absent  # data present, just doesn't match

    def test_no_filiation_data(self):
        family = {"father_praenomen": "marcus", "grandfather_praenomen": None}
        score, explanation, is_absent = score_filiation(family, {})
        assert score == 0.0
        assert is_absent

    def test_no_family_data(self):
        family = {}
        score, explanation, is_absent = score_filiation(family, {"father": "marcus"})
        assert score == 0.0
        assert is_absent
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/linked-past/tests/test_disambiguate.py::TestScoreFiliation -v`
Expected: FAIL — `score_filiation` not defined.

- [ ] **Step 3: Implement `score_filiation`**

Add to `disambiguate.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/linked-past/tests/test_disambiguate.py -v`
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/linked-past/linked_past/core/disambiguate.py packages/linked-past/tests/test_disambiguate.py
git commit -m "feat: add filiation signal scorer"
```

---

### Task 4: Implement geography signal scorer

**Files:**
- Modify: `packages/linked-past/linked_past/core/disambiguate.py`
- Modify: `packages/linked-past/tests/test_disambiguate.py`

- [ ] **Step 1: Write failing test for geography scoring**

Add to `test_disambiguate.py`:

```python
from linked_past.core.disambiguate import score_geography


class TestScoreGeography:
    def test_province_match(self):
        provinces = ["https://pleiades.stoa.org/places/837#this"]
        score, explanation, is_absent = score_geography(provinces, "https://pleiades.stoa.org/places/837#this")
        assert score == 1.0
        assert not is_absent

    def test_no_match(self):
        provinces = ["https://pleiades.stoa.org/places/775#this"]  # Africa
        score, explanation, is_absent = score_geography(provinces, "https://pleiades.stoa.org/places/837#this")  # Asia
        assert score == 0.0
        assert not is_absent  # data present, just doesn't match

    def test_no_findspot(self):
        provinces = ["https://pleiades.stoa.org/places/837#this"]
        score, explanation, is_absent = score_geography(provinces, None)
        assert score == 0.0
        assert is_absent

    def test_no_provinces(self):
        score, explanation, is_absent = score_geography([], "https://pleiades.stoa.org/places/837#this")
        assert score == 0.0
        assert is_absent

    def test_italy_fallback(self):
        score, explanation, is_absent = score_geography([], None, is_italian_findspot=True, has_italian_career=True)
        assert score == 0.0  # no findspot URI → absent
        assert is_absent

    def test_italy_career_italian_findspot(self):
        score, explanation, is_absent = score_geography(
            [], "https://pleiades.stoa.org/places/423025#this",
            is_italian_findspot=True, has_italian_career=True,
        )
        assert score == 0.3
        assert not is_absent
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/linked-past/tests/test_disambiguate.py::TestScoreGeography -v`
Expected: FAIL.

- [ ] **Step 3: Implement `score_geography`**

Add to `disambiguate.py`:

```python
def score_geography(
    dprr_province_pleiades_uris: list[str],
    findspot_pleiades_uri: str | None,
    is_italian_findspot: bool = False,
    has_italian_career: bool = False,
) -> tuple[float, str, bool]:
    """Score geographic match between DPRR provincial posts and inscription findspot.
    Returns (score, explanation, is_absent).

    dprr_province_pleiades_uris: Pleiades URIs for provinces where DPRR person served
    findspot_pleiades_uri: Pleiades URI for the inscription's findspot
    is_italian_findspot: True if findspot is in Italia/Rome/Italian region
    has_italian_career: True if DPRR person held posts in Italia/Rome
    """
    if not findspot_pleiades_uri:
        return 0.0, "no findspot data", True
    if not dprr_province_pleiades_uris:
        # No provincial posts — check Italy fallback
        if is_italian_findspot and has_italian_career:
            return 0.3, "Italy-based career + Italian findspot", False
        return 0.0, "no provincial posts recorded", True

    if findspot_pleiades_uri in dprr_province_pleiades_uris:
        return 1.0, f"findspot matches provincial post ({findspot_pleiades_uri})", False

    # Check Italy fallback
    if is_italian_findspot and has_italian_career:
        return 0.3, "Italy-based career + Italian findspot (no provincial match)", False

    return 0.0, f"findspot {findspot_pleiades_uri} not in served provinces", False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/linked-past/tests/test_disambiguate.py -v`
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/linked-past/linked_past/core/disambiguate.py packages/linked-past/tests/test_disambiguate.py
git commit -m "feat: add geography signal scorer"
```

---

### Task 5: Implement PersonDisambiguator orchestrator

**Files:**
- Modify: `packages/linked-past/linked_past/core/disambiguate.py`
- Modify: `packages/linked-past/tests/test_disambiguate.py`

- [ ] **Step 1: Write failing integration test**

Add to `test_disambiguate.py`:

```python
from linked_past.core.disambiguate import PersonDisambiguator, PersonContext, SignalResult


class TestPersonDisambiguator:
    def test_weighted_combination(self):
        """Test that the orchestrator combines signal scores correctly."""
        disambiguator = PersonDisambiguator()

        # Candidate A: filiation match + career match
        signals_a = {
            "filiation": SignalResult(1.0, 0.4, "father+grandfather match", False),
            "career": SignalResult(1.0, 0.3, "consul -147 confirmed", False),
            "geography": SignalResult(0.0, 0.2, "no findspot", True),
            "temporal": SignalResult(1.0, 0.1, "within era", False),
        }
        # Candidate B: only temporal overlap
        signals_b = {
            "filiation": SignalResult(0.0, 0.4, "father mismatch", False),
            "career": SignalResult(0.0, 0.3, "office not held", False),
            "geography": SignalResult(0.0, 0.2, "no findspot", True),
            "temporal": SignalResult(1.0, 0.1, "within era", False),
        }

        score_a = disambiguator._compute_weighted_score(signals_a)
        score_b = disambiguator._compute_weighted_score(signals_b)

        assert score_a > 0.7
        assert score_b < 0.2
        assert score_a > score_b

    def test_weight_redistribution_missing_signals(self):
        """When a signal has no data, its weight redistributes to others."""
        disambiguator = PersonDisambiguator()

        signals = {
            "filiation": SignalResult(0.0, 0.4, "no filiation", True),  # absent
            "career": SignalResult(1.0, 0.3, "consul confirmed", False),
            "geography": SignalResult(0.0, 0.2, "no findspot", True),  # absent
            "temporal": SignalResult(1.0, 0.1, "within era", False),
        }

        score = disambiguator._compute_weighted_score(signals)
        # career (0.3) + temporal (0.1) = 0.4 available → normalized to 1.0
        assert score == pytest.approx(1.0, abs=0.01)

    def test_all_signals_absent(self):
        """When all signals are absent, score is 0."""
        disambiguator = PersonDisambiguator()
        signals = {
            "filiation": SignalResult(0.0, 0.4, "absent", True),
            "career": SignalResult(0.0, 0.3, "absent", True),
            "geography": SignalResult(0.0, 0.2, "absent", True),
            "temporal": SignalResult(0.0, 0.1, "absent", True),
        }
        assert disambiguator._compute_weighted_score(signals) == 0.0

    def test_confidence_strong(self):
        assert PersonDisambiguator._classify_confidence(0.8, 0.3) == "strong"

    def test_confidence_probable(self):
        assert PersonDisambiguator._classify_confidence(0.6, 0.15) == "probable"

    def test_confidence_ambiguous(self):
        assert PersonDisambiguator._classify_confidence(0.4, 0.05) == "ambiguous"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/linked-past/tests/test_disambiguate.py::TestPersonDisambiguator -v`
Expected: FAIL.

- [ ] **Step 3: Implement `PersonDisambiguator`**

Add to `disambiguate.py`:

```python
class PersonDisambiguator:
    """Scores DPRR person candidates against contextual evidence."""

    def _compute_weighted_score(self, signals: dict[str, SignalResult]) -> float:
        """Compute weighted score with redistribution for absent signals.

        Absent signals (is_absent=True) have their weight redistributed
        proportionally to present signals.
        """
        present_weight = 0.0
        weighted_sum = 0.0

        for sig in signals.values():
            if not sig.is_absent:
                present_weight += sig.weight
                weighted_sum += sig.weight * sig.score

        if present_weight == 0.0:
            return 0.0
        return weighted_sum / present_weight

    @staticmethod
    def _classify_confidence(top_score: float, gap: float) -> str:
        """Classify match confidence based on top score and gap to next candidate."""
        if top_score >= 0.7 and gap >= 0.2:
            return "strong"
        elif top_score >= 0.5 and gap >= 0.1:
            return "probable"
        return "ambiguous"

    def rank_candidates(
        self,
        candidates_signals: list[tuple[str, str, dict[str, SignalResult]]],
    ) -> list[CandidateMatch]:
        """Rank candidates by weighted score.

        candidates_signals: list of (dprr_uri, dprr_label, signals_dict)
        """
        scored = []
        for dprr_uri, dprr_label, signals in candidates_signals:
            score = self._compute_weighted_score(signals)
            scored.append((score, dprr_uri, dprr_label, signals))

        scored.sort(key=lambda x: -x[0])

        results = []
        for i, (score, uri, label, signals) in enumerate(scored):
            gap = score - scored[i + 1][0] if i + 1 < len(scored) else score
            confidence = self._classify_confidence(score, gap)
            results.append(CandidateMatch(
                dprr_uri=uri,
                dprr_label=label,
                score=score,
                confidence=confidence,
                signals=signals,
            ))

        return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/linked-past/tests/test_disambiguate.py -v`
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/linked-past/linked_past/core/disambiguate.py packages/linked-past/tests/test_disambiguate.py
git commit -m "feat: add PersonDisambiguator orchestrator with weighted scoring"
```

---

### Task 6: Implement context extraction and SPARQL data fetching

**Files:**
- Modify: `packages/linked-past/linked_past/core/disambiguate.py`
- Modify: `packages/linked-past/tests/test_disambiguate.py`

- [ ] **Step 1: Write failing test for context extraction**

Add to `test_disambiguate.py`:

```python
from linked_past.core.disambiguate import extract_context_from_fields


class TestExtractContext:
    def test_from_fields_basic(self):
        ctx = extract_context_from_fields(
            name="P. Cornelius Scipio",
            filiation="P. f. Cn. n.",
            office="cos.",
            date=-147,
        )
        assert ctx.praenomen == "publius"
        assert ctx.nomen == "Cornelius"
        assert ctx.cognomen == "Scipio"
        assert ctx.filiation == "P. f. Cn. n."
        assert ctx.office == "consul"
        assert ctx.date_start == -147

    def test_from_fields_greek_name(self):
        ctx = extract_context_from_fields(name="Κ. Ἀνχάριος")
        assert ctx.praenomen == "quintus" or ctx.praenomen == "gaius"  # κ → c → gaius
        assert "ancharius" in ctx.normalized_name.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/linked-past/tests/test_disambiguate.py::TestExtractContext -v`
Expected: FAIL.

- [ ] **Step 3: Implement `extract_context_from_fields` and SPARQL helpers**

Add to `disambiguate.py`:

```python
from linked_past.core.onomastics import (
    is_greek,
    normalize_praenomen,
    parse_filiation,
    parse_office,
    parse_roman_name,
    transliterate_greek,
)


def extract_context_from_fields(
    name: str,
    filiation: str | None = None,
    office: str | None = None,
    date: int | None = None,
    province: str | None = None,
    uri: str | None = None,
) -> PersonContext:
    """Build PersonContext from manually provided fields."""
    if is_greek(name):
        normalized = transliterate_greek(name)
    else:
        normalized = name

    parsed = parse_roman_name(normalized)
    parsed_office = parse_office(office) if office else None

    return PersonContext(
        name=name,
        normalized_name=normalized,
        praenomen=parsed.get("praenomen"),
        nomen=parsed.get("nomen"),
        cognomen=parsed.get("cognomen"),
        filiation=filiation,
        office=parsed_office,
        date_start=date,
        date_end=date,
        findspot_uri=province,
        source_uri=uri,
    )


def fetch_dprr_candidates(dprr_store, nomen: str) -> list[dict]:
    """Find DPRR persons matching a nomen. Returns list of person dicts."""
    from linked_past.core.store import execute_query

    sparql = f"""
    PREFIX vocab: <http://romanrepublic.ac.uk/rdf/ontology#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT DISTINCT ?person ?label ?nomen ?cognomen ?praenomenLabel
           ?eraFrom ?eraTo WHERE {{
      ?person a vocab:Person ;
              vocab:hasPersonName ?label ;
              vocab:hasNomen ?nomen .
      FILTER(LCASE(?nomen) = "{nomen.lower()}")
      OPTIONAL {{ ?person vocab:hasCognomen ?cognomen }}
      OPTIONAL {{ ?person vocab:hasPraenomen ?prae . ?prae rdfs:label ?praenomenLabel }}
      OPTIONAL {{ ?person vocab:hasEraFrom ?eraFrom }}
      OPTIONAL {{ ?person vocab:hasEraTo ?eraTo }}
    }}
    """
    return execute_query(dprr_store, sparql)


def fetch_dprr_offices(dprr_store, person_uri: str) -> list[dict]:
    """Get all offices held by a DPRR person."""
    from linked_past.core.store import execute_query

    sparql = f"""
    PREFIX vocab: <http://romanrepublic.ac.uk/rdf/ontology#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?officeName ?dateStart WHERE {{
      ?pa a vocab:PostAssertion ;
          vocab:isAboutPerson <{person_uri}> ;
          vocab:hasOffice ?office .
      ?office rdfs:label ?officeName .
      OPTIONAL {{ ?pa vocab:hasDateStart ?dateStart }}
    }}
    """
    rows = execute_query(dprr_store, sparql)
    return [{
        "office": r.get("officeName", ""),
        "date_start": int(r["dateStart"]) if r.get("dateStart") else None,
    } for r in rows]


def fetch_dprr_family(dprr_store, person_uri: str) -> dict[str, str | None]:
    """Get father's and grandfather's praenomina for a DPRR person.

    Chains RelationshipAssertions: person ← father of ← father → father of → grandfather.
    """
    from linked_past.core.store import execute_query

    # Query for father AND grandfather in one SPARQL query using property path chaining
    sparql = f"""
    PREFIX vocab: <http://romanrepublic.ac.uk/rdf/ontology#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?fatherPrae ?grandfatherPrae WHERE {{
      # Find father: someone whose "father of" relationship points to person_uri
      ?ra1 a vocab:RelationshipAssertion ;
           vocab:isAboutPerson ?father ;
           vocab:hasRelatedPerson <{person_uri}> ;
           vocab:hasRelationship ?rel1 .
      ?rel1 rdfs:label "Relationship: father of" .
      ?father vocab:hasPraenomen ?fprae .
      ?fprae rdfs:label ?fatherPrae .

      # Find grandfather: someone whose "father of" relationship points to father
      OPTIONAL {{
        ?ra2 a vocab:RelationshipAssertion ;
             vocab:isAboutPerson ?grandfather ;
             vocab:hasRelatedPerson ?father ;
             vocab:hasRelationship ?rel2 .
        ?rel2 rdfs:label "Relationship: father of" .
        ?grandfather vocab:hasPraenomen ?gprae .
        ?gprae rdfs:label ?grandfatherPrae .
      }}
    }}
    LIMIT 1
    """
    rows = execute_query(dprr_store, sparql)
    result: dict[str, str | None] = {"father_praenomen": None, "grandfather_praenomen": None}
    for r in rows:
        father_label = r.get("fatherPrae", "")
        if father_label:
            result["father_praenomen"] = normalize_praenomen(father_label.replace("Praenomen: ", ""))
        grandfather_label = r.get("grandfatherPrae", "")
        if grandfather_label:
            result["grandfather_praenomen"] = normalize_praenomen(grandfather_label.replace("Praenomen: ", ""))
    return result


def fetch_dprr_province_pleiades(dprr_store, linkage, person_uri: str) -> list[str]:
    """Get Pleiades URIs for provinces where a DPRR person served."""
    from linked_past.core.store import execute_query

    sparql = f"""
    PREFIX vocab: <http://romanrepublic.ac.uk/rdf/ontology#>
    SELECT DISTINCT ?province WHERE {{
      ?pap a vocab:PostAssertionProvince ;
           vocab:hasPostAssertion ?pa ;
           vocab:hasProvince ?province .
      ?pa vocab:isAboutPerson <{person_uri}> .
    }}
    """
    rows = execute_query(dprr_store, sparql)
    pleiades_uris = []
    for r in rows:
        province_uri = r.get("province", "")
        if province_uri and linkage:
            links = linkage.find_links(province_uri)
            for link in links:
                target = link.get("target", "")
                if "pleiades.stoa.org" in target:
                    pleiades_uris.append(target)
    return pleiades_uris
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/linked-past/tests/test_disambiguate.py -v`
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/linked-past/linked_past/core/disambiguate.py packages/linked-past/tests/test_disambiguate.py
git commit -m "feat: add context extraction and SPARQL data fetchers for disambiguation"
```

---

### Task 6b: Implement `extract_context_from_edh_uri`

**Files:**
- Modify: `packages/linked-past/linked_past/core/disambiguate.py`
- Modify: `packages/linked-past/tests/test_disambiguate.py`

- [ ] **Step 1: Write failing test**

Add to `test_disambiguate.py`:

```python
from linked_past.core.disambiguate import extract_context_from_edh_uri


class TestExtractContextFromEDH:
    def test_returns_none_for_missing_uri(self):
        """With a mock empty store, extraction returns None."""
        from pyoxigraph import Store as OxStore
        store = OxStore()
        result = extract_context_from_edh_uri("https://example.org/nonexistent", store)
        assert result is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/linked-past/tests/test_disambiguate.py::TestExtractContextFromEDH -v`
Expected: FAIL — function not defined.

- [ ] **Step 3: Implement `extract_context_from_edh_uri`**

Add to `disambiguate.py`:

```python
def extract_context_from_edh_uri(uri: str, edh_store) -> PersonContext | None:
    """Extract a PersonContext from an EDH person URI by querying the EDH store.

    Fetches: name, inscription text (for filiation/office parsing), dates, findspot.
    """
    from linked_past.core.store import execute_query

    # Step 1: Get person name and attestation
    person_sparql = f"""
    PREFIX foaf: <http://xmlns.com/foaf/0.1/>
    PREFIX lawd: <http://lawd.info/ontology/>
    SELECT ?name ?att WHERE {{
      <{uri}> foaf:name ?name .
      OPTIONAL {{ <{uri}> lawd:hasAttestation ?att }}
    }}
    LIMIT 1
    """
    person_rows = execute_query(edh_store, person_sparql)
    if not person_rows:
        return None

    name = person_rows[0].get("name", "")
    att_uri = person_rows[0].get("att")

    # Step 2: Get inscription data from attestation
    edition_text = None
    date_start = None
    date_end = None
    findspot_uri = None

    if att_uri:
        # Extract inscription URI from attestation (remove /N#ref suffix)
        import re
        insc_uri = re.sub(r"/\d+#.*$", "", att_uri)

        insc_sparql = f"""
        PREFIX epi: <http://edh-www.adw.uni-heidelberg.de/lod/ontology#>
        PREFIX nmo: <http://nomisma.org/ontology#>
        PREFIX lawd: <http://lawd.info/ontology/1.0/>
        SELECT ?editionText ?startDate ?endDate ?foundAt WHERE {{
          <{insc_uri}> epi:editionText ?editionText .
          OPTIONAL {{ <{insc_uri}> nmo:hasStartDate ?startDate }}
          OPTIONAL {{ <{insc_uri}> nmo:hasEndDate ?endDate }}
          OPTIONAL {{ <{insc_uri}> lawd:foundAt ?foundAt }}
        }}
        LIMIT 1
        """
        insc_rows = execute_query(edh_store, insc_sparql)
        if insc_rows:
            edition_text = insc_rows[0].get("editionText")
            raw_start = insc_rows[0].get("startDate")
            raw_end = insc_rows[0].get("endDate")
            findspot_uri = insc_rows[0].get("foundAt")
            try:
                date_start = int(raw_start) if raw_start else None
            except (ValueError, TypeError):
                date_start = None
            try:
                date_end = int(raw_end) if raw_end else None
            except (ValueError, TypeError):
                date_end = None

    # Step 3: Parse name (with Greek transliteration)
    if is_greek(name):
        normalized = transliterate_greek(name)
    else:
        normalized = name

    parsed = parse_roman_name(normalized)

    # Step 4: Parse filiation and office from edition text
    filiation_str = None
    office_str = None
    if edition_text:
        filiation_str = edition_text  # parse_filiation will extract from full text
        office_str = parse_office(edition_text)

    return PersonContext(
        name=name,
        normalized_name=normalized,
        praenomen=parsed.get("praenomen"),
        nomen=parsed.get("nomen"),
        cognomen=parsed.get("cognomen"),
        filiation=filiation_str,
        office=office_str,
        date_start=date_start,
        date_end=date_end,
        findspot_uri=findspot_uri,
        source_uri=uri,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/linked-past/tests/test_disambiguate.py -v`
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/linked-past/linked_past/core/disambiguate.py packages/linked-past/tests/test_disambiguate.py
git commit -m "feat: add extract_context_from_edh_uri for automatic EDH context extraction"
```

---

### Task 7: Register MCP tool in server.py

**Files:**
- Modify: `packages/linked-past/linked_past/core/server.py`

- [ ] **Step 1: Add the disambiguate tool**

Add the following tool registration after the existing `find_links` tool in `server.py`. Follow the same pattern as `explore_entity` and `find_links`:

```python
@mcp.tool()
def disambiguate(
    ctx: Context,
    uri: str | None = None,
    name: str | None = None,
    filiation: str | None = None,
    office: str | None = None,
    date: int | None = None,
    province: str | None = None,
) -> str:
    """Disambiguate a person across datasets. Given an EDH person URI or a name with optional context (filiation, office, date, province), find and rank the most likely DPRR person match using prosopographic signals."""
    t0 = time.monotonic()
    app: AppContext = ctx.request_context.lifespan_context

    from linked_past.core.disambiguate import (
        PersonDisambiguator,
        SignalResult,
        extract_context_from_edh_uri,
        extract_context_from_fields,
        fetch_dprr_candidates,
        fetch_dprr_family,
        fetch_dprr_offices,
        fetch_dprr_province_pleiades,
        score_career,
        score_filiation,
        score_geography,
        score_temporal,
    )
    from linked_past.core.onomastics import normalize_praenomen, parse_filiation as parse_fil

    if not uri and not name:
        return "Error: provide either `uri` (EDH person URI) or `name`."

    # Build context
    if uri and not name:
        # Extract from EDH store
        try:
            edh_store = app.registry.get_store("edh")
        except KeyError:
            return "Error: EDH dataset not loaded."
        context = extract_context_from_edh_uri(uri, edh_store)
        if context is None:
            return f"Error: could not find EDH person at `{uri}`."
    else:
        context = extract_context_from_fields(
            name=name or "",
            filiation=filiation,
            office=office,
            date=date,
            province=province,
            uri=uri,
        )

    if not context.nomen:
        return f"Error: could not parse nomen from name '{name}'."

    # Find DPRR candidates by nomen
    dprr_store = app.registry.get_store("dprr")
    candidates = fetch_dprr_candidates(dprr_store, context.nomen)
    if not candidates:
        return f"No DPRR persons found with nomen '{context.nomen}'."

    # Parse inscription filiation
    insc_filiation = parse_fil(context.filiation) if context.filiation else {}

    # Score each candidate
    disambiguator = PersonDisambiguator()
    candidates_signals = []
    for cand in candidates:
        person_uri = cand["person"]
        label = cand.get("label", "")
        era_from = int(cand["eraFrom"]) if cand.get("eraFrom") else None
        era_to = int(cand["eraTo"]) if cand.get("eraTo") else None

        # Fetch per-candidate data
        offices = fetch_dprr_offices(dprr_store, person_uri)
        family = fetch_dprr_family(dprr_store, person_uri)
        province_uris = fetch_dprr_province_pleiades(dprr_store, app.linkage, person_uri)

        # Score signals
        fil_score, fil_expl, fil_absent = score_filiation(family, insc_filiation)
        car_score, car_expl, car_absent = score_career(offices, era_from, context.office, context.date_start)
        geo_score, geo_expl, geo_absent = score_geography(province_uris, context.findspot_uri)
        tmp_score, tmp_expl, tmp_absent = score_temporal(era_from, era_to, context.date_start, context.date_end)

        signals = {
            "filiation": SignalResult(fil_score, 0.4, fil_expl, fil_absent),
            "career": SignalResult(car_score, 0.3, car_expl, car_absent),
            "geography": SignalResult(geo_score, 0.2, geo_expl, geo_absent),
            "temporal": SignalResult(tmp_score, 0.1, tmp_expl, tmp_absent),
        }
        candidates_signals.append((person_uri, label, signals))

    ranked = disambiguator.rank_candidates(candidates_signals)

    # Format output
    lines = [f"# Disambiguation: {context.name}\n"]
    ctx_parts = []
    if context.office:
        ctx_parts.append(context.office)
    if context.filiation:
        ctx_parts.append(f"filiation {context.filiation}")
    if context.date_start:
        ctx_parts.append(f"date {context.date_start}")
    if ctx_parts:
        lines.append(f"Context: {', '.join(ctx_parts)}\n")

    lines.append(f"## Candidates ({len(ranked)})\n")

    for i, match in enumerate(ranked[:10]):
        lines.append(f"### {i+1}. {match.dprr_label} (score: {match.score:.2f})\n")
        for sig_name, sig in match.signals.items():
            lines.append(f"- {sig_name.title()}: **{sig.score * sig.weight:.2f}/{sig.weight:.1f}** — {sig.explanation}")
        lines.append(f"**Confidence: {match.confidence}**\n")

    if ranked:
        top = ranked[0]
        lines.append(f"## Recommendation\n")
        lines.append(f"{top.dprr_label} — {top.confidence} match (score {top.score:.2f}).")

    output = "\n".join(lines)
    _log_tool_call(app, "disambiguate", {"name": name, "uri": uri}, output, int((time.monotonic() - t0) * 1000))
    return output
```

- [ ] **Step 2: Update `test_server.py` to verify tool registration**

In `packages/linked-past/tests/test_server.py`, find the `test_create_mcp_server` test and add:

```python
assert "disambiguate" in tool_names
```

- [ ] **Step 3: Run the full test suite**

Run: `uv run pytest && uv run ruff check .`
Expected: All pass.

- [ ] **Step 4: Commit**

```bash
git add packages/linked-past/linked_past/core/server.py packages/linked-past/tests/test_server.py
git commit -m "feat: register disambiguate MCP tool"
```

---

### Task 7b: Aquillius golden integration test

**Files:**
- Modify: `packages/linked-past/tests/test_disambiguate.py`

- [ ] **Step 1: Write golden integration test using inline Turtle fixtures**

Add to `test_disambiguate.py` an `AQUILLIUS_TURTLE` fixture containing three Aquillii (Person/1614 cos. 129, Person/1757 cos. 101, Person/4686 quaestor c. 70) with RelationshipAssertions (1614 father of 1757, 1757 father of 4686) and PostAssertions (quaestor for 4686, consul for 1757). Use `pyoxigraph.Store` + `load_rdf()` for an ephemeral store.

Tests:
- `test_filiation_scores_1_for_florus` — verify `fetch_dprr_family(store, Person/4686)` returns father=manius, grandfather=manius, and `score_filiation` returns 1.0 for "M'. f. M'. n."
- `test_career_scores_for_quaestor` — verify Person/4686 scores ≥ 0.7 for quaestor office dated -70
- `test_florus_ranks_above_grandfather` — run full disambiguation with 3 Aquillii candidates, verify Person/4686 ranks #1

- [ ] **Step 2: Run test**

Run: `uv run pytest packages/linked-past/tests/test_disambiguate.py::TestAquilliusGoldenCase -v`
Expected: All 3 tests PASS.

- [ ] **Step 3: Commit**

```bash
git add packages/linked-past/tests/test_disambiguate.py
git commit -m "test: add Aquillius golden integration test for disambiguation engine"
```

---

### Task 8: Batch disambiguation script

**Files:**
- Create: `scripts/batch_disambiguate_edh.py`

- [ ] **Step 1: Write the batch script**

```python
"""Batch-process ambiguous DPRR↔EDH candidates through the disambiguation engine.

Usage:
    uv run python scripts/batch_disambiguate_edh.py
"""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

import yaml
from pyoxigraph import Store

from linked_past.core.disambiguate import (
    PersonDisambiguator,
    extract_context_from_fields,
    fetch_dprr_candidates,
    fetch_dprr_family,
    fetch_dprr_offices,
    fetch_dprr_province_pleiades,
    score_career,
    score_filiation,
    score_geography,
    score_temporal,
)
from linked_past.core.linkage import LinkageGraph
from linked_past.core.onomastics import normalize_praenomen, parse_filiation, parse_roman_name

# Thresholds (tunable)
CONFIRM_SCORE = 0.7
CONFIRM_GAP = 0.2
REVIEW_SCORE = 0.5

DATA_DIR = Path.home() / ".local" / "share" / "linked-past"
LINKAGE_DIR = Path(__file__).resolve().parents[1] / "packages" / "linked-past" / "linked_past" / "linkages"


def _open_store(dataset: str) -> Store:
    path = DATA_DIR / dataset / "store"
    return Store.read_only(str(path))


def _load_linkage() -> LinkageGraph:
    graph = LinkageGraph()
    for yaml_file in LINKAGE_DIR.glob("*.yaml"):
        graph.load_yaml(yaml_file)
    for rdf_file in (LINKAGE_DIR / "wikidata").glob("*.ttl"):
        graph.load_rdf_file(rdf_file)
    return graph


def main():
    print("Opening stores...")
    dprr_store = _open_store("dprr")
    edh_store = _open_store("edh")

    print("Loading linkage graph...")
    linkage = _load_linkage()

    # Load existing confirmed links
    conf_path = LINKAGE_DIR / "dprr_edh_confirmed.yaml"
    with conf_path.open() as f:
        conf_data = yaml.safe_load(f)
    existing = {(l["source"], l["target"]) for l in conf_data["links"]}
    print(f"  {len(existing)} existing confirmed links")

    # Get all name-matched candidates using the onomastics module
    # (replicates the matching logic from match_dprr_edh.py using shared utilities)
    from linked_past.core.onomastics import parse_roman_name, normalize_praenomen, is_greek, transliterate_greek
    from linked_past.core.store import execute_query
    import re

    # Query DPRR persons
    dprr_rows = execute_query(dprr_store, """
        PREFIX vocab: <http://romanrepublic.ac.uk/rdf/ontology#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT DISTINCT ?person ?label ?nomen ?cognomen ?praenomenLabel ?eraFrom ?eraTo WHERE {
          ?person a vocab:Person ; vocab:hasPersonName ?label ; vocab:hasNomen ?nomen .
          OPTIONAL { ?person vocab:hasCognomen ?cognomen }
          OPTIONAL { ?person vocab:hasPraenomen ?prae . ?prae rdfs:label ?praenomenLabel }
          OPTIONAL { ?person vocab:hasEraFrom ?eraFrom }
          OPTIONAL { ?person vocab:hasEraTo ?eraTo }
        }
    """)
    # Query EDH elite persons
    edh_rows = execute_query(edh_store, """
        PREFIX foaf: <http://xmlns.com/foaf/0.1/>
        SELECT ?person ?name WHERE {
          ?person a <http://lawd.info/ontology/Person> ; foaf:name ?name .
          FILTER EXISTS {
            ?person foaf:member ?s .
            FILTER(?s IN (
              <https://edh-www.adw.uni-heidelberg.de/edh/social_status/senatorial_order>,
              <https://edh-www.adw.uni-heidelberg.de/edh/social_status/equestrian_order>
            ))
          }
        }
    """)

    # Build nomen index and match (same logic as match_dprr_edh.py)
    dprr_by_nomen = defaultdict(list)
    for d in dprr_rows:
        nomen = re.sub(r"[()]", "", d.get("nomen", "")).strip().lower()
        if nomen and len(nomen) > 2:
            dprr_by_nomen[nomen].append(d)

    all_candidates = []
    for edh in edh_rows:
        name = edh.get("name", "")
        if not name or len(name) < 5:
            continue
        norm_name = transliterate_greek(name) if is_greek(name) else name
        parsed = parse_roman_name(norm_name)
        edh_nomen = (parsed.get("nomen") or "").lower()
        edh_cog = (parsed.get("cognomen") or "").lower()
        edh_prae = parsed.get("praenomen")
        if not edh_nomen or len(edh_nomen) < 3:
            continue
        for dprr in dprr_by_nomen.get(edh_nomen, []):
            dprr_prae_label = (dprr.get("praenomenLabel") or "").lower()
            dprr_prae = normalize_praenomen(dprr_prae_label.split(":")[-1].strip())
            dprr_cog = (dprr.get("cognomen") or "").lower().strip("() []")
            score = 1  # nomen
            if edh_prae and dprr_prae:
                if edh_prae == dprr_prae:
                    score += 2
                else:
                    continue
            if edh_cog and dprr_cog:
                if edh_cog == dprr_cog:
                    score += 2
                elif edh_cog in dprr_cog or dprr_cog in edh_cog:
                    score += 1
                else:
                    continue
            if score >= 5:
                all_candidates.append({
                    "dprr_uri": dprr["person"],
                    "edh_uri": edh["person"],
                    "dprr_label": dprr.get("label", ""),
                    "edh_name": name,
                    "dprr_era": f"{dprr.get('eraFrom', '?')} to {dprr.get('eraTo', '?')}",
                })

    # Filter to ambiguous only (not already confirmed, not 1:1)
    all_candidates = [c for c in all_candidates if (c["dprr_uri"], c["edh_uri"]) not in existing]
    dc = Counter(c["dprr_uri"] for c in all_candidates)
    ec = Counter(c["edh_uri"] for c in all_candidates)
    ambiguous = [c for c in all_candidates if dc[c["dprr_uri"]] > 1 or ec[c["edh_uri"]] > 1]
    print(f"  {len(ambiguous)} ambiguous candidates to process")

    # Group by EDH person
    by_edh: dict[str, list[dict]] = defaultdict(list)
    for c in ambiguous:
        by_edh[c["edh_uri"]].append(c)

    disambiguator = PersonDisambiguator()
    confirmed = []
    reviewed = []

    for edh_uri, group in by_edh.items():
        edh_name = group[0]["edh_name"]
        parsed = parse_roman_name(edh_name)

        # Build context from EDH name (basic — no inscription text parsing yet)
        context = extract_context_from_fields(name=edh_name)

        insc_filiation = parse_filiation(context.filiation) if context.filiation else {}

        # Score each DPRR candidate
        candidates_signals = []
        for cand in group:
            person_uri = cand["dprr_uri"]
            label = cand["dprr_label"]

            # Fetch data
            offices = fetch_dprr_offices(dprr_store, person_uri)
            family = fetch_dprr_family(dprr_store, person_uri)
            province_uris = fetch_dprr_province_pleiades(dprr_store, linkage, person_uri)

            era_from = None
            era_to = None
            # Extract era from the group data if available
            era_str = cand.get("dprr_era", "")
            if era_str and " to " in era_str:
                parts = era_str.split(" to ")
                try:
                    era_from = int(parts[0])
                    era_to = int(parts[1])
                except (ValueError, IndexError):
                    pass

            fil_score, fil_expl = score_filiation(family, insc_filiation)
            car_score, car_expl = score_career(offices, era_from, context.office, context.date_start)
            geo_score, geo_expl = score_geography(province_uris, context.findspot_uri)
            tmp_score, tmp_expl = score_temporal(era_from, era_to, context.date_start, context.date_end)

            signals = {
                "filiation": (fil_score, 0.4, fil_expl),
                "career": (car_score, 0.3, car_expl),
                "geography": (geo_score, 0.2, geo_expl),
                "temporal": (tmp_score, 0.1, tmp_expl),
            }
            candidates_signals.append((person_uri, label, signals))

        ranked = disambiguator.rank_candidates(candidates_signals)
        if not ranked:
            continue

        top = ranked[0]
        if top.confidence == "strong":
            confirmed.append({
                "source": top.dprr_uri,
                "target": edh_uri,
                "note": f"DPRR: {top.dprr_label[:60]}; EDH: {edh_name}; disambiguated (score {top.score:.2f}, {top.confidence})",
            })
        elif top.score >= REVIEW_SCORE:
            reviewed.append({
                "source": top.dprr_uri,
                "target": edh_uri,
                "score": top.score,
                "confidence": top.confidence,
                "dprr_label": top.dprr_label,
                "edh_name": edh_name,
            })

    print(f"\nResults:")
    print(f"  {len(confirmed)} confirmed (score >= {CONFIRM_SCORE}, gap >= {CONFIRM_GAP})")
    print(f"  {len(reviewed)} for review (score {REVIEW_SCORE}-{CONFIRM_SCORE})")

    # Append confirmed to file
    if confirmed:
        # Deduplicate against existing
        new_confirmed = [c for c in confirmed if (c["source"], c["target"]) not in existing]
        conf_data["links"].extend(new_confirmed)
        with conf_path.open("w") as f:
            yaml.dump(conf_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        print(f"  Added {len(new_confirmed)} new links to {conf_path}")
        print(f"  Total confirmed: {len(conf_data['links'])}")

    # Print review candidates
    if reviewed:
        print(f"\nTop review candidates:")
        for r in sorted(reviewed, key=lambda x: -x["score"])[:20]:
            print(f"  {r['score']:.2f} {r['confidence']:>10}  {r['dprr_label'][:45]:<45}  {r['edh_name'][:30]}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the batch script**

Run: `uv run python scripts/batch_disambiguate_edh.py`
Expected: Output showing how many candidates were confirmed vs. reviewed. The Aquillius case may not appear here (it was already manually confirmed), but other cases with filiation or career data in the inscription should score well.

- [ ] **Step 3: Run full test suite**

Run: `uv run pytest && uv run ruff check .`
Expected: All pass.

- [ ] **Step 4: Commit**

```bash
git add scripts/batch_disambiguate_edh.py packages/linked-past/linked_past/linkages/dprr_edh_confirmed.yaml
git commit -m "feat: batch disambiguation of ambiguous EDH candidates

Process 819 ambiguous DPRR↔EDH candidates through the weighted
scoring engine (filiation, career, geography, temporal signals).
Confirmed matches appended to dprr_edh_confirmed.yaml."
```
