# RDFS Materialization at Store Load Time

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** After loading raw RDF into an Oxigraph store, run RDFS/OWL2 RL materialization using the `reasonable` library so that inferred triples (from `rdfs:subPropertyOf`, `rdfs:subClassOf`, etc.) are queryable without explicit assertion in the source data.

**Architecture:** Add a `materialize()` function to the store module that serializes the store to a temp Turtle file, runs `reasonable.PyReasoner`, and inserts genuinely new triples back into the store. Call it from `DatasetPlugin.load()` after bulk-loading raw data. This is generic — any dataset with RDFS/OWL axioms benefits automatically. Currently DPRR (427K → 749K triples, +322K inferred) and Nomisma benefit; the other 5 datasets have no axioms and the function is a fast no-op for them.

**Tech Stack:** `reasonable` (Rust OWL2 RL reasoner with Python bindings), `pyoxigraph`

---

### Task 1: Add `reasonable` Dependency

**Files:**
- Modify: `packages/linked-past/pyproject.toml`

- [ ] **Step 1: Add reasonable to dependencies**

In `packages/linked-past/pyproject.toml`, add `"reasonable"` to the `dependencies` list:

```toml
dependencies = [
    "pyoxigraph",
    "rdflib",
    "pyyaml",
    "mcp",
    "toons>=0.5.3",
    "markdown",
    "websockets",
    "linked-past-store",
    "reasonable",
]
```

- [ ] **Step 2: Sync the environment**

Run: `uv sync`
Expected: `reasonable` resolves and installs.

- [ ] **Step 3: Verify import works**

Run: `uv run python -c "import reasonable; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add packages/linked-past/pyproject.toml
git commit -m "deps: add reasonable for RDFS/OWL materialization"
```

---

### Task 2: Implement `materialize()` in Store Module

Add a `materialize(store)` function that runs OWL2 RL forward-chaining on an Oxigraph store and inserts inferred triples.

**Files:**
- Modify: `packages/linked-past/linked_past/core/store.py`
- Test: `packages/linked-past/tests/test_core_store.py`

- [ ] **Step 1: Write failing tests**

Add to `packages/linked-past/tests/test_core_store.py`:

```python
from linked_past.core.store import create_store, load_rdf, materialize


def test_materialize_subpropertyof(tmp_path):
    """rdfs:subPropertyOf materialization: hasPersonName subPropertyOf rdfs:label."""
    store = create_store(tmp_path / "store")
    ttl = tmp_path / "data.ttl"
    ttl.write_text(
        '@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n'
        '@prefix owl: <http://www.w3.org/2002/07/owl#> .\n'
        '@prefix ex: <http://example.org/> .\n'
        '\n'
        'ex:hasPersonName a owl:DatatypeProperty ;\n'
        '    rdfs:subPropertyOf rdfs:label .\n'
        '\n'
        'ex:Person1 ex:hasPersonName "Marcus Tullius Cicero" .\n'
    )
    load_rdf(store, ttl)

    # Before materialization: no rdfs:label on Person1
    rows = list(store.query(
        'SELECT ?label WHERE { <http://example.org/Person1> <http://www.w3.org/2000/01/rdf-schema#label> ?label }'
    ))
    assert len(rows) == 0

    added = materialize(store)
    assert added > 0

    # After materialization: rdfs:label is inferred
    rows = list(store.query(
        'SELECT ?label WHERE { <http://example.org/Person1> <http://www.w3.org/2000/01/rdf-schema#label> ?label }'
    ))
    assert len(rows) == 1
    assert rows[0][0].value == "Marcus Tullius Cicero"


def test_materialize_subclassof(tmp_path):
    """rdfs:subClassOf materialization: Person subClassOf Agent."""
    store = create_store(tmp_path / "store")
    ttl = tmp_path / "data.ttl"
    ttl.write_text(
        '@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n'
        '@prefix ex: <http://example.org/> .\n'
        '\n'
        'ex:Person rdfs:subClassOf ex:Agent .\n'
        'ex:Person1 a ex:Person .\n'
    )
    load_rdf(store, ttl)

    # Before: not typed as Agent
    rows = list(store.query(
        'ASK { <http://example.org/Person1> a <http://example.org/Agent> }'
    ))
    assert not bool(rows)

    materialize(store)

    # After: inferred as Agent
    rows = list(store.query(
        'ASK { <http://example.org/Person1> a <http://example.org/Agent> }'
    ))
    assert bool(rows)


def test_materialize_no_axioms(tmp_path):
    """When data has no RDFS/OWL axioms, materialize is a no-op."""
    store = create_store(tmp_path / "store")
    ttl = tmp_path / "data.ttl"
    ttl.write_text(
        '@prefix ex: <http://example.org/> .\n'
        'ex:Thing1 a ex:Widget .\n'
    )
    load_rdf(store, ttl)
    original = len(store)
    added = materialize(store)
    assert added == 0
    assert len(store) == original


def test_materialize_idempotent(tmp_path):
    """Running materialize twice doesn't add duplicate triples."""
    store = create_store(tmp_path / "store")
    ttl = tmp_path / "data.ttl"
    ttl.write_text(
        '@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n'
        '@prefix ex: <http://example.org/> .\n'
        'ex:Person rdfs:subClassOf ex:Agent .\n'
        'ex:Person1 a ex:Person .\n'
    )
    load_rdf(store, ttl)
    first = materialize(store)
    count_after_first = len(store)
    second = materialize(store)
    assert second == 0
    assert len(store) == count_after_first
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/linked-past/tests/test_core_store.py -v -k "materialize"`
Expected: FAIL — `materialize` not importable.

- [ ] **Step 3: Implement materialize()**

In `packages/linked-past/linked_past/core/store.py`, add at the end of the file:

```python
def materialize(store: Store) -> int:
    """Run RDFS/OWL2 RL forward-chaining and insert inferred triples.

    Uses the `reasonable` library (Rust Datalog engine) to compute the
    deductive closure. Returns the number of genuinely new triples added.

    Fast no-op when the data contains no RDFS/OWL axioms.
    """
    import logging
    import tempfile

    import reasonable
    from pyoxigraph import BlankNode, Literal, NamedNode, Quad, RdfFormat, serialize

    logger = logging.getLogger(__name__)

    # Quick check: skip if no RDFS/OWL axioms present
    has_axioms = bool(list(store.query(
        "ASK { "
        "  { ?p <http://www.w3.org/2000/01/rdf-schema#subPropertyOf> ?q } "
        "  UNION "
        "  { ?c <http://www.w3.org/2000/01/rdf-schema#subClassOf> ?d } "
        "}"
    )))
    if not has_axioms:
        return 0

    # Serialize store to temp Turtle file (reasonable only reads ttl/n3)
    tmp = tempfile.NamedTemporaryFile(suffix=".ttl", delete=False)
    try:
        quads = store.query("CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o }")
        with open(tmp.name, "wb") as f:
            serialize(quads, f, format=RdfFormat.TURTLE)

        # Run OWL2 RL reasoning
        r = reasonable.PyReasoner()
        r.load_file(tmp.name)
        inferred = r.reason()
    finally:
        Path(tmp.name).unlink(missing_ok=True)

    # Insert genuinely new triples
    def _to_term(val: str):
        if val.startswith("http://") or val.startswith("https://"):
            return NamedNode(val)
        if val.startswith("_:"):
            return BlankNode(val[2:])
        return Literal(val)

    added = 0
    for s, p, o in inferred:
        try:
            subj = _to_term(s)
            pred = NamedNode(p)
            obj = _to_term(o)
            existing = list(store.quads_for_pattern(subj, pred, obj, None))
            if not existing:
                store.add(Quad(subj, pred, obj))
                added += 1
        except Exception:
            pass  # Skip malformed triples (e.g., literals in subject position)

    logger.info("materialize: %d new triples inferred (%d total from reasoner)", added, len(inferred))
    return added
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest packages/linked-past/tests/test_core_store.py -v -k "materialize"`
Expected: All 4 PASS.

- [ ] **Step 5: Run full test suite**

Run: `uv run pytest -x -v`
Expected: All PASS.

- [ ] **Step 6: Commit**

```bash
git add packages/linked-past/linked_past/core/store.py packages/linked-past/tests/test_core_store.py
git commit -m "feat: add RDFS/OWL2 RL materialization via reasonable"
```

---

### Task 3: Call materialize() from DatasetPlugin.load()

After bulk-loading raw triples, run materialization before returning the triple count.

**Files:**
- Modify: `packages/linked-past/linked_past/datasets/base.py:95-106`

- [ ] **Step 1: Update DatasetPlugin.load()**

In `packages/linked-past/linked_past/datasets/base.py`, replace the `load()` method:

```python
    def load(self, store: Store, rdf_path: Path) -> int:
        """Bulk-load all data files into Oxigraph store, return triple count.

        Loads all .ttl files in rdf_path's directory, skipping _* sidecars
        (e.g. _void.ttl, _schema.yaml). Single-file datasets load just the
        one file; multi-file datasets (like EDH) load all of them.

        After loading, runs RDFS/OWL2 RL materialization to infer triples
        from rdfs:subPropertyOf, rdfs:subClassOf, and other axioms present
        in the data.
        """
        from linked_past.core.store import materialize

        data_dir = rdf_path.parent
        ttl_files = [f for f in sorted(data_dir.glob("*.ttl")) if not f.name.startswith("_")]
        for ttl in ttl_files:
            store.bulk_load(path=str(ttl), format=self.rdf_format)
        materialize(store)
        return len(store)
```

- [ ] **Step 2: Run plugin tests**

Run: `uv run pytest packages/linked-past/tests/test_plugins.py -v`
Expected: All PASS — plugins still load and return triple counts, now including inferred triples.

- [ ] **Step 3: Run full test suite**

Run: `uv run pytest -x -v`
Expected: All PASS.

- [ ] **Step 4: Commit**

```bash
git add packages/linked-past/linked_past/datasets/base.py
git commit -m "feat: run RDFS materialization after dataset load"
```

---

### Task 4: Verify with Real Data

Verify that materialization works correctly against the fresh DPRR export and live Nomisma data.

**Files:**
- No code changes — verification only.

- [ ] **Step 1: Force-update DPRR with fresh export**

If the fresh `dprr.ttl` is available at the repo root, first copy it to the DPRR data dir, then force re-initialize to trigger the new load path:

```bash
uv run linked-past-server init --all
```

Or use the MCP `update_dataset` tool with `force=True` for DPRR.

- [ ] **Step 2: Verify DPRR rdfs:label inference**

Query DPRR for a Person's rdfs:label — this should now work even though the fresh export only has `:hasPersonName`:

```sparql
PREFIX vocab: <http://romanrepublic.ac.uk/rdf/ontology#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?name ?label WHERE {
  <http://romanrepublic.ac.uk/rdf/entity/Person/1> vocab:hasPersonName ?name .
  <http://romanrepublic.ac.uk/rdf/entity/Person/1> rdfs:label ?label .
}
```

Expected: Both `?name` and `?label` return `"IUNI0001 L. Iunius (46a, Supb. 5.356ff.) M. f. Brutus"`.

- [ ] **Step 3: Verify Nomisma hasDate inference**

Query Nomisma for objects with `nmo:hasDate` — this should now find objects that only assert `nmo:hasStartDate` (a subPropertyOf `nmo:hasDate`):

```sparql
PREFIX nmo: <http://nomisma.org/ontology#>
SELECT (COUNT(*) AS ?count) WHERE {
  ?s nmo:hasDate ?d .
}
```

Expected: Non-zero count (the 6,275 instances from hasStartDate/hasEndDate).

- [ ] **Step 4: Verify no-op for datasets without axioms**

Check logs during init for datasets like Pleiades or EDH — the materialize log line should show `0 new triples inferred`.

- [ ] **Step 5: Commit verification notes (optional)**

No code to commit — this is a manual verification step.

---

## Summary

| Task | What | Files |
|------|------|-------|
| 1 | Add `reasonable` dependency | `pyproject.toml` |
| 2 | Implement `materialize()` function | `store.py`, `test_core_store.py` |
| 3 | Call from `DatasetPlugin.load()` | `base.py` |
| 4 | Verify with real DPRR + Nomisma data | (manual) |

Performance: ~9 seconds for DPRR (427K → 749K triples). Fast no-op for datasets without RDFS/OWL axioms.
