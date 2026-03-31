# Prosopographic Disambiguation Engine

## Goal

Build an MCP tool (`disambiguate`) and core library module that resolves ambiguous person matches between DPRR and EDH (and other datasets) by scoring candidates against four prosopographic signals: filiation, career/office, geography, and temporal overlap.

## Motivation

Automated name matching between DPRR (4,876 Republican senators/equites) and EDH (87,329 inscription persons) produces 819 ambiguous candidates where multiple DPRR persons share the same tria nomina as an EDH person (e.g. 18 P. Cornelii Scipiones, 16 M. Claudii Marcelli). These cannot be resolved by name or date alone — they require prosopographic reasoning about family trees, career sequences, and geographic context.

No existing computational system combines these signals for Roman prosopography. Berkeley Prosopography Services (BPS) does temporal constraints for Babylonian records; DPRR provides the LOD infrastructure; but an integrated scorer is missing.

## Architecture

A new core module `disambiguate.py` exposes a `PersonDisambiguator` class that scores DPRR candidates against a `PersonContext` (extracted from an EDH record or provided manually). The server exposes this as an MCP tool. A batch script uses the same library to process the 819 existing candidates.

```
EDH URI or manual input
        │
        ▼
  extract_context()          ← queries EDH store for name, inscription text, dates, findspot
        │
        ▼
  PersonContext              ← dataclass: name, filiation, office, dates, findspot
        │
        ▼
  find DPRR candidates       ← nomen lookup (with Greek transliteration) against DPRR store
        │
        ▼
  score each candidate       ← 4 signal functions, weighted linear combination
        │
        ▼
  ranked results             ← scores, explanations, confidence level
```

## Core Module: `packages/linked-past/linked_past/core/disambiguate.py`

### PersonContext dataclass

```python
@dataclass
class PersonContext:
    name: str                    # Raw name from EDH (Latin or Greek)
    normalized_name: str         # After Greek transliteration if needed
    praenomen: str | None        # Parsed/normalized praenomen
    nomen: str | None            # Parsed nomen
    cognomen: str | None         # Parsed cognomen
    filiation: str | None        # "M. f. Cn. n." extracted from inscription text
    office: str | None           # "cos.", "pr.", etc. from inscription text
    date_start: int | None       # Inscription date range start
    date_end: int | None         # Inscription date range end
    findspot_uri: str | None     # EDH geography URI for findspot
    source_uri: str | None       # The EDH person URI
```

### extract_context(uri, edh_store) → PersonContext

Builds a `PersonContext` from an EDH person URI by:

1. Querying EDH for `foaf:name`, `foaf:member` (social status)
2. Following `lawd:hasAttestation` to the inscription URI
3. Querying the inscription for `epi:editionText`, `nmo:hasStartDate`, `nmo:hasEndDate`, `lawd:foundAt`
4. Parsing filiation from edition text: regex `/(\w+)\.\s*f\.\s*(\w+)\.\s*n\./` captures father's and grandfather's praenomina
5. Parsing office mentions from edition text: regex patterns for cos., pr., tr. pl., q., aed., leg., procos., etc.
6. Running Greek transliteration (`transliterate_greek()` from `match_dprr_edh.py`) if Greek characters detected
7. Parsing the (transliterated) name into praenomen/nomen/cognomen

For free-form input (no EDH URI), the caller provides fields directly and they're wrapped into `PersonContext`.

### PersonDisambiguator class

```python
class PersonDisambiguator:
    def __init__(self, dprr_store, edh_store, linkage_graph, registry):
        ...

    def disambiguate(self, context: PersonContext, max_candidates: int = 10) -> list[CandidateMatch]:
        ...
```

#### Signal functions

Each returns `(score: float, explanation: str)` where score is 0.0–1.0.

**`_score_filiation(dprr_person_uri, filiation_str)`**

Parses filiation string into father's praenomen and grandfather's praenomen. Queries DPRR for `RelationshipAssertion` with `hasRelationship` = "father of" / "son of" to find the candidate's father and grandfather. Compares praenomina.

| Condition | Score |
|-----------|-------|
| Father + grandfather praenomen both match | 1.0 |
| Father praenomen matches, grandfather unknown | 0.5 |
| Father praenomen doesn't match | 0.0 |
| No filiation data available | 0.0 (signal absent) |

**`_score_career(dprr_person_uri, office_str, date)`**

Queries DPRR PostAssertions for the candidate. If the inscription mentions an office:

| Condition | Score |
|-----------|-------|
| Same office held, date matches within ±5 years | 1.0 |
| Same office held, date within ±10 years | 0.7 |
| Same office held, no date or date within ±20 years | 0.5 |
| Office held but date incompatible (cursus age violation) | 0.0 |
| Office not held but career level plausible | 0.3 |
| No office data from inscription | 0.0 (signal absent) |

Cursus age constraints: uses `eraFrom` as approximate birth year. Consul before age 35 or after age 75 is impossible; quaestor before age 25 is impossible.

**`_score_geography(dprr_person_uri, findspot_uri)`**

Chains DPRR PostAssertionProvince → Province → Pleiades (via linkage graph) → EDH geography. If the DPRR person held a post in the province where the inscription was found:

| Condition | Score |
|-----------|-------|
| DPRR provincial post matches inscription findspot | 1.0 |
| DPRR provincial post in adjacent region | 0.5 |
| No provincial post recorded, but Italy-based career + Italian findspot | 0.3 |
| No geographic data | 0.0 (signal absent) |

**`_score_temporal(dprr_person_uri, date_start, date_end)`**

| Condition | Score |
|-----------|-------|
| Inscription date midpoint falls within DPRR era range | 1.0 |
| Inscription date range partially overlaps DPRR era | 0.5 |
| No overlap | 0.0 |
| No date data | 0.0 (signal absent) |

#### Weighted combination

```python
WEIGHTS = {
    "filiation": 0.4,
    "career": 0.3,
    "geography": 0.2,
    "temporal": 0.1,
}
```

Final score = sum of (weight × score) for each signal. Only signals where data is available contribute — if filiation is absent, its weight is redistributed proportionally across the other signals so that a career + geography match isn't penalized by missing filiation.

#### CandidateMatch dataclass

```python
@dataclass
class CandidateMatch:
    dprr_uri: str
    dprr_label: str
    score: float
    confidence: str              # "strong", "probable", "ambiguous"
    signals: dict[str, tuple[float, float, str]]  # signal → (score, max_weight, explanation)
```

Confidence levels:
- **strong**: top score ≥ 0.7 and gap to second candidate ≥ 0.2
- **probable**: top score ≥ 0.5 and gap ≥ 0.1
- **ambiguous**: everything else

## MCP Tool: `disambiguate`

Registered in `server.py` following the existing tool pattern.

**Parameters:**
- `uri` (optional, str) — EDH person URI for automatic context extraction
- `name` (optional, str) — Person name for manual mode
- `filiation` (optional, str) — e.g. "M. f. Cn. n."
- `office` (optional, str) — e.g. "cos."
- `date` (optional, int) — Approximate date (negative = BC)
- `province` (optional, str) — Province name or Pleiades URI

At least one of `uri` or `name` required.

**Output:** Markdown with ranked candidates, per-signal score breakdowns, and confidence assessment (see Design Section 3 in brainstorming for example output).

## Batch Script: `scripts/batch_disambiguate_edh.py`

Processes the 819 ambiguous EDH candidates:

1. Load existing ambiguous candidates (from name-matching output)
2. For each EDH person URI, call `extract_context()` + `disambiguate()`
3. Classify results:
   - Score ≥ 0.7 and gap ≥ 0.2 → append to `dprr_edh_confirmed.yaml`
   - Score 0.5–0.7 or gap < 0.2 → write to review file
   - Score < 0.5 → skip
4. Report summary statistics

Thresholds are constants at the top of the script, tunable after initial results.

## Testing

### Golden test case: Aquillius Florus (HD051507/2)

We know Person/4686 is the correct match. The inscription provides:
- Filiation: "M'. f. M'. n." — should match DPRR genealogy (father M'. Aquillius cos. 101)
- Office: "q." (quaestor)
- Geography: Found near Smyrna, province of Asia — DPRR records no Asian post for Person/4686 directly, but his grandfather served there
- Temporal: Inscription c. 70s BC, DPRR era -125 to 0

If the disambiguator doesn't rank Person/4686 first, the signal weights need tuning.

### Unit tests

- `test_score_filiation`: Test with known DPRR family trees (e.g. Aquillii, Cornelii Scipiones)
- `test_score_career`: Test consul/praetor date matching and cursus age constraints
- `test_score_geography`: Test province→Pleiades→findspot chain
- `test_score_temporal`: Test era overlap calculation
- `test_extract_context`: Test parsing of inscription edition text for filiation and office
- `test_disambiguate_aquillius`: Integration test with the golden case
- `test_greek_transliteration_context`: Test that Greek EDH names get transliterated before candidate lookup

### Test fixtures

Use inline SPARQL INSERT fixtures in ephemeral stores (following existing test patterns — tests create inline SAMPLE_TURTLE, not mocks).

## Scope Exclusions

- **Co-occurrence analysis** (persons on same inscription) — future iteration
- **Inscription text NLP** beyond regex for filiation/office — future iteration
- **Machine learning / trained classifiers** — insufficient labeled data; weighted scoring is appropriate
- **Non-EDH datasets** — the tool works with any `PersonContext`, but batch processing targets EDH first

## Dependencies

- Existing: `pyoxigraph` (SPARQL), `pyyaml` (linkage files)
- Existing: Greek transliteration from `match_dprr_edh.py` (will be moved into core or imported)
- No new dependencies
