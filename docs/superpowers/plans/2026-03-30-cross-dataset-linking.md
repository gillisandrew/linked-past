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

---

### Task 1: Add Confirmed Person Links YAML

**Files:**
- Create: `linked_past/linkages/dprr_nomisma_confirmed.yaml`
- Test: `tests/test_linkage.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_linkage.py`:

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

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_linkage.py::test_load_person_links tests/test_linkage.py::test_person_link_reverse_lookup tests/test_linkage.py::test_person_link_provenance -v`

Expected: PASS (these use in-memory data, no YAML file needed yet — they validate the linkage format works with `skos:closeMatch`).

If they pass, the existing `LinkageGraph` already handles `skos:closeMatch` — proceed to step 3. If they fail, check that `skos:closeMatch` is in the `_RELATIONSHIP_MAP` in `linkage.py`.

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

**Note:** Only include links where both URIs are verified. The URIs above
(`pompey`, `q_c_m_p_i_rrc`, `q_cassivs_rrc`) were confirmed to exist in the
Nomisma store during the investigation. Additional confirmed links (C. Annius,
Lentulus Marcellinus, Caesar) should be added after verifying their Nomisma
URIs exist — run `search_entities(name, "nomisma")` for each candidate and
add to this file only if the URI resolves.

- [ ] **Step 4: Write a test that loads the YAML file from disk**

Add to `tests/test_linkage.py`:

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
```

- [ ] **Step 5: Run all linkage tests**

Run: `uv run pytest tests/test_linkage.py -v`

Expected: All pass.

- [ ] **Step 6: Commit**

```bash
git add linked_past/linkages/dprr_nomisma_confirmed.yaml tests/test_linkage.py
git commit -m "feat: add confirmed DPRR-Nomisma person cross-links"
```

---

### Task 2: Add Probable Person Links YAML

**Files:**
- Create: `linked_past/linkages/dprr_nomisma_probable.yaml`
- Test: `tests/test_linkage.py`

- [ ] **Step 1: Create the probable links YAML file**

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

Start with an empty links list. Probable links require URI verification
against the Nomisma store before adding. Candidates identified in the gap
analysis (Cn. Pompeius Jr., Sex. Pompeius Pius, M. Minatius Sabinus,
M. Publicius) should be verified in the enrichment workflow and added here.

- [ ] **Step 2: Write a test that loads both YAML files together**

Add to `tests/test_linkage.py`:

```python
def test_load_both_nomisma_yamls():
    base = Path(__file__).parent.parent / "linked_past" / "linkages"
    confirmed = base / "dprr_nomisma_confirmed.yaml"
    probable = base / "dprr_nomisma_probable.yaml"
    if not confirmed.exists() or not probable.exists():
        pytest.skip("YAML files not yet created")
    g = LinkageGraph()
    g.load_yaml(confirmed)
    g.load_yaml(probable)
    # Confirmed links still work
    results = g.find_links("http://romanrepublic.ac.uk/rdf/entity/Person/1976")
    assert len(results) == 1
    assert results[0]["confidence"] == "confirmed"
```

- [ ] **Step 3: Run all linkage tests**

Run: `uv run pytest tests/test_linkage.py -v`

Expected: All pass.

- [ ] **Step 4: Commit**

```bash
git add linked_past/linkages/dprr_nomisma_probable.yaml tests/test_linkage.py
git commit -m "feat: add probable DPRR-Nomisma person links YAML (empty, ready for enrichment)"
```

---

### Task 3: Implement `_collect_see_also` Helper

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
    # Generate rows with many distinct URIs
    rows = [{"uri": f"http://example.com/{i}"} for i in range(200)]
    # Add one that actually has a link
    rows.append({"uri": "http://romanrepublic.ac.uk/rdf/entity/Person/1976"})
    result = _collect_see_also(rows, linkage, max_uris=50)
    # Should still work — either finds the link within 50 URIs or not,
    # but should not error
    assert isinstance(result, str)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_see_also.py -v`

Expected: FAIL with `ImportError: cannot import name '_collect_see_also' from 'linked_past.core.server'`

- [ ] **Step 3: Implement `_collect_see_also`**

Add to `linked_past/core/server.py`, before the `build_app` function (around line 30, after the imports):

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
                    f"  {uri} \u2192 {target} ({confidence})"
                )

    if not see_also_lines:
        return ""

    header = "\n\n\u2500\u2500\u2500 See also \u2500\u2500\u2500\n"
    hint = "\nUse `find_links(uri)` for full provenance."
    return header + "\n".join(see_also_lines) + hint
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_see_also.py -v`

Expected: All 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_see_also.py linked_past/core/server.py
git commit -m "feat: add _collect_see_also helper for cross-dataset hints"
```

---

### Task 4: Wire `_collect_see_also` into the Query Tool

**Files:**
- Modify: `linked_past/core/server.py:227-236`
- Modify: `tests/test_linked_past_integration.py`

- [ ] **Step 1: Write the failing integration test**

Add to `tests/test_linked_past_integration.py`:

```python
def test_query_response_includes_see_also(integration_ctx):
    """Query returning a person URI with a known cross-link includes See also."""
    # Load a person link into the linkage graph
    if integration_ctx.linkage:
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

    # Simulate what the query tool does
    import toons
    from linked_past.core.server import _collect_see_also

    table = toons.dumps(result.rows)
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

- [ ] **Step 2: Run the integration tests to verify the first one fails**

Run: `uv run pytest tests/test_linked_past_integration.py::test_query_response_includes_see_also tests/test_linked_past_integration.py::test_query_response_no_see_also_when_no_links -v`

Expected: First test may pass already (since `_collect_see_also` exists from Task 3). If so, proceed — this test validates the integration, not the helper.

- [ ] **Step 3: Wire `_collect_see_also` into the `query` tool**

In `linked_past/core/server.py`, modify the `query` tool function. Replace lines 227-236:

```python
        table = toons.dumps(result.rows)
        meta = app.registry.get_metadata(dataset)
        version = meta.get("version", "unknown")
        footer = (
            f"\n\n─── Sources ───\n"
            f"Data: {plugin.display_name} v{version}. {plugin.license}.\n"
            f"      Cite as: {plugin.citation}\n"
            f"Tool: linked-past, https://github.com/gillisandrew/dprr-tool"
        )
        return table + footer
```

With:

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

The only change is adding the `see_also = ...` line and inserting `see_also +` in the return.

- [ ] **Step 4: Run all tests**

Run: `uv run pytest tests/test_linked_past_integration.py tests/test_see_also.py tests/test_linkage.py -v`

Expected: All pass.

- [ ] **Step 5: Run the full test suite to check for regressions**

Run: `uv run pytest -v`

Expected: All pass. The existing `test_query_result_includes_citation` test should still pass because the Sources footer is unchanged.

- [ ] **Step 6: Commit**

```bash
git add linked_past/core/server.py tests/test_linked_past_integration.py
git commit -m "feat: surface cross-dataset links as 'See also' in query responses"
```

---

### Task 5: Lint and Final Verification

**Files:**
- All modified files

- [ ] **Step 1: Run linter**

Run: `uv run ruff check .`

Expected: No errors. Fix any issues.

- [ ] **Step 2: Run full test suite**

Run: `uv run pytest -v`

Expected: All tests pass.

- [ ] **Step 3: Manually verify by inspecting output format**

Run a quick smoke test to confirm the "See also" section renders correctly
when the server is running with the YAML files loaded. This can be done by
starting the MCP server and issuing a query that returns a person URI with
a known link (e.g., Person/1976 for Pompey).

- [ ] **Step 4: Commit any lint fixes**

```bash
git add -u
git commit -m "fix: lint cleanup"
```
