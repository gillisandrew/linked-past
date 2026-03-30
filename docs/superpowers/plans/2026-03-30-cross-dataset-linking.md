# Cross-Dataset Person Linking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add DPRR-Nomisma person cross-links and surface them as "See also" hints in query responses.

**Architecture:** Declare person-level `skos:closeMatch` links in YAML files (the existing linkage format). Add a helper that scans query result URIs against the linkage graph and appends a "See also" section to the response. No new dependencies.

**Tech Stack:** Python, pyoxigraph, YAML, pytest

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `linked_past/linkages/dprr_nomisma_confirmed.yaml` | Create | Confirmed person links (DPRR ↔ Nomisma) |
| `linked_past/linkages/dprr_nomisma_probable.yaml` | Create | Probable person links (DPRR ↔ Nomisma) |
| `linked_past/core/server.py` | Modify | Add `_collect_see_also` helper; call it in `query` tool |
| `tests/test_linkage.py` | Modify | Add tests for closeMatch links loading |
| `tests/test_see_also.py` | Create | Unit tests for `_collect_see_also` helper |
| `tests/test_linked_past_integration.py` | Modify | Integration test: query response includes "See also" |

## Deferred Links

The spec identifies 10 candidate links. This plan includes the 3 whose
Nomisma URIs were verified during investigation. The remaining 7 require
URI verification via the enrichment workflow described in the spec and
should be added in a follow-up session:

**Confirmed (deferred — need URI verification):**
- Person/1740 (C. Annius) → `nomisma:c_annivs_rrc`
- Person/2082 (Cn. Lentulus Marcellinus) → `nomisma:cn_len_rrc`
- Person/1957 (C. Iulius Caesar) → `nomisma:julius_caesar`

**Probable (deferred — need URI verification):**
- Person/2253 (Cn. Pompeius Jr.) → `nomisma:cn_magnvs_imp_rrc`
- Person/2254 (Sex. Pompeius Pius) → `nomisma:sex_magnvs_rrc`
- Person/2613 (M. Minatius Sabinus) → `nomisma:m_minat_sabin_rrc`
- Person/2623 (M. Publicius) → `nomisma:m_poblici_rrc`

---

### Task 1: Add YAML Link Files and Linkage Tests

**Files:**
- Create: `linked_past/linkages/dprr_nomisma_confirmed.yaml`
- Create: `linked_past/linkages/dprr_nomisma_probable.yaml`
- Modify: `tests/test_linkage.py`

- [ ] **Step 1: Write the linkage tests**

Add to `tests/test_linkage.py`, after the existing `SAMPLE_TEMPORAL` dict:

```python
SAMPLE_PERSON_LINK = {
    "metadata": {
        "source_dataset": "dprr",
        "target_dataset": "nomisma",
        "relationship": "skos:closeMatch",
        "confidence": "confirmed",
        "method": "manual_alignment",
        "basis": "DPRR moneyer posts citing RRC cross-referenced with Nomisma person authorities",
        "author": "linked-past project",
        "date": "2026-03-30",
    },
    "links": [
        {
            "source": "http://romanrepublic.ac.uk/rdf/entity/Person/1976",
            "target": "http://nomisma.org/id/pompey",
            "note": "RRC moneyer 71, 49 BC; DPRR proconsul Hispania 77-49 BC",
        },
        {
            "source": "http://romanrepublic.ac.uk/rdf/entity/Person/1889",
            "target": "http://nomisma.org/id/q_c_m_p_i_rrc",
            "note": "RRC moneyer 81 BC; DPRR proconsul Hispania Ulterior 79-71 BC",
        },
    ],
}


def test_load_person_links():
    g = LinkageGraph()
    g.load_data(SAMPLE_PERSON_LINK)
    results = g.find_links("http://romanrepublic.ac.uk/rdf/entity/Person/1976")
    assert len(results) == 1
    r = results[0]
    assert r["target"] == "http://nomisma.org/id/pompey"
    assert r["confidence"] == "confirmed"
    assert r["direction"] == "forward"


def test_person_link_reverse_lookup():
    g = LinkageGraph()
    g.load_data(SAMPLE_PERSON_LINK)
    results = g.find_links("http://nomisma.org/id/q_c_m_p_i_rrc")
    assert len(results) == 1
    r = results[0]
    assert r["target"] == "http://romanrepublic.ac.uk/rdf/entity/Person/1889"
    assert r["direction"] == "reverse"


def test_person_link_provenance():
    g = LinkageGraph()
    g.load_data(SAMPLE_PERSON_LINK)
    prov = g.get_provenance(
        "http://romanrepublic.ac.uk/rdf/entity/Person/1976",
        "http://nomisma.org/id/pompey",
    )
    assert prov is not None
    assert "RRC" in prov["basis"]
    assert prov["confidence"] == "confirmed"
    assert prov["note"] == "RRC moneyer 71, 49 BC; DPRR proconsul Hispania 77-49 BC"
```

- [ ] **Step 2: Run new tests to confirm they pass**

These use in-memory data, validating that `LinkageGraph` handles
`skos:closeMatch`. It should work — `skos:closeMatch` is already in
`_RELATIONSHIP_MAP` at `linked_past/core/linkage.py:19`.

Run: `uv run pytest tests/test_linkage.py::test_load_person_links tests/test_linkage.py::test_person_link_reverse_lookup tests/test_linkage.py::test_person_link_provenance -v`

Expected: All 3 PASS.

- [ ] **Step 3: Create the confirmed links YAML file**

Create `linked_past/linkages/dprr_nomisma_confirmed.yaml`:

```yaml
metadata:
  source_dataset: dprr
  target_dataset: nomisma
  relationship: "skos:closeMatch"
  confidence: confirmed
  method: manual_alignment
  basis: >-
    DPRR moneyer posts citing RRC cross-referenced with CRRO coin type
    attributions and Nomisma person authorities. See
    hispanic-mint-documentary-gaps.md for full methodology.
  author: linked-past project
  date: "2026-03-30"
links:
  - source: "http://romanrepublic.ac.uk/rdf/entity/Person/1976"
    target: "http://nomisma.org/id/pompey"
    note: "RRC moneyer 71, 49 BC; DPRR proconsul Hispania 77-49 BC"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Person/1889"
    target: "http://nomisma.org/id/q_c_m_p_i_rrc"
    note: "RRC moneyer 81 BC; DPRR proconsul Hispania Ulterior 79-71 BC"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Person/2481"
    target: "http://nomisma.org/id/q_cassivs_rrc"
    note: "RRC 428; DPRR quaestor Hispania Ulterior 55-47 BC"
```

- [ ] **Step 4: Create the probable links YAML file (empty, ready for enrichment)**

Create `linked_past/linkages/dprr_nomisma_probable.yaml`:

```yaml
metadata:
  source_dataset: dprr
  target_dataset: nomisma
  relationship: "skos:closeMatch"
  confidence: probable
  method: manual_alignment
  basis: >-
    Name and date matching between DPRR post assertions and Nomisma person
    authorities, supported by CRRO coin type attributions from Hispania.
    See hispanic-mint-documentary-gaps.md for full methodology.
  author: linked-past project
  date: "2026-03-30"
links: []
```

- [ ] **Step 5: Write tests that load the YAML files from disk**

Add to `tests/test_linkage.py` (add the `Path` import at the top of the file
alongside the existing `pytest` import):

```python
from pathlib import Path


def test_load_dprr_nomisma_yaml():
    yaml_path = Path(__file__).parent.parent / "linked_past" / "linkages" / "dprr_nomisma_confirmed.yaml"
    if not yaml_path.exists():
        pytest.skip("YAML file not yet created")
    g = LinkageGraph()
    g.load_yaml(yaml_path)
    results = g.find_links("http://romanrepublic.ac.uk/rdf/entity/Person/1976")
    assert len(results) == 1
    assert results[0]["target"] == "http://nomisma.org/id/pompey"


def test_load_both_nomisma_yamls():
    base = Path(__file__).parent.parent / "linked_past" / "linkages"
    confirmed = base / "dprr_nomisma_confirmed.yaml"
    probable = base / "dprr_nomisma_probable.yaml"
    if not confirmed.exists() or not probable.exists():
        pytest.skip("YAML files not yet created")
    g = LinkageGraph()
    g.load_yaml(confirmed)
    g.load_yaml(probable)
    # Confirmed links still work after loading empty probable file
    results = g.find_links("http://romanrepublic.ac.uk/rdf/entity/Person/1976")
    assert len(results) == 1
    assert results[0]["confidence"] == "confirmed"
```

- [ ] **Step 6: Run all linkage tests and lint**

Run: `uv run pytest tests/test_linkage.py -v && uv run ruff check tests/test_linkage.py`

Expected: All pass, no lint errors.

- [ ] **Step 7: Commit**

```bash
git add linked_past/linkages/dprr_nomisma_confirmed.yaml linked_past/linkages/dprr_nomisma_probable.yaml tests/test_linkage.py
git commit -m "feat: add DPRR-Nomisma person cross-link YAML files with tests"
```

---

### Task 2: Implement `_collect_see_also` Helper

**Files:**
- Create: `tests/test_see_also.py`
- Modify: `linked_past/core/server.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_see_also.py`:

```python
"""Tests for the _collect_see_also helper."""

from linked_past.core.linkage import LinkageGraph

PERSON_LINKS = {
    "metadata": {
        "source_dataset": "dprr",
        "target_dataset": "nomisma",
        "relationship": "skos:closeMatch",
        "confidence": "confirmed",
        "method": "manual_alignment",
        "basis": "Test basis",
        "author": "test",
        "date": "2026-03-30",
    },
    "links": [
        {
            "source": "http://romanrepublic.ac.uk/rdf/entity/Person/1976",
            "target": "http://nomisma.org/id/pompey",
            "note": "Pompey",
        },
        {
            "source": "http://romanrepublic.ac.uk/rdf/entity/Person/1889",
            "target": "http://nomisma.org/id/q_c_m_p_i_rrc",
            "note": "Metellus Pius",
        },
    ],
}


def _make_linkage():
    g = LinkageGraph()
    g.load_data(PERSON_LINKS)
    return g


def test_see_also_with_matching_uris():
    from linked_past.core.server import _collect_see_also

    linkage = _make_linkage()
    rows = [
        {"person": "http://romanrepublic.ac.uk/rdf/entity/Person/1976", "name": "Pompey"},
    ]
    result = _collect_see_also(rows, linkage)
    assert "See also" in result
    assert "http://nomisma.org/id/pompey" in result
    assert "confirmed" in result


def test_see_also_no_matching_uris():
    from linked_past.core.server import _collect_see_also

    linkage = _make_linkage()
    rows = [
        {"person": "http://romanrepublic.ac.uk/rdf/entity/Person/9999", "name": "Nobody"},
    ]
    result = _collect_see_also(rows, linkage)
    assert result == ""


def test_see_also_no_uris_at_all():
    from linked_past.core.server import _collect_see_also

    linkage = _make_linkage()
    rows = [{"name": "Just a string", "date": "-509"}]
    result = _collect_see_also(rows, linkage)
    assert result == ""


def test_see_also_none_linkage():
    from linked_past.core.server import _collect_see_also

    rows = [
        {"person": "http://romanrepublic.ac.uk/rdf/entity/Person/1976", "name": "Pompey"},
    ]
    result = _collect_see_also(rows, None)
    assert result == ""


def test_see_also_deduplicates_targets():
    from linked_past.core.server import _collect_see_also

    linkage = _make_linkage()
    # Same URI appears in multiple rows
    rows = [
        {"person": "http://romanrepublic.ac.uk/rdf/entity/Person/1976", "name": "Pompey"},
        {"person": "http://romanrepublic.ac.uk/rdf/entity/Person/1976", "name": "Pompey again"},
    ]
    result = _collect_see_also(rows, linkage)
    assert result.count("nomisma.org/id/pompey") == 1


def test_see_also_multiple_linked_persons():
    from linked_past.core.server import _collect_see_also

    linkage = _make_linkage()
    rows = [
        {"person": "http://romanrepublic.ac.uk/rdf/entity/Person/1976", "name": "Pompey"},
        {"person": "http://romanrepublic.ac.uk/rdf/entity/Person/1889", "name": "Metellus"},
    ]
    result = _collect_see_also(rows, linkage)
    assert "nomisma.org/id/pompey" in result
    assert "nomisma.org/id/q_c_m_p_i_rrc" in result


def test_see_also_respects_max_uris():
    from linked_past.core.server import _collect_see_also

    linkage = _make_linkage()
    # Put the linked URI first, then pad with unlinked URIs
    rows = [{"uri": "http://romanrepublic.ac.uk/rdf/entity/Person/1976"}]
    rows.extend({"uri": f"http://example.com/{i}"} for i in range(200))
    # With max_uris=50 the linked URI (row 0) is within range
    result = _collect_see_also(rows, linkage, max_uris=50)
    assert "nomisma.org/id/pompey" in result

    # Now put the linked URI beyond the cap
    rows_late = [{"uri": f"http://example.com/{i}"} for i in range(200)]
    rows_late.append({"uri": "http://romanrepublic.ac.uk/rdf/entity/Person/1976"})
    result_late = _collect_see_also(rows_late, linkage, max_uris=50)
    # Should NOT find the link — it's past the 50-URI cap
    assert result_late == ""


def test_see_also_skips_reverse_links():
    """URIs that are link targets should not produce reverse 'see also' entries."""
    from linked_past.core.server import _collect_see_also

    linkage = _make_linkage()
    # Query returns a Nomisma URI (which is a target in the linkage graph)
    rows = [
        {"authority": "http://nomisma.org/id/pompey", "label": "Pompey"},
    ]
    result = _collect_see_also(rows, linkage)
    # Should not surface a reverse link back to the DPRR person —
    # that would be confusing circular cross-referencing
    assert result == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_see_also.py -v`

Expected: FAIL with `ImportError: cannot import name '_collect_see_also' from 'linked_past.core.server'`

- [ ] **Step 3: Implement `_collect_see_also`**

Add to `linked_past/core/server.py` at module level, after the `QUERY_TIMEOUT`
line and before the `AppContext` dataclass (insert after line 31):

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
            # Only surface forward links — reverse links (where our URI is the
            # target) would create confusing circular cross-references.
            if link.get("direction") != "forward":
                continue
            target = link["target"]
            if target not in seen_targets:
                seen_targets.add(target)
                confidence = link.get("confidence", "")
                see_also_lines.append(
                    f"  {uri} \u2192 {target} ({confidence})"
                )

    if not see_also_lines:
        return ""

    header = "\n\n\u2500\u2500\u2500 See also \u2500\u2500\u2500\n"
    hint = "\nUse `find_links(uri)` for full provenance.\n"
    return header + "\n".join(see_also_lines) + hint
```

Key differences from the spec version:
- `isinstance(value, str)` guard to handle non-string result values.
- `max_uris` break is at the outer loop level (spec had it in the inner loop).
- Filters to `direction == "forward"` only, skipping reverse links.
- Trailing `\n` on `hint` so there's a blank line before the Sources footer.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_see_also.py -v && uv run ruff check tests/test_see_also.py linked_past/core/server.py`

Expected: All 9 tests PASS, no lint errors.

- [ ] **Step 5: Commit**

```bash
git add tests/test_see_also.py linked_past/core/server.py
git commit -m "feat: add _collect_see_also helper for cross-dataset hints"
```

---

### Task 3: Wire `_collect_see_also` into the Query Tool

**Files:**
- Modify: `linked_past/core/server.py`
- Modify: `tests/test_linked_past_integration.py`

- [ ] **Step 1: Write the integration tests**

Add to `tests/test_linked_past_integration.py`:

```python
def test_query_response_includes_see_also(integration_ctx):
    """Query returning a person URI with a known cross-link includes See also."""
    # Load a person link into the linkage graph
    integration_ctx.linkage.load_data({
        "metadata": {
            "source_dataset": "dprr",
            "target_dataset": "nomisma",
            "relationship": "skos:closeMatch",
            "confidence": "confirmed",
            "method": "manual_alignment",
            "basis": "Test",
            "author": "test",
            "date": "2026-03-30",
        },
        "links": [
            {
                "source": "http://romanrepublic.ac.uk/rdf/entity/Person/1",
                "target": "http://nomisma.org/id/test_person",
                "note": "Test link",
            },
        ],
    })

    store = integration_ctx.registry.get_store("dprr")
    plugin = integration_ctx.registry.get_plugin("dprr")
    result = validate_and_execute(
        "PREFIX vocab: <http://romanrepublic.ac.uk/rdf/ontology#>\n"
        "SELECT ?p ?name WHERE { ?p a vocab:Person ; vocab:hasPersonName ?name }",
        store, plugin.build_schema_dict(), plugin.get_prefixes(),
    )
    assert result.success is True

    from linked_past.core.server import _collect_see_also

    see_also = _collect_see_also(result.rows, integration_ctx.linkage)
    assert "See also" in see_also
    assert "nomisma.org/id/test_person" in see_also
    assert "confirmed" in see_also


def test_query_response_no_see_also_when_no_links(integration_ctx):
    """Query returning URIs with no cross-links omits See also."""
    store = integration_ctx.registry.get_store("dprr")
    plugin = integration_ctx.registry.get_plugin("dprr")
    result = validate_and_execute(
        "PREFIX vocab: <http://romanrepublic.ac.uk/rdf/ontology#>\n"
        "SELECT ?name WHERE { ?p a vocab:Person ; vocab:hasPersonName ?name }",
        store, plugin.build_schema_dict(), plugin.get_prefixes(),
    )
    assert result.success is True

    from linked_past.core.server import _collect_see_also

    see_also = _collect_see_also(result.rows, integration_ctx.linkage)
    assert see_also == ""
```

- [ ] **Step 2: Wire `_collect_see_also` into the `query` tool**

In `linked_past/core/server.py`, find the `query` tool's return block. Match
this exact pattern (do NOT rely on line numbers — Task 2 shifted them):

```python
        table = toons.dumps(result.rows)
        meta = app.registry.get_metadata(dataset)
```

Replace the block from `table = toons.dumps(...)` through `return table + footer` with:

```python
        table = toons.dumps(result.rows)
        see_also = _collect_see_also(result.rows, app.linkage)
        meta = app.registry.get_metadata(dataset)
        version = meta.get("version", "unknown")
        footer = (
            f"\n\n─── Sources ───\n"
            f"Data: {plugin.display_name} v{version}. {plugin.license}.\n"
            f"      Cite as: {plugin.citation}\n"
            f"Tool: linked-past, https://github.com/gillisandrew/dprr-tool"
        )
        return table + see_also + footer
```

The only changes are: adding the `see_also = ...` line and `see_also +` in
the return statement.

- [ ] **Step 3: Run all tests and lint**

Run: `uv run pytest -v && uv run ruff check .`

Expected: All tests pass, no lint errors. The existing
`test_query_result_includes_citation` test should still pass because the
Sources footer is unchanged.

- [ ] **Step 4: Commit**

```bash
git add linked_past/core/server.py tests/test_linked_past_integration.py
git commit -m "feat: surface cross-dataset links as 'See also' in query responses"
```

---

### Task 4: Final Verification

**Files:**
- All modified files

- [ ] **Step 1: Run full test suite with lint**

Run: `uv run ruff check . && uv run pytest -v`

Expected: No lint errors, all tests pass.

- [ ] **Step 2: Verify output format visually**

Run a quick sanity check that the "See also" section renders between the
table and the Sources footer with proper spacing. Create a temporary test
script or inspect test output to confirm:

```
[results table]

─── See also ───
  http://romanrepublic.ac.uk/rdf/entity/Person/1976 → http://nomisma.org/id/pompey (confirmed)
Use `find_links(uri)` for full provenance.

─── Sources ───
Data: ...
```

Confirm there are blank lines separating each section.

- [ ] **Step 3: Commit any remaining fixes**

```bash
git add -u
git commit -m "fix: final cleanup"
```
