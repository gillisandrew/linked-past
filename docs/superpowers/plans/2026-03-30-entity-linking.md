# Entity Linking: Cross-Dataset References and "See Also" — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Populate the linkage graph with cross-dataset references (DPRR↔Nomisma persons, DPRR↔Pleiades places, Wikidata-derived concordances) and surface them automatically in query responses as "See also" hints.

**Architecture:** Curated YAML linkage files for known person/place equivalences. A `_collect_see_also` helper scans query result URIs against the linkage graph and appends a cross-reference section. Wikidata CONSTRUCT queries extract Pleiades↔TM and other concordances as Turtle for loading into the linkage graph. Per-link confidence override support in the linkage loader.

**Tech Stack:** Python, pyoxigraph, YAML, pytest

**Sources:**
- Spec: `docs/superpowers/specs/2026-03-30-cross-dataset-linking-design.md`
- Existing plan: `docs/superpowers/plans/2026-03-30-cross-dataset-linking.md` (superseded by this)

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `linked_past/linkages/dprr_nomisma_confirmed.yaml` | Create | Confirmed DPRR↔Nomisma person links |
| `linked_past/linkages/dprr_nomisma_probable.yaml` | Create | Probable DPRR↔Nomisma person links |
| `linked_past/core/linkage.py` | Modify | Support per-link confidence override in YAML |
| `linked_past/core/server.py` | Modify | Add `_collect_see_also` helper; call in `query` tool |
| `scripts/extract_wikidata_concordances.py` | Create | SPARQL CONSTRUCT queries → Turtle concordance files |
| `tests/test_see_also.py` | Create | Unit tests for `_collect_see_also` |
| `tests/test_linkage.py` | Modify | Add tests for person links and per-link confidence |

---

### Task 1: Per-link confidence support in LinkageGraph

**Files:**
- Modify: `linked_past/core/linkage.py`
- Modify: `tests/test_linkage.py`

Currently the YAML loader applies the metadata-level confidence to all links. Add support for an optional per-link `confidence` field that overrides the default.

- [ ] **Step 1: Write the test**

Add to `tests/test_linkage.py`:

```python
SAMPLE_MIXED_CONFIDENCE = {
    "metadata": {
        "source_dataset": "dprr",
        "target_dataset": "nomisma",
        "relationship": "skos:closeMatch",
        "confidence": "confirmed",
        "method": "manual_alignment",
        "basis": "RRC cross-referencing",
        "author": "linked-past project",
        "date": "2026-03-30",
    },
    "links": [
        {
            "source": "http://romanrepublic.ac.uk/rdf/entity/Person/1957",
            "target": "http://nomisma.org/id/julius_caesar",
            "note": "RRC 468; confirmed via MRR",
        },
        {
            "source": "http://romanrepublic.ac.uk/rdf/entity/Person/2253",
            "target": "http://nomisma.org/id/cn_magnvs_imp_rrc",
            "confidence": "probable",
            "note": "Name + date match only",
        },
    ],
}


def test_per_link_confidence(tmp_path):
    graph = LinkageGraph(tmp_path / "store")
    graph.load_data(SAMPLE_MIXED_CONFIDENCE)

    # Caesar link should use metadata default: confirmed
    links_caesar = graph.find_links("http://romanrepublic.ac.uk/rdf/entity/Person/1957")
    assert len(links_caesar) == 1
    assert links_caesar[0]["confidence"] == "confirmed"

    # Pompey Jr should use per-link override: probable
    links_pompey = graph.find_links("http://romanrepublic.ac.uk/rdf/entity/Person/2253")
    assert len(links_pompey) == 1
    assert links_pompey[0]["confidence"] == "probable"
```

- [ ] **Step 2: Update `load_data` / `load_yaml` in linkage.py**

In the link processing loop, read per-link confidence if present:

```python
confidence = link.get("confidence", metadata.get("confidence", "candidate"))
```

Use this `confidence` value instead of always reading from `metadata`.

- [ ] **Step 3: Run tests, commit**

```bash
uv run pytest tests/test_linkage.py -v
git commit -m "feat: support per-link confidence override in linkage YAML"
```

---

### Task 2: DPRR↔Nomisma person linkage YAML files

**Files:**
- Create: `linked_past/linkages/dprr_nomisma_confirmed.yaml`
- Create: `linked_past/linkages/dprr_nomisma_probable.yaml`

- [ ] **Step 1: Create confirmed links file**

```yaml
# linked_past/linkages/dprr_nomisma_confirmed.yaml
metadata:
  source_dataset: dprr
  target_dataset: nomisma
  relationship: "skos:closeMatch"
  confidence: confirmed
  method: manual_alignment
  basis: >-
    DPRR v1.3.0 moneyer post assertions citing Crawford RRC,
    cross-referenced with Nomisma person authorities and CRRO coin types.
  author: linked-past project
  date: "2026-03-30"

links:
  - source: "http://romanrepublic.ac.uk/rdf/entity/Person/1976"
    target: "http://nomisma.org/id/pompey"
    note: "RRC moneyer 71, 49 BC; DPRR proconsul Hispania 77-49 BC"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Person/1889"
    target: "http://nomisma.org/id/q_c_m_p_i_rrc"
    note: "RRC moneyer 81 BC; DPRR proconsul Hispania Ulterior 79-71 BC"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Person/1957"
    target: "http://nomisma.org/id/julius_caesar"
    note: "RRC 468; DPRR moneyer 49-44 BC"
```

- [ ] **Step 2: Create probable links file**

```yaml
# linked_past/linkages/dprr_nomisma_probable.yaml
metadata:
  source_dataset: dprr
  target_dataset: nomisma
  relationship: "skos:closeMatch"
  confidence: probable
  method: manual_alignment
  basis: >-
    Name and date matching between DPRR persons with Hispanic provincial
    posts and Nomisma/CRRO coin authorities. No direct RRC citation chain
    in DPRR secondary sources.
  author: linked-past project
  date: "2026-03-30"

links:
  - source: "http://romanrepublic.ac.uk/rdf/entity/Person/2253"
    target: "http://nomisma.org/id/cn_magnvs_imp_rrc"
    note: "RRC 470-471; DPRR promagistrate in Hispania"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Person/2254"
    target: "http://nomisma.org/id/sex_magnvs_rrc"
    note: "RRC 477-479; DPRR legatus Hispania Ulterior"
```

- [ ] **Step 3: Verify links load**

```bash
uv run pytest tests/test_linkage.py -v
```

- [ ] **Step 4: Commit**

```bash
git add linked_past/linkages/dprr_nomisma_*.yaml
git commit -m "feat: add DPRR↔Nomisma person cross-links (confirmed and probable)"
```

---

### Task 3: "See also" in query responses

**Files:**
- Modify: `linked_past/core/server.py`
- Create: `tests/test_see_also.py`

- [ ] **Step 1: Write the tests**

```python
# tests/test_see_also.py
"""Tests for the _collect_see_also helper."""

from linked_past.core.server import _collect_see_also


class FakeLinkage:
    """Mock linkage graph for testing."""

    def __init__(self, links: dict[str, list[dict]]):
        self._links = links

    def find_links(self, uri: str) -> list[dict]:
        return self._links.get(uri, [])


def test_see_also_with_links():
    linkage = FakeLinkage({
        "http://romanrepublic.ac.uk/rdf/entity/Person/1957": [
            {"target": "http://nomisma.org/id/julius_caesar", "confidence": "confirmed", "basis": "RRC"},
        ],
    })
    rows = [{"person": "http://romanrepublic.ac.uk/rdf/entity/Person/1957", "name": "Caesar"}]
    result = _collect_see_also(rows, linkage)
    assert "See also" in result
    assert "julius_caesar" in result
    assert "confirmed" in result


def test_see_also_no_links():
    linkage = FakeLinkage({})
    rows = [{"person": "http://romanrepublic.ac.uk/rdf/entity/Person/9999", "name": "Nobody"}]
    result = _collect_see_also(rows, linkage)
    assert result == ""


def test_see_also_no_uris():
    linkage = FakeLinkage({})
    rows = [{"name": "Caesar", "office": "consul"}]
    result = _collect_see_also(rows, linkage)
    assert result == ""


def test_see_also_none_linkage():
    result = _collect_see_also([{"x": "http://example.org/1"}], None)
    assert result == ""


def test_see_also_deduplicates():
    linkage = FakeLinkage({
        "http://example.org/1": [
            {"target": "http://example.org/a", "confidence": "confirmed", "basis": "test"},
        ],
    })
    # Same URI appears in multiple rows
    rows = [
        {"x": "http://example.org/1"},
        {"x": "http://example.org/1"},
    ]
    result = _collect_see_also(rows, linkage)
    assert result.count("example.org/a") == 1  # Deduplicated


def test_see_also_caps_at_max_uris():
    linkage = FakeLinkage({
        f"http://example.org/{i}": [
            {"target": f"http://target.org/{i}", "confidence": "confirmed", "basis": "test"},
        ]
        for i in range(100)
    })
    rows = [{"x": f"http://example.org/{i}"} for i in range(100)]
    result = _collect_see_also(rows, linkage, max_uris=5)
    # Should not process more than 5 URIs
    assert result.count("→") <= 5
```

- [ ] **Step 2: Implement `_collect_see_also` in server.py**

Add before `create_mcp_server()`:

```python
def _collect_see_also(
    rows: list[dict[str, str]],
    linkage: LinkageGraph | None,
    max_uris: int = 50,
) -> str:
    """Scan query result URIs for cross-dataset links. Returns formatted section or empty string."""
    if not linkage:
        return ""

    uris: set[str] = set()
    for row in rows:
        for value in row.values():
            if value and isinstance(value, str) and value.startswith("http"):
                uris.add(value)
            if len(uris) >= max_uris:
                break

    see_also_lines: list[str] = []
    seen_targets: set[str] = set()
    for uri in uris:
        for link in linkage.find_links(uri):
            target = link["target"]
            if target not in seen_targets:
                seen_targets.add(target)
                confidence = link.get("confidence", "")
                see_also_lines.append(
                    f"  {uri} → {target} ({confidence})"
                )

    if not see_also_lines:
        return ""

    header = "\n─── See also ───\n"
    hint = "\nUse `find_links(uri)` for full provenance.\n"
    return header + "\n".join(see_also_lines) + hint
```

- [ ] **Step 3: Wire into the `query` tool**

In the `query` tool, after `table = toons.dumps(result.rows)`, add:

```python
        see_also = _collect_see_also(result.rows, app.linkage)
```

Change the return to:

```python
        return table + see_also + footer
```

- [ ] **Step 4: Run tests, commit**

```bash
uv run pytest tests/test_see_also.py tests/test_linkage.py -v
uv run pytest -v && uv run ruff check .
git commit -m "feat: add 'See also' cross-reference hints in query responses"
```

---

### Task 4: Wikidata concordance extraction script

**Files:**
- Create: `scripts/extract_wikidata_concordances.py`

This script runs SPARQL CONSTRUCT queries against the Wikidata endpoint to extract cross-dataset concordances as Turtle files for the linkage graph.

- [ ] **Step 1: Create the script**

```python
# scripts/extract_wikidata_concordances.py
"""Extract cross-dataset concordances from Wikidata as Turtle for the linkage graph.

Queries Wikidata SPARQL endpoint for entities that bridge our datasets via
shared identifiers, and produces Turtle files loadable into the linkage graph.

Usage:
    uv run python scripts/extract_wikidata_concordances.py [output_dir]
"""

import sys
import urllib.parse
import urllib.request
from pathlib import Path

WIKIDATA_ENDPOINT = "https://query.wikidata.org/sparql"

# Pleiades ↔ Trismegistos Place concordance
PLEIADES_TM_QUERY = """\
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

CONSTRUCT {
    ?pleiades_uri skos:exactMatch ?tm_uri .
}
WHERE {
    ?item wdt:P1584 ?pleiades .
    ?item wdt:P1958 ?tm_place .
    BIND(IRI(CONCAT("https://pleiades.stoa.org/places/", ?pleiades)) AS ?pleiades_uri)
    BIND(IRI(CONCAT("https://www.trismegistos.org/place/", ?tm_place)) AS ?tm_uri)
}
"""

# Nomisma mints ↔ Pleiades via Wikidata
NOMISMA_PLEIADES_QUERY = """\
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

CONSTRUCT {
    ?nomisma_uri skos:exactMatch ?pleiades_uri .
}
WHERE {
    ?item wdt:P2950 ?nomisma_id .
    ?item wdt:P1584 ?pleiades .
    BIND(IRI(CONCAT("http://nomisma.org/id/", ?nomisma_id)) AS ?nomisma_uri)
    BIND(IRI(CONCAT("https://pleiades.stoa.org/places/", ?pleiades)) AS ?pleiades_uri)
}
"""

QUERIES = {
    "pleiades_tm_places.ttl": PLEIADES_TM_QUERY,
    "nomisma_pleiades.ttl": NOMISMA_PLEIADES_QUERY,
}


def run_construct(query: str) -> bytes:
    """Run a SPARQL CONSTRUCT query against Wikidata, return Turtle bytes."""
    params = urllib.parse.urlencode({"query": query, "format": "text/turtle"})
    url = f"{WIKIDATA_ENDPOINT}?{params}"
    req = urllib.request.Request(url, headers={"Accept": "text/turtle", "User-Agent": "linked-past/0.1"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read()


def main(output_dir: str = "linked_past/linkages/wikidata"):
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    for filename, query in QUERIES.items():
        print(f"Running {filename}...")
        try:
            data = run_construct(query)
            path = out / filename
            path.write_bytes(data)
            lines = data.decode("utf-8", errors="replace").count("\n")
            print(f"  Wrote {path} ({len(data):,} bytes, ~{lines} lines)")
        except Exception as e:
            print(f"  ERROR: {e}")

    print("Done. Load these into the linkage graph or linkages/ directory.")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "linked_past/linkages/wikidata")
```

- [ ] **Step 2: Run the script**

```bash
uv run python scripts/extract_wikidata_concordances.py
```

- [ ] **Step 3: Commit**

```bash
git add scripts/extract_wikidata_concordances.py
git commit -m "feat: add Wikidata concordance extraction script (Pleiades↔TM, Nomisma↔Pleiades)"
```

---

### Task 5: Final verification

- [ ] **Step 1: Run full test suite**

```bash
uv run pytest -v && uv run ruff check .
```

- [ ] **Step 2: Verify linkage graph loads all YAML files**

```bash
uv run python -c "
from linked_past.core.linkage import LinkageGraph
from pathlib import Path
g = LinkageGraph(Path('/tmp/test-linkage-store'))
linkages_dir = Path('linked_past/linkages')
for f in sorted(linkages_dir.glob('*.yaml')):
    count = g.load_yaml(f)
    print(f'{f.name}: {count} links')
print(f'Total: {g.triple_count()} triples')
"
```

- [ ] **Step 3: Test "See also" end-to-end**

Start the server and query for a person who has cross-links (e.g., Pompey, Caesar). The response should include a "See also" section with Nomisma URIs.

- [ ] **Step 4: Commit any fixes**

```bash
git add -A && git commit -m "fix: address issues found in final verification"
```
