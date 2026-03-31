# DPRR Province → Pleiades Enrichment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend DPRR→Pleiades province cross-links from 5 to ~60, using store-consistent numeric URIs.

**Architecture:** Replace and extend `dprr_pleiades.yaml` with numeric DPRR Province URIs (matching the Oxigraph store) and verified Pleiades Place URIs. This fixes a URI mismatch where existing slug-based URIs (`Province/Sicilia`) don't match the store's numeric URIs (`Province/5`), making `find_links` fail for store-derived URIs.

**Tech Stack:** YAML linkage file, pytest, MCP tools for verification.

---

### Task 1: Write the failing test

**Files:**
- Create: `packages/linked-past/tests/test_pleiades_linkage.py`

- [ ] **Step 1: Write a test that loads the linkage file and checks link count and URI format**

```python
"""Tests for DPRR→Pleiades province linkage completeness and URI consistency."""

from pathlib import Path

import yaml

LINKAGE_FILE = (
    Path(__file__).resolve().parents[1]
    / "linked_past"
    / "linkages"
    / "dprr_pleiades.yaml"
)


def _load_links() -> dict:
    with LINKAGE_FILE.open() as f:
        return yaml.safe_load(f)


def test_minimum_link_count():
    """We should have at least 55 province→place links."""
    data = _load_links()
    assert len(data["links"]) >= 55, (
        f"Expected >=55 links, got {len(data['links'])}"
    )


def test_source_uris_use_numeric_ids():
    """All source URIs must use the numeric Province ID form that matches the DPRR Oxigraph store."""
    data = _load_links()
    for link in data["links"]:
        source = link["source"]
        # Must be http://romanrepublic.ac.uk/rdf/entity/Province/{number}
        suffix = source.replace("http://romanrepublic.ac.uk/rdf/entity/Province/", "")
        assert suffix.isdigit(), (
            f"Source URI {source} does not use numeric ID — "
            f"slug-based URIs don't match the DPRR store"
        )


def test_target_uris_use_pleiades_this_fragment():
    """All target URIs must use the https://pleiades.stoa.org/places/{id}#this pattern."""
    data = _load_links()
    for link in data["links"]:
        target = link["target"]
        assert target.startswith("https://pleiades.stoa.org/places/"), (
            f"Target {target} is not a Pleiades place URI"
        )
        assert target.endswith("#this"), (
            f"Target {target} missing #this fragment"
        )


def test_no_duplicate_sources():
    """Each DPRR province should appear at most once as a source."""
    data = _load_links()
    sources = [link["source"] for link in data["links"]]
    duplicates = [s for s in sources if sources.count(s) > 1]
    assert not duplicates, f"Duplicate sources: {set(duplicates)}"


def test_metadata_fields():
    """Metadata must have required fields."""
    data = _load_links()
    meta = data["metadata"]
    assert meta["source_dataset"] == "dprr"
    assert meta["target_dataset"] == "pleiades"
    assert meta["relationship"] == "skos:closeMatch"
    assert meta["confidence"] == "confirmed"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/linked-past/tests/test_pleiades_linkage.py -v`
Expected: FAIL on `test_minimum_link_count` (only 5 links) and `test_source_uris_use_numeric_ids` (existing links use slug URIs).

---

### Task 2: Replace the linkage file with enriched data

**Files:**
- Modify: `packages/linked-past/linked_past/linkages/dprr_pleiades.yaml`

- [ ] **Step 1: Replace the entire file content**

Replace the full contents of `packages/linked-past/linked_past/linkages/dprr_pleiades.yaml` with:

```yaml
metadata:
  source_dataset: dprr
  target_dataset: pleiades
  relationship: "skos:closeMatch"
  confidence: confirmed
  method: manual_alignment
  basis: "Barrington Atlas of the Greek and Roman World (Talbert 2000)"
  author: linked-past project
  date: "2026-03-30"
links:
  # ── Existing links (migrated from slug to numeric URIs) ──
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/5"
    target: "https://pleiades.stoa.org/places/462492#this"
    note: "Sicilia — Map 47"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/23"
    target: "https://pleiades.stoa.org/places/775#this"
    note: "Africa — Map 33"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/18"
    target: "https://pleiades.stoa.org/places/1027#this"
    note: "Hispania — Map 25-27"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/25"
    target: "https://pleiades.stoa.org/places/837#this"
    note: "Asia — Map 56-62"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/6"
    target: "https://pleiades.stoa.org/places/993#this"
    note: "Gallia — Map 14-17"
  # ── New links: major provinces ──
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/49"
    target: "https://pleiades.stoa.org/places/570028#this"
    note: "Achaea — Map 58"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/57"
    target: "https://pleiades.stoa.org/places/766#this"
    note: "Aegyptus — Map 74"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/79"
    target: "https://pleiades.stoa.org/places/540591#this"
    note: "Aetolia — Map 55"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/15"
    target: "https://pleiades.stoa.org/places/442469#this"
    note: "Apulia — Map 45"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/61"
    target: "https://pleiades.stoa.org/places/874350#this"
    note: "Armenia — Map 89"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/96"
    target: "https://pleiades.stoa.org/places/265817#this"
    note: "Balearic islands — Map 27"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/13"
    target: "https://pleiades.stoa.org/places/511189#this"
    note: "Bithynia — Map 52"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/63"
    target: "https://pleiades.stoa.org/places/20419#this"
    note: "Britannia — Map 2"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/95"
    target: "https://pleiades.stoa.org/places/442509#this"
    note: "Brundisium — Map 45"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/8"
    target: "https://pleiades.stoa.org/places/452366#this"
    note: "Bruttium — Map 46"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/83"
    target: "https://pleiades.stoa.org/places/442518#this"
    note: "Calabria — Map 45"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/74"
    target: "https://pleiades.stoa.org/places/432742#this"
    note: "Campania — Map 44"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/60"
    target: "https://pleiades.stoa.org/places/628949#this"
    note: "Cappadocia — Map 64"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/32"
    target: "https://pleiades.stoa.org/places/432754#this"
    note: "Capua — Map 44"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/26"
    target: "https://pleiades.stoa.org/places/658440#this"
    note: "Cilicia — Map 67"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/81"
    target: "https://pleiades.stoa.org/places/472063#this"
    note: "Corsica — Map 48"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/44"
    target: "https://pleiades.stoa.org/places/589748#this"
    note: "Crete — Map 60"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/62"
    target: "https://pleiades.stoa.org/places/707498#this"
    note: "Cyprus — Map 72"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/56"
    target: "https://pleiades.stoa.org/places/373777#this"
    note: "Cyrenaica — Map 38"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/69"
    target: "https://pleiades.stoa.org/places/373778#this"
    note: "Cyrene — Map 38"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/103"
    target: "https://pleiades.stoa.org/places/197240#this"
    note: "Dalmatia — Map 20"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/101"
    target: "https://pleiades.stoa.org/places/599588#this"
    note: "Delos — Map 60"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/53"
    target: "https://pleiades.stoa.org/places/530871#this"
    note: "Epirus — Map 54"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/12"
    target: "https://pleiades.stoa.org/places/413122#this"
    note: "Etruria — Map 42"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/58"
    target: "https://pleiades.stoa.org/places/619161#this"
    note: "Galatia — Map 63"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/36"
    target: "https://pleiades.stoa.org/places/383801#this"
    note: "Gallia Cisalpina — Map 39"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/97"
    target: "https://pleiades.stoa.org/places/981537#this"
    note: "Gallia Narbonensis — Map 15"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/47"
    target: "https://pleiades.stoa.org/places/981537#this"
    note: "Gallia Transalpina — Map 15 (Republican name for Narbonensis)"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/9"
    target: "https://pleiades.stoa.org/places/530036687#this"
    note: "Hispania Citerior"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/7"
    target: "https://pleiades.stoa.org/places/862#this"
    note: "Hispania Ulterior — Map 26 (Baetica is the Augustan successor)"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/24"
    target: "https://pleiades.stoa.org/places/481865#this"
    note: "Illyria — Map 49"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/65"
    target: "https://pleiades.stoa.org/places/481865#this"
    note: "Illyricum — Map 49"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/17"
    target: "https://pleiades.stoa.org/places/197304#this"
    note: "Istria — Map 20"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/51"
    target: "https://pleiades.stoa.org/places/1052#this"
    note: "Italia — Map 1"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/59"
    target: "https://pleiades.stoa.org/places/687934#this"
    note: "Iudaea — Map 70"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/80"
    target: "https://pleiades.stoa.org/places/432900#this"
    note: "Latium — Map 43"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/67"
    target: "https://pleiades.stoa.org/places/383698#this"
    note: "Liguria — Map 39"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/70"
    target: "https://pleiades.stoa.org/places/442639#this"
    note: "Lucania — Map 45"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/35"
    target: "https://pleiades.stoa.org/places/442640#this"
    note: "Luceria — Map 45"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/52"
    target: "https://pleiades.stoa.org/places/638965#this"
    note: "Lycia — Map 65"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/50"
    target: "https://pleiades.stoa.org/places/491656#this"
    note: "Macedonia — Map 49-51"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/55"
    target: "https://pleiades.stoa.org/places/305106#this"
    note: "Mauretania — Map 28-30"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/54"
    target: "https://pleiades.stoa.org/places/305120#this"
    note: "Numidia — Map 33"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/64"
    target: "https://pleiades.stoa.org/places/197425#this"
    note: "Pannonia — Map 20"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/73"
    target: "https://pleiades.stoa.org/places/413253#this"
    note: "Picenum — Map 42"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/10"
    target: "https://pleiades.stoa.org/places/403253#this"
    note: "Pisa (Pisae) — Map 41"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/85"
    target: "https://pleiades.stoa.org/places/857287#this"
    note: "Pontus — Map 87"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/93"
    target: "https://pleiades.stoa.org/places/590031#this"
    note: "Rhodes — Map 61"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/86"
    target: "https://pleiades.stoa.org/places/423025#this"
    note: "Rome — Map 43"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/71"
    target: "https://pleiades.stoa.org/places/433078#this"
    note: "Samnium — Map 44"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/3"
    target: "https://pleiades.stoa.org/places/472014#this"
    note: "Sardinia — Map 48"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/31"
    target: "https://pleiades.stoa.org/places/433133#this"
    note: "Suessula — Map 44"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/68"
    target: "https://pleiades.stoa.org/places/1306#this"
    note: "Syria — Map 68-69"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/14"
    target: "https://pleiades.stoa.org/places/442810#this"
    note: "Tarentum — Map 45"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/48"
    target: "https://pleiades.stoa.org/places/501638#this"
    note: "Thracia — Map 51-52"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/82"
    target: "https://pleiades.stoa.org/places/413360#this"
    note: "Umbria — Map 42"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/76"
    target: "https://pleiades.stoa.org/places/393511#this"
    note: "Venetia — Map 40"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/100"
    target: "https://pleiades.stoa.org/places/727070#this"
    note: "Alexandria — Map 74"
  # ── New links: ethnic territories (with Pleiades people/region entries) ──
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/87"
    target: "https://pleiades.stoa.org/places/413291#this"
    note: "Sabine territory (Sabini) — Map 42"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/84"
    target: "https://pleiades.stoa.org/places/413291#this"
    note: "Sabinum (Sabini) — Map 42"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/89"
    target: "https://pleiades.stoa.org/places/422822#this"
    note: "Aequian territory (Aequi) — Map 43"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/90"
    target: "https://pleiades.stoa.org/places/422944#this"
    note: "Hernican territory (Hernici) — Map 43"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/88"
    target: "https://pleiades.stoa.org/places/433208#this"
    note: "Volscian territory (Volsci) — Map 43"
```

That is 65 links total (5 migrated + 60 new).

**Provinces intentionally skipped (no clear 1:1 Pleiades match):**
- Province/45 Africa Nova — no Pleiades entry for this short-lived subdivision
- Province/46 Africa Vetus — no Pleiades entry
- Province/104 Gallia Cispadana — no Pleiades entry for this sub-region
- Province/20 Macedonia/Achaea — combined assignment, ambiguous target

**Provinces skipped (non-geographic):**
Province/92 (blank), Province/2 urbanus, Province/4 inter peregrinos, Province/16 quaestio extraordinaria, Province/19 quo senatus censuisset, Province/21 city, Province/22 repetundae, Province/27 inter sicarios, Province/28 peculatus, Province/29 maiestas, Province/30 ambitus, Province/33 provincia declined, Province/34 de vi, Province/94 de veneficiis, Province/11 fleet, Province/66 cum imperio consulari, Province/75 cum imperio consulari infinito, Province/91 Allied cities of Italy, Province/98 In the east, Province/99 Mediterranean.

- [ ] **Step 2: Verify the file parses correctly**

Run: `python3 -c "import yaml; data=yaml.safe_load(open('packages/linked-past/linked_past/linkages/dprr_pleiades.yaml')); print(f'{len(data[\"links\"])} links')"` from the repo root.
Expected: `65 links`

---

### Task 3: Run the tests and verify they pass

**Files:**
- Test: `packages/linked-past/tests/test_pleiades_linkage.py`

- [ ] **Step 1: Run the new linkage tests**

Run: `uv run pytest packages/linked-past/tests/test_pleiades_linkage.py -v`
Expected: All 5 tests PASS.

- [ ] **Step 2: Run the full test suite to check for regressions**

Run: `uv run pytest`
Expected: All tests pass. The linkage YAML format hasn't changed — only the URIs and number of entries — so existing integration tests should still work.

- [ ] **Step 3: Run lint**

Run: `uv run ruff check .`
Expected: No new lint errors.

---

### Task 4: Verify links work via MCP tools

- [ ] **Step 1: Verify a migrated link resolves from the numeric URI**

Use `find_links` with `http://romanrepublic.ac.uk/rdf/entity/Province/5` (Sicilia).
Expected: Returns the Pleiades link to `https://pleiades.stoa.org/places/462492#this`.

- [ ] **Step 2: Verify a new link resolves**

Use `find_links` with `http://romanrepublic.ac.uk/rdf/entity/Province/50` (Macedonia).
Expected: Returns the Pleiades link to `https://pleiades.stoa.org/places/491656#this`.

- [ ] **Step 3: Verify `explore_entity` shows cross-links**

Use `explore_entity` with `http://romanrepublic.ac.uk/rdf/entity/Province/68` (Syria).
Expected: Cross-dataset links section includes the Pleiades match.

---

### Task 5: Commit

- [ ] **Step 1: Stage and commit**

```bash
git add packages/linked-past/linked_past/linkages/dprr_pleiades.yaml packages/linked-past/tests/test_pleiades_linkage.py
git commit -m "feat: enrich DPRR→Pleiades province links from 5 to 65

Migrate existing links from slug-based URIs (Province/Sicilia) to
numeric URIs (Province/5) matching the DPRR Oxigraph store, so
find_links resolves correctly from SPARQL query results.

Add 60 new province→place links covering all geographic DPRR provinces
with clear Pleiades matches. Skips legal/jurisdictional categories and
provinces without 1:1 Pleiades entries (Africa Nova/Vetus, Gallia
Cispadana, Macedonia/Achaea combined)."
```
