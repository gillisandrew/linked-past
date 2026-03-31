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
        (r"\bq\b\.(?!\s*f)", "quaestor"),  # q. but not q. f. (which is filiation)
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
        # Inscription dated -147, person era -185 to -129
        score, explanation = score_temporal(era_from=-185, era_to=-129, date_start=-150, date_end=-140)
        assert score == 1.0

    def test_partial_overlap(self):
        # Inscription dated 0-50 AD, person era -100 to 0
        score, explanation = score_temporal(era_from=-100, era_to=0, date_start=0, date_end=50)
        assert score == 0.5

    def test_no_overlap(self):
        # Inscription dated 100 AD, person era -300 to -200
        score, explanation = score_temporal(era_from=-300, era_to=-200, date_start=100, date_end=150)
        assert score == 0.0

    def test_no_inscription_date(self):
        score, explanation = score_temporal(era_from=-185, era_to=-129, date_start=None, date_end=None)
        assert score == 0.0

    def test_no_era_data(self):
        score, explanation = score_temporal(era_from=None, era_to=None, date_start=-147, date_end=-140)
        assert score == 0.0


class TestScoreCareer:
    def test_exact_office_and_date(self):
        # Person held consulship in -147, inscription says cos. dated -147
        offices = [{"office": "Office: consul", "date_start": -147}]
        score, explanation = score_career(offices, era_from=-185, office="consul", date=-147)
        assert score == 1.0

    def test_office_match_close_date(self):
        # Person held consulship in -147, inscription dated -140
        offices = [{"office": "Office: consul", "date_start": -147}]
        score, explanation = score_career(offices, era_from=-185, office="consul", date=-140)
        assert score == 0.7

    def test_office_match_no_date(self):
        offices = [{"office": "Office: consul", "date_start": -147}]
        score, explanation = score_career(offices, era_from=-185, office="consul", date=None)
        assert score == 0.5

    def test_office_not_held(self):
        offices = [{"office": "Office: praetor", "date_start": -150}]
        score, explanation = score_career(offices, era_from=-185, office="consul", date=-147)
        assert score == 0.3  # career level plausible

    def test_cursus_age_violation(self):
        # Person born -150, consul inscription dated -130 — age 20, impossible
        offices = [{"office": "Office: consul", "date_start": -130}]
        score, explanation = score_career(offices, era_from=-150, office="consul", date=-130)
        assert score == 0.0  # too young

    def test_no_office_in_inscription(self):
        offices = [{"office": "Office: consul", "date_start": -147}]
        score, explanation = score_career(offices, era_from=-185, office=None, date=None)
        assert score == 0.0  # signal absent

    def test_no_dprr_offices(self):
        score, explanation = score_career([], era_from=-185, office="consul", date=-147)
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
class CandidateMatch:
    dprr_uri: str
    dprr_label: str
    score: float
    confidence: str  # "strong", "probable", "ambiguous"
    signals: dict[str, tuple[float, float, str]] = field(default_factory=dict)
    # signal_name → (score, max_weight, explanation)


def score_temporal(
    era_from: int | None,
    era_to: int | None,
    date_start: int | None,
    date_end: int | None,
) -> tuple[float, str]:
    """Score temporal overlap between DPRR era and inscription dates."""
    if era_from is None and era_to is None:
        return 0.0, "no DPRR era data"
    if date_start is None and date_end is None:
        return 0.0, "no inscription date"

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
        return 1.0, f"inscription date {mid:.0f} within era {e_from}..{e_to}"
    elif (date_start is not None and date_end is not None and
          not (date_end < e_from or date_start > e_to)):
        return 0.5, f"partial overlap: inscription {date_start}..{date_end}, era {e_from}..{e_to}"
    else:
        return 0.0, f"no overlap: inscription ~{mid:.0f}, era {e_from}..{e_to}"


def score_career(
    dprr_offices: list[dict],
    era_from: int | None,
    office: str | None,
    date: int | None,
) -> tuple[float, str]:
    """Score career/office match between DPRR person and inscription evidence."""
    if office is None:
        return 0.0, "no office in inscription"

    # Normalize office name for comparison
    office_label = f"Office: {office}"

    # Check cursus age constraint
    if era_from is not None and date is not None:
        age_at_date = abs(date - era_from)
        min_age = _MIN_AGE_FOR_OFFICE.get(office, 25)
        if age_at_date < min_age:
            return 0.0, f"cursus violation: age {age_at_date} at {date}, min {min_age} for {office}"
        if age_at_date > _MAX_AGE:
            return 0.0, f"implausible: age {age_at_date} at {date}"

    # Check if DPRR person held this office
    held_offices = [o for o in dprr_offices if office in o.get("office", "").lower()]
    if not held_offices:
        # Office not held — but if they held a higher office, career level is plausible
        any_offices = len(dprr_offices) > 0
        if any_offices:
            return 0.3, f"{office} not held, but career active"
        return 0.0, f"no offices recorded"

    # Office held — check date proximity
    if date is None:
        return 0.5, f"{office} held (no inscription date to compare)"

    closest = min(held_offices, key=lambda o: abs((o.get("date_start") or 0) - date))
    closest_date = closest.get("date_start")
    if closest_date is None:
        return 0.5, f"{office} held (no DPRR date to compare)"

    gap = abs(closest_date - date)
    if gap <= 5:
        return 1.0, f"{office} held in {closest_date}, inscription {date} (±{gap}yr)"
    elif gap <= 10:
        return 0.7, f"{office} held in {closest_date}, inscription {date} (±{gap}yr)"
    elif gap <= 20:
        return 0.5, f"{office} held in {closest_date}, inscription {date} (±{gap}yr)"
    else:
        return 0.3, f"{office} held in {closest_date}, inscription {date} (±{gap}yr, distant)"
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
        # DPRR person's father praenomen = manius, grandfather = manius
        # Inscription filiation = M'. f. M'. n.
        family = {"father_praenomen": "manius", "grandfather_praenomen": "manius"}
        score, explanation = score_filiation(family, {"father": "manius", "grandfather": "manius"})
        assert score == 1.0

    def test_father_match_only(self):
        family = {"father_praenomen": "lucius", "grandfather_praenomen": None}
        score, explanation = score_filiation(family, {"father": "lucius"})
        assert score == 0.5

    def test_father_mismatch(self):
        family = {"father_praenomen": "marcus", "grandfather_praenomen": None}
        score, explanation = score_filiation(family, {"father": "lucius"})
        assert score == 0.0

    def test_no_filiation_data(self):
        family = {"father_praenomen": "marcus", "grandfather_praenomen": None}
        score, explanation = score_filiation(family, {})
        assert score == 0.0

    def test_no_family_data(self):
        family = {}
        score, explanation = score_filiation(family, {"father": "marcus"})
        assert score == 0.0
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
) -> tuple[float, str]:
    """Score filiation match between DPRR family data and inscription filiation.

    dprr_family: {"father_praenomen": "marcus", "grandfather_praenomen": "gnaeus"}
    inscription_filiation: {"father": "marcus", "grandfather": "gnaeus"} (from parse_filiation)
    """
    if not inscription_filiation:
        return 0.0, "no filiation in inscription"
    if not dprr_family:
        return 0.0, "no family data in DPRR"

    insc_father = inscription_filiation.get("father")
    insc_grandfather = inscription_filiation.get("grandfather")
    dprr_father = dprr_family.get("father_praenomen")
    dprr_grandfather = dprr_family.get("grandfather_praenomen")

    if not insc_father:
        return 0.0, "no father in filiation"

    if not dprr_father:
        return 0.0, "DPRR father unknown"

    if insc_father != dprr_father:
        return 0.0, f"father mismatch: inscription {insc_father}, DPRR {dprr_father}"

    # Father matches
    if insc_grandfather and dprr_grandfather:
        if insc_grandfather == dprr_grandfather:
            return 1.0, f"father ({insc_father}) + grandfather ({insc_grandfather}) match"
        else:
            return 0.0, f"grandfather mismatch: inscription {insc_grandfather}, DPRR {dprr_grandfather}"

    return 0.5, f"father matches ({insc_father}), grandfather not verifiable"
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
        # DPRR person served in Asia, inscription found at Pleiades URI in Asia
        provinces = ["https://pleiades.stoa.org/places/837#this"]
        score, explanation = score_geography(provinces, "https://pleiades.stoa.org/places/837#this")
        assert score == 1.0

    def test_no_match(self):
        provinces = ["https://pleiades.stoa.org/places/775#this"]  # Africa
        score, explanation = score_geography(provinces, "https://pleiades.stoa.org/places/837#this")  # Asia
        assert score == 0.0

    def test_no_findspot(self):
        provinces = ["https://pleiades.stoa.org/places/837#this"]
        score, explanation = score_geography(provinces, None)
        assert score == 0.0

    def test_no_provinces(self):
        score, explanation = score_geography([], "https://pleiades.stoa.org/places/837#this")
        assert score == 0.0
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
) -> tuple[float, str]:
    """Score geographic match between DPRR provincial posts and inscription findspot.

    dprr_province_pleiades_uris: Pleiades URIs for provinces where DPRR person served
        (resolved via linkage graph: DPRR Province → Pleiades Place)
    findspot_pleiades_uri: Pleiades URI for the inscription's findspot
        (resolved via EDH geography → Pleiades)
    """
    if not findspot_pleiades_uri:
        return 0.0, "no findspot data"
    if not dprr_province_pleiades_uris:
        return 0.0, "no provincial posts recorded"

    if findspot_pleiades_uri in dprr_province_pleiades_uris:
        return 1.0, f"findspot matches provincial post ({findspot_pleiades_uri})"

    return 0.0, f"findspot {findspot_pleiades_uri} not in served provinces"
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
from linked_past.core.disambiguate import PersonDisambiguator, PersonContext


class TestPersonDisambiguator:
    def test_weighted_combination(self):
        """Test that the orchestrator combines signal scores correctly."""
        disambiguator = PersonDisambiguator()

        # Mock pre-computed signal scores for two candidates
        # Candidate A: filiation match + career match
        # Candidate B: only temporal overlap
        signals_a = {
            "filiation": (1.0, 0.4, "father+grandfather match"),
            "career": (1.0, 0.3, "consul -147 confirmed"),
            "geography": (0.0, 0.2, "no findspot"),
            "temporal": (1.0, 0.1, "within era"),
        }
        signals_b = {
            "filiation": (0.0, 0.4, "father mismatch"),
            "career": (0.0, 0.3, "office not held"),
            "geography": (0.0, 0.2, "no findspot"),
            "temporal": (1.0, 0.1, "within era"),
        }

        score_a = disambiguator._compute_weighted_score(signals_a)
        score_b = disambiguator._compute_weighted_score(signals_b)

        assert score_a > 0.7
        assert score_b < 0.2
        assert score_a > score_b

    def test_weight_redistribution_missing_signals(self):
        """When a signal has no data, its weight redistributes to others."""
        disambiguator = PersonDisambiguator()

        # Only career and temporal have data (filiation and geography absent)
        signals = {
            "filiation": (0.0, 0.4, "no filiation in inscription"),  # absent
            "career": (1.0, 0.3, "consul confirmed"),
            "geography": (0.0, 0.2, "no findspot"),  # absent
            "temporal": (1.0, 0.1, "within era"),
        }

        score = disambiguator._compute_weighted_score(signals)
        # With redistribution: career (0.3) + temporal (0.1) = 0.4 available
        # Normalized: career = 0.3/0.4 * 1.0, temporal = 0.1/0.4 * 1.0 → total = 1.0
        assert score == pytest.approx(1.0, abs=0.01)

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

    def _compute_weighted_score(self, signals: dict[str, tuple[float, float, str]]) -> float:
        """Compute weighted score with redistribution for absent signals.

        A signal is 'absent' if its explanation indicates no data (score == 0.0
        and explanation starts with 'no '). Absent signals' weights are
        redistributed proportionally to present signals.
        """
        present_weight = 0.0
        weighted_sum = 0.0

        for name, (score, weight, explanation) in signals.items():
            # Signal is absent if score is 0 AND explanation indicates missing data
            is_absent = score == 0.0 and explanation.startswith("no ")
            if not is_absent:
                present_weight += weight
                weighted_sum += weight * score

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
        candidates_signals: list[tuple[str, str, dict[str, tuple[float, float, str]]]],
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
              rdfs:label ?label ;
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
    """Get father's and grandfather's praenomina for a DPRR person."""
    from linked_past.core.store import execute_query

    sparql = f"""
    PREFIX vocab: <http://romanrepublic.ac.uk/rdf/ontology#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?relLabel ?relatedPraenomen WHERE {{
      ?ra a vocab:RelationshipAssertion ;
          vocab:isAboutPerson ?related ;
          vocab:hasRelatedPerson <{person_uri}> ;
          vocab:hasRelationship ?rel .
      ?rel rdfs:label ?relLabel .
      FILTER(?relLabel IN ("Relationship: father of"))
      ?related vocab:hasPraenomen ?prae .
      ?prae rdfs:label ?relatedPraenomen .
    }}
    """
    rows = execute_query(dprr_store, sparql)
    result: dict[str, str | None] = {"father_praenomen": None, "grandfather_praenomen": None}
    for r in rows:
        prae_label = r.get("relatedPraenomen", "")
        prae = normalize_praenomen(prae_label.replace("Praenomen: ", ""))
        if prae:
            result["father_praenomen"] = prae
    # Grandfather requires chaining — find father first, then father's father
    # For now, only extract direct father. Grandfather requires a second query.
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
        # TODO in future: implement extract_context_from_edh_uri
        return f"Error: EDH URI extraction not yet implemented. Provide `name` instead."

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
        for sig_name, (score, weight, expl) in match.signals.items():
            lines.append(f"- {sig_name.title()}: **{score * weight:.2f}/{weight:.1f}** — {expl}")
        lines.append(f"**Confidence: {match.confidence}**\n")

    if ranked:
        top = ranked[0]
        lines.append(f"## Recommendation\n")
        lines.append(f"{top.dprr_label} — {top.confidence} match (score {top.score:.2f}).")

    output = "\n".join(lines)
    _log_tool_call(app, "disambiguate", {"name": name, "uri": uri}, output, int((time.monotonic() - t0) * 1000))
    return output
```

- [ ] **Step 2: Run the full test suite**

Run: `uv run pytest && uv run ruff check .`
Expected: All pass.

- [ ] **Step 3: Commit**

```bash
git add packages/linked-past/linked_past/core/server.py
git commit -m "feat: register disambiguate MCP tool"
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

    # Re-run name matching to get all ambiguous candidates
    # (import the matching function from the EDH script)
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts.match_dprr_edh import get_dprr_persons, get_edh_elite_persons, match_candidates

    dprr_persons = get_dprr_persons(dprr_store)
    edh_persons = get_edh_elite_persons(edh_store)
    all_candidates = match_candidates(dprr_persons, edh_persons)

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
