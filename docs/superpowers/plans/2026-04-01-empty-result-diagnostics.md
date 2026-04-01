# Empty-Result Diagnostics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When a valid SPARQL query returns 0 rows, automatically diagnose why and return actionable hints alongside the empty result.

**Architecture:** A new `diagnose_empty_result()` function in `validate.py` runs two passes — free heuristic checks on the AST, then budget-capped ASK/COUNT probes against the store. Results append to the existing `QueryResult.errors` list. A JSONL log captures all zero-result queries for later analysis.

**Tech Stack:** Python, rdflib (AST parsing), pyoxigraph (ASK probes), existing schema_dict infrastructure.

---

### Task 1: Add `execute_ask` to store.py

**Files:**
- Modify: `packages/linked-past/linked_past/core/store.py:34-77`
- Test: `packages/linked-past/tests/test_core_store.py`

- [ ] **Step 1: Write failing test for execute_ask**

Add to `test_core_store.py`:

```python
def test_execute_ask_true(tmp_path):
    store_path = tmp_path / "store"
    store = create_store(store_path)
    ttl = tmp_path / "data.ttl"
    ttl.write_text(SAMPLE_TURTLE)
    load_rdf(store, ttl)
    from linked_past.core.store import execute_ask
    result = execute_ask(store, "ASK { ?s a <http://example.org/Widget> }")
    assert result is True


def test_execute_ask_false(tmp_path):
    store_path = tmp_path / "store"
    store = create_store(store_path)
    ttl = tmp_path / "data.ttl"
    ttl.write_text(SAMPLE_TURTLE)
    load_rdf(store, ttl)
    from linked_past.core.store import execute_ask
    result = execute_ask(store, "ASK { ?s a <http://example.org/Nonexistent> }")
    assert result is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/linked-past/tests/test_core_store.py::test_execute_ask_true packages/linked-past/tests/test_core_store.py::test_execute_ask_false -v`
Expected: FAIL with `ImportError: cannot import name 'execute_ask'`

- [ ] **Step 3: Implement execute_ask**

Add to `packages/linked-past/linked_past/core/store.py` after `execute_query`:

```python
from pyoxigraph import QueryBoolean


def execute_ask(store: Store, sparql: str) -> bool:
    """Execute a SPARQL ASK query and return True/False."""
    result = store.query(sparql)
    if not isinstance(result, QueryBoolean):
        raise ValueError(
            "Expected ASK query but got a non-boolean result. "
            "Use execute_query() for SELECT queries."
        )
    return bool(result)
```

- [ ] **Step 3b: Add test for non-ASK rejection**

Add to `test_core_store.py`:

```python
def test_execute_ask_rejects_select(tmp_path):
    store_path = tmp_path / "store"
    store = create_store(store_path)
    ttl = tmp_path / "data.ttl"
    ttl.write_text(SAMPLE_TURTLE)
    load_rdf(store, ttl)
    from linked_past.core.store import execute_ask
    with pytest.raises(ValueError, match="Expected ASK"):
        execute_ask(store, "SELECT ?s WHERE { ?s ?p ?o }")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/linked-past/tests/test_core_store.py -v`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add packages/linked-past/linked_past/core/store.py packages/linked-past/tests/test_core_store.py
git commit -m "feat: add execute_ask for SPARQL ASK queries"
```

---

### Task 2: DiagnosticResult dataclass and diagnose_empty_result skeleton

**Files:**
- Modify: `packages/linked-past/linked_past/core/validate.py`
- Test: `packages/linked-past/tests/test_core_validate.py`

- [ ] **Step 1: Write failing test**

Add to `test_core_validate.py`:

```python
from linked_past.core.validate import DiagnosticResult, diagnose_empty_result


def test_diagnose_empty_result_returns_dataclass(tmp_path):
    store_path = tmp_path / "store"
    store = create_store(store_path)
    ttl = tmp_path / "data.ttl"
    ttl.write_text(SAMPLE_TURTLE)
    load_rdf(store, ttl)
    sd = build_schema_dict(SCHEMAS, PREFIXES)
    sparql = "PREFIX ex: <http://example.org/>\nSELECT ?w WHERE { ?w a ex:Gadget }"
    result = diagnose_empty_result(sparql, store, sd, PREFIXES)
    assert isinstance(result, DiagnosticResult)
    assert isinstance(result.hints, list)
    assert isinstance(result.probe_results, dict)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/linked-past/tests/test_core_validate.py::test_diagnose_empty_result_returns_dataclass -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement dataclass and skeleton**

Add to `packages/linked-past/linked_past/core/validate.py`:

```python
@dataclass
class DiagnosticResult:
    """Result of diagnosing why a query returned 0 rows."""
    hints: list[str] = field(default_factory=list)
    probe_results: dict[str, bool] = field(default_factory=dict)


def diagnose_empty_result(
    sparql: str,
    store,
    schema_dict: dict,
    prefix_map: dict[str, str],
    dataset: str | None = None,
    semantic_hints: list[str] | None = None,
    budget_ms: int = 500,
) -> DiagnosticResult:
    """Diagnose why a valid SPARQL query returned 0 rows.

    Runs two passes:
    1. Heuristic checks (free) — AST + schema analysis
    2. Probe queries (budget-capped) — ASK queries against the store
    """
    result = DiagnosticResult()
    result.hints.extend(_run_heuristics(sparql, schema_dict, prefix_map, dataset, semantic_hints))
    probe_hints, probe_results = _run_probes(sparql, store, budget_ms)
    result.hints.extend(probe_hints)
    result.probe_results = probe_results
    return result


def _run_heuristics(
    sparql: str,
    schema_dict: dict,
    prefix_map: dict[str, str],
    dataset: str | None,
    semantic_hints: list[str] | None,
) -> list[str]:
    """Zero-cost heuristic checks on the SPARQL AST."""
    return []


def _run_probes(
    sparql: str,
    store,
    budget_ms: int,
) -> tuple[list[str], dict[str, bool]]:
    """Budget-capped diagnostic ASK queries."""
    return [], {}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/linked-past/tests/test_core_validate.py::test_diagnose_empty_result_returns_dataclass -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/linked-past/linked_past/core/validate.py packages/linked-past/tests/test_core_validate.py
git commit -m "feat: add DiagnosticResult dataclass and diagnose_empty_result skeleton"
```

---

### Task 3: Heuristic — open-world boolean escalation

**Files:**
- Modify: `packages/linked-past/linked_past/core/validate.py` (`_run_heuristics`)
- Test: `packages/linked-past/tests/test_core_validate.py`

- [ ] **Step 1: Write failing test**

```python
def test_heuristic_escalates_open_world_boolean():
    """When pre-execution warned about open-world boolean and result is empty, escalate."""
    schemas = {
        "Person": {
            "uri": "ex:Person",
            "properties": [
                {"pred": "ex:isPatrician", "range": "xsd:boolean", "open_world": True},
            ],
        },
    }
    sd = build_schema_dict(schemas, PREFIXES)
    sparql = (
        "PREFIX ex: <http://example.org/>\n"
        "SELECT ?p WHERE { ?p a ex:Person ; ex:isPatrician ?v . FILTER(?v = false) }"
    )
    semantic_hints = [
        "Hint: 'isPatrician' only stores true values (open-world boolean). "
        "FILTER(?v = false) returns 0 rows. "
        "Use: FILTER NOT EXISTS { ?p <http://example.org/isPatrician> true }"
    ]
    result = diagnose_empty_result(sparql, None, sd, PREFIXES, semantic_hints=semantic_hints)
    assert any("open-world" in h.lower() and "likely the cause" in h.lower() for h in result.hints)


def test_heuristic_no_escalation_without_prior_warning():
    """No escalation if pre-execution didn't warn about open-world."""
    schemas = {
        "Person": {
            "uri": "ex:Person",
            "properties": [
                {"pred": "ex:hasName", "range": "xsd:string"},
            ],
        },
    }
    sd = build_schema_dict(schemas, PREFIXES)
    sparql = (
        "PREFIX ex: <http://example.org/>\n"
        "SELECT ?p WHERE { ?p a ex:Person ; ex:hasName ?n . FILTER(?n = \"Nobody\") }"
    )
    result = diagnose_empty_result(sparql, None, sd, PREFIXES, semantic_hints=[])
    assert not any("open-world" in h.lower() for h in result.hints)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/linked-past/tests/test_core_validate.py::test_heuristic_escalates_open_world_boolean packages/linked-past/tests/test_core_validate.py::test_heuristic_no_escalation_without_prior_warning -v`
Expected: FAIL (hints list is empty)

- [ ] **Step 3: Implement open-world escalation in _run_heuristics**

Replace `_run_heuristics` in `validate.py`:

```python
def _run_heuristics(
    sparql: str,
    schema_dict: dict,
    prefix_map: dict[str, str],
    dataset: str | None,
    semantic_hints: list[str] | None,
) -> list[str]:
    """Zero-cost heuristic checks on the SPARQL AST."""
    hints: list[str] = []

    # Parse triples and variable types once for all heuristics
    triples: list[tuple] = []
    var_types: dict[str, list[str]] = {}
    try:
        triples = _collect_triples(sparql)
        for s, p, o in triples:
            if p == RDF_TYPE and isinstance(s, Variable) and isinstance(o, URIRef):
                var_types.setdefault(str(s), []).append(str(o))
    except Exception:
        pass

    # Also build var_preds map (variable -> predicates that produce it)
    var_preds: dict[str, list[str]] = {}
    for s, p, o in triples:
        if isinstance(p, URIRef) and isinstance(o, Variable):
            var_preds.setdefault(str(o), []).append(str(p))

    # 1. Escalate open-world boolean warnings from pre-execution
    if semantic_hints:
        for hint in semantic_hints:
            if "open-world boolean" in hint.lower():
                hints.append(
                    "Diagnostic: This query returned 0 rows. The open-world boolean "
                    "warning above is likely the cause — the property only stores "
                    "true values, so filtering for false always yields nothing."
                )
                break

    return hints
```

**Important:** `triples`, `var_types`, and `var_preds` are now computed once at the top and reused by all subsequent heuristic tasks. Later tasks (4, 5, 6, 13) add checks after the open-world block using these shared variables.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/linked-past/tests/test_core_validate.py::test_heuristic_escalates_open_world_boolean packages/linked-past/tests/test_core_validate.py::test_heuristic_no_escalation_without_prior_warning -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/linked-past/linked_past/core/validate.py packages/linked-past/tests/test_core_validate.py
git commit -m "feat: heuristic escalation for open-world boolean warnings"
```

---

### Task 4: Heuristic — contradictory type constraints

**Files:**
- Modify: `packages/linked-past/linked_past/core/validate.py` (`_run_heuristics`)
- Test: `packages/linked-past/tests/test_core_validate.py`

- [ ] **Step 1: Write failing test**

```python
def test_heuristic_contradictory_types():
    """Detect when a variable is bound to two incompatible rdf:type classes."""
    schemas = {
        "Person": {
            "uri": "ex:Person",
            "properties": [{"pred": "ex:hasName", "range": "xsd:string"}],
        },
        "PostAssertion": {
            "uri": "ex:PostAssertion",
            "properties": [{"pred": "ex:hasOffice", "range": "xsd:string"}],
        },
    }
    sd = build_schema_dict(schemas, PREFIXES)
    sparql = (
        "PREFIX ex: <http://example.org/>\n"
        "SELECT ?x WHERE { ?x a ex:Person . ?x a ex:PostAssertion }"
    )
    result = diagnose_empty_result(sparql, None, sd, PREFIXES)
    assert any("contradictory" in h.lower() or "both" in h.lower() for h in result.hints)


def test_heuristic_no_contradiction_single_type():
    schemas = {
        "Person": {
            "uri": "ex:Person",
            "properties": [{"pred": "ex:hasName", "range": "xsd:string"}],
        },
    }
    sd = build_schema_dict(schemas, PREFIXES)
    sparql = (
        "PREFIX ex: <http://example.org/>\n"
        "SELECT ?x WHERE { ?x a ex:Person ; ex:hasName ?n }"
    )
    result = diagnose_empty_result(sparql, None, sd, PREFIXES)
    assert not any("contradictory" in h.lower() or "both" in h.lower() for h in result.hints)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/linked-past/tests/test_core_validate.py::test_heuristic_contradictory_types packages/linked-past/tests/test_core_validate.py::test_heuristic_no_contradiction_single_type -v`
Expected: FAIL (hints list is empty)

- [ ] **Step 3: Implement contradictory type detection**

Add to `_run_heuristics` after the open-world check. Note: `triples` and `var_types` are already computed at the top of the function (from Task 3).

```python
    # 2. Contradictory type constraints
    for var_name, types in var_types.items():
        if len(types) > 1:
            # Only flag if both types are known dataset classes (not universal)
            known = [t for t in types if t in schema_dict]
            if len(known) > 1:
                names = [_local_name(t) for t in known]
                hints.append(
                    f"Diagnostic: ?{var_name} is typed as both {' and '.join(names)}. "
                    f"No entity is likely to satisfy both types simultaneously. "
                    f"Use separate variables for each type."
                )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/linked-past/tests/test_core_validate.py::test_heuristic_contradictory_types packages/linked-past/tests/test_core_validate.py::test_heuristic_no_contradiction_single_type -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/linked-past/linked_past/core/validate.py packages/linked-past/tests/test_core_validate.py
git commit -m "feat: heuristic for contradictory type constraints"
```

---

### Task 5: Heuristic — date range sanity (DPRR negative integers)

**Files:**
- Modify: `packages/linked-past/linked_past/core/validate.py` (`_run_heuristics`)
- Test: `packages/linked-past/tests/test_core_validate.py`

- [ ] **Step 1: Write failing test**

```python
def test_heuristic_date_range_positive_on_bc_field():
    """Detect FILTER with positive integer on a field documented as 'Negative = BC'."""
    schemas = {
        "Person": {
            "uri": "ex:Person",
            "properties": [
                {
                    "pred": "ex:hasEraFrom",
                    "range": "xsd:integer",
                    "comment": "Era start. Negative = BC.",
                },
            ],
        },
    }
    sd = build_schema_dict(schemas, PREFIXES)
    sparql = (
        "PREFIX ex: <http://example.org/>\n"
        "SELECT ?p WHERE { ?p a ex:Person ; ex:hasEraFrom ?era . FILTER(?era > 100) }"
    )
    result = diagnose_empty_result(sparql, None, sd, PREFIXES)
    assert any("negative" in h.lower() and "bc" in h.lower() for h in result.hints)


def test_heuristic_date_range_negative_no_warning():
    """No warning when using negative integers on a BC date field."""
    schemas = {
        "Person": {
            "uri": "ex:Person",
            "properties": [
                {
                    "pred": "ex:hasEraFrom",
                    "range": "xsd:integer",
                    "comment": "Era start. Negative = BC.",
                },
            ],
        },
    }
    sd = build_schema_dict(schemas, PREFIXES)
    sparql = (
        "PREFIX ex: <http://example.org/>\n"
        "SELECT ?p WHERE { ?p a ex:Person ; ex:hasEraFrom ?era . FILTER(?era < -100) }"
    )
    result = diagnose_empty_result(sparql, None, sd, PREFIXES)
    assert not any("negative" in h.lower() and "bc" in h.lower() for h in result.hints)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/linked-past/tests/test_core_validate.py::test_heuristic_date_range_positive_on_bc_field packages/linked-past/tests/test_core_validate.py::test_heuristic_date_range_negative_no_warning -v`
Expected: FAIL

- [ ] **Step 3: Implement date range sanity check**

Add to `_run_heuristics` after the contradictory types check. Note: `triples`, `var_types`, and `var_preds` are already computed at the top of the function (from Task 3).

```python
    # 3. Date range sanity — positive integers on BC date fields
    # Find date predicates with "negative = bc" in comment
    bc_preds: set[str] = set()
    for class_uri, preds in schema_dict.items():
        for pred_uri, pred_info in preds.items():
            if pred_uri == "_meta" or not isinstance(pred_info, dict):
                continue
            comment = pred_info.get("comment", "").lower()
            if "negative" in comment and "bc" in comment:
                bc_preds.add(pred_uri)

    if bc_preds:
        # Look for FILTER with positive integer comparisons on BC date variables
        filter_pattern = re.compile(
            r"FILTER\s*\(.*?\?\s*(\w+)\s*(?:>|>=|=)\s*(\d+)",
            re.IGNORECASE,
        )
        for match in filter_pattern.finditer(sparql):
            var_name = match.group(1)
            value = int(match.group(2))
            if value > 0:
                for pred_uri in var_preds.get(var_name, []):
                    if pred_uri in bc_preds:
                        pred_local = _local_name(pred_uri)
                        hints.append(
                            f"Diagnostic: '{pred_local}' uses negative integers for BC dates. "
                            f"Your filter compares ?{var_name} against {value} (a positive "
                            f"number, meaning AD). For BC dates, use negative values "
                            f"(e.g., -100 for 100 BC)."
                        )
                        break
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/linked-past/tests/test_core_validate.py::test_heuristic_date_range_positive_on_bc_field packages/linked-past/tests/test_core_validate.py::test_heuristic_date_range_negative_no_warning -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/linked-past/linked_past/core/validate.py packages/linked-past/tests/test_core_validate.py
git commit -m "feat: heuristic for positive integers on BC date fields"
```

---

### Task 6: Heuristic — date literal padding (xsd:gYear, xsd:date, xsd:dateTime)

**Files:**
- Modify: `packages/linked-past/linked_past/core/validate.py` (`_run_heuristics`)
- Test: `packages/linked-past/tests/test_core_validate.py`

- [ ] **Step 1: Write failing tests**

```python
def test_heuristic_gyear_unpadded():
    """Detect unpadded year in FILTER on xsd:gYear predicate."""
    schemas = {
        "TypeSeries": {
            "uri": "ex:TypeSeries",
            "properties": [
                {"pred": "ex:hasStartDate", "range": "xsd:gYear", "comment": "Earliest date"},
            ],
        },
    }
    sd = build_schema_dict(schemas, PREFIXES)
    sparql = (
        "PREFIX ex: <http://example.org/>\n"
        'SELECT ?t WHERE { ?t a ex:TypeSeries ; ex:hasStartDate ?d . FILTER(?d < "-44") }'
    )
    result = diagnose_empty_result(sparql, None, sd, PREFIXES)
    assert any("padded" in h.lower() or "gYear" in h.lower() for h in result.hints)


def test_heuristic_gyear_properly_padded():
    """No warning when year is properly padded."""
    schemas = {
        "TypeSeries": {
            "uri": "ex:TypeSeries",
            "properties": [
                {"pred": "ex:hasStartDate", "range": "xsd:gYear", "comment": "Earliest date"},
            ],
        },
    }
    sd = build_schema_dict(schemas, PREFIXES)
    sparql = (
        "PREFIX ex: <http://example.org/>\n"
        'SELECT ?t WHERE { ?t a ex:TypeSeries ; ex:hasStartDate ?d . FILTER(?d < "-0044"^^xsd:gYear) }'
    )
    result = diagnose_empty_result(sparql, None, sd, PREFIXES)
    assert not any("padded" in h.lower() for h in result.hints)


def test_heuristic_xsd_date_bare_year():
    """Detect bare year comparison on xsd:date predicate (needs full ISO 8601)."""
    schemas = {
        "Event": {
            "uri": "ex:Event",
            "properties": [
                {"pred": "ex:hasDate", "range": "xsd:date", "comment": "Event date"},
            ],
        },
    }
    sd = build_schema_dict(schemas, PREFIXES)
    sparql = (
        "PREFIX ex: <http://example.org/>\n"
        'SELECT ?e WHERE { ?e a ex:Event ; ex:hasDate ?d . FILTER(?d < "-44") }'
    )
    result = diagnose_empty_result(sparql, None, sd, PREFIXES)
    assert any("padded" in h.lower() or "date" in h.lower() for h in result.hints)


def test_heuristic_xsd_date_properly_formatted():
    """No warning when xsd:date is full ISO 8601."""
    schemas = {
        "Event": {
            "uri": "ex:Event",
            "properties": [
                {"pred": "ex:hasDate", "range": "xsd:date", "comment": "Event date"},
            ],
        },
    }
    sd = build_schema_dict(schemas, PREFIXES)
    sparql = (
        "PREFIX ex: <http://example.org/>\n"
        'SELECT ?e WHERE { ?e a ex:Event ; ex:hasDate ?d . FILTER(?d < "-0044-03-15"^^xsd:date) }'
    )
    result = diagnose_empty_result(sparql, None, sd, PREFIXES)
    assert not any("padded" in h.lower() for h in result.hints)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/linked-past/tests/test_core_validate.py::test_heuristic_gyear_unpadded packages/linked-past/tests/test_core_validate.py::test_heuristic_gyear_properly_padded -v`
Expected: FAIL

- [ ] **Step 3: Implement date literal padding check**

Add to `_run_heuristics` after the date range check. Note: `var_preds` is already computed at the top of the function (from Task 3).

```python
    # 4. Date literal padding — detect unpadded year in gYear, date, dateTime literals
    _DATE_SUFFIXES = ("gYear", "date", "dateTime")
    date_preds: dict[str, str] = {}  # pred_uri -> datatype suffix
    for class_uri, preds in schema_dict.items():
        for pred_uri, pred_info in preds.items():
            if pred_uri == "_meta" or not isinstance(pred_info, dict):
                continue
            dt = pred_info.get("datatype", "")
            if dt:
                for suffix in _DATE_SUFFIXES:
                    if dt.endswith(suffix):
                        date_preds[pred_uri] = suffix
                        break

    if date_preds:
        # Match patterns like: FILTER(?d < "-44") or FILTER(?d = "-44")
        # Captures the variable name and the literal year (1-3 digit, possibly negative)
        date_filter = re.compile(
            r"""FILTER\s*\(.*?\?(\w+)\s*(?:[<>=!]+)\s*"(-?\d{1,3})(?:["-])""",
            re.IGNORECASE,
        )
        for match in date_filter.finditer(sparql):
            var_name = match.group(1)
            year_val = match.group(2)
            for pred_uri in var_preds.get(var_name, []):
                if pred_uri in date_preds:
                    pred_local = _local_name(pred_uri)
                    dtype = date_preds[pred_uri]
                    padded = year_val.zfill(4) if not year_val.startswith("-") else "-" + year_val[1:].zfill(4)
                    if dtype == "gYear":
                        example = f'"{padded}"^^xsd:gYear'
                    else:
                        # xsd:date and xsd:dateTime need full ISO 8601
                        example = f'"{padded}-01-01"^^xsd:{dtype}'
                    hints.append(
                        f"Diagnostic: '{pred_local}' uses xsd:{dtype} with zero-padded 4-digit years. "
                        f'Your value "{year_val}" needs padding: use {example} '
                        f'(e.g., "-0044-03-15"^^xsd:date for 44 BC).'
                    )
                    break
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/linked-past/tests/test_core_validate.py::test_heuristic_gyear_unpadded packages/linked-past/tests/test_core_validate.py::test_heuristic_gyear_properly_padded -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/linked-past/linked_past/core/validate.py packages/linked-past/tests/test_core_validate.py
git commit -m "feat: heuristic for unpadded xsd:gYear and xsd:date literals"
```

---

### Task 7: Probe — base pattern ASK

**Files:**
- Modify: `packages/linked-past/linked_past/core/validate.py` (`_run_probes`)
- Test: `packages/linked-past/tests/test_core_validate.py`

- [ ] **Step 1: Write failing tests**

```python
def test_probe_base_pattern_matches(tmp_path):
    """When base pattern matches but filters exclude all, report filter problem."""
    store_path = tmp_path / "store"
    store = create_store(store_path)
    ttl = tmp_path / "data.ttl"
    ttl.write_text(SAMPLE_TURTLE)
    load_rdf(store, ttl)
    sd = build_schema_dict(SCHEMAS, PREFIXES)
    # Widget exists, but no Widget has label "Nonexistent"
    sparql = (
        "PREFIX ex: <http://example.org/>\n"
        "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n"
        'SELECT ?w WHERE { ?w a ex:Widget ; rdfs:label ?l . FILTER(?l = "Nonexistent") }'
    )
    result = diagnose_empty_result(sparql, store, sd, PREFIXES)
    assert result.probe_results.get("base_pattern_matches") is True
    assert any("filter" in h.lower() for h in result.hints)


def test_probe_base_pattern_no_match(tmp_path):
    """When base pattern itself doesn't match, report pattern problem."""
    store_path = tmp_path / "store"
    store = create_store(store_path)
    ttl = tmp_path / "data.ttl"
    ttl.write_text(SAMPLE_TURTLE)
    load_rdf(store, ttl)
    sd = build_schema_dict(SCHEMAS, PREFIXES)
    sparql = (
        "PREFIX ex: <http://example.org/>\n"
        "SELECT ?w WHERE { ?w a ex:Gadget }"
    )
    result = diagnose_empty_result(sparql, store, sd, PREFIXES)
    assert result.probe_results.get("base_pattern_matches") is False
    assert any("base graph pattern" in h.lower() or "no entities match" in h.lower() for h in result.hints)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/linked-past/tests/test_core_validate.py::test_probe_base_pattern_matches packages/linked-past/tests/test_core_validate.py::test_probe_base_pattern_no_match -v`
Expected: FAIL

- [ ] **Step 3: Implement base pattern ASK probe**

Replace `_run_probes` in `validate.py`:

```python
import time
from copy import deepcopy

from rdflib.plugins.sparql.algebra import translateQuery
from rdflib.plugins.sparql.parser import parseQuery
from rdflib.plugins.sparql.parserutils import CompValue


def _collect_bgp_triples(algebra, skip_optional: bool = True) -> list[tuple]:
    """Recursively collect triple patterns from BGP nodes in SPARQL algebra.

    If skip_optional is True (default), triples inside OPTIONAL (LeftJoin.p2)
    are excluded so that base pattern ASK probes don't turn optional patterns
    into required joins.
    """
    triples = []

    def _walk(node, in_optional: bool = False):
        if isinstance(node, CompValue):
            if node.name == "BGP" and not in_optional:
                for t in node.get("triples", []):
                    triples.append(t)
            elif node.name == "LeftJoin" and skip_optional:
                # p1 is the required side, p2 is the optional side
                _walk(node.get("p1"), in_optional=False)
                _walk(node.get("p2"), in_optional=True)
                return
            for key in node:
                _walk(node[key], in_optional)
        elif isinstance(node, list):
            for item in node:
                _walk(item, in_optional)

    _walk(algebra)
    return triples


def _term_to_sparql(term, bnode_counter: dict) -> str:
    """Convert an rdflib term to a SPARQL string representation."""
    from rdflib.term import BNode

    if isinstance(term, Variable):
        return f"?{term}"
    elif isinstance(term, URIRef):
        return f"<{term}>"
    elif isinstance(term, BNode):
        # Replace blank nodes with fresh variables
        key = str(term)
        if key not in bnode_counter:
            bnode_counter[key] = f"?_bnode_{len(bnode_counter)}"
        return bnode_counter[key]
    elif isinstance(term, Literal):
        if term.datatype:
            return f'"{term}"^^<{term.datatype}>'
        elif term.language:
            return f'"{term}"@{term.language}'
        else:
            return f'"{term}"'
    else:
        return f'"{term}"'


def _build_ask_from_triples(
    triples: list[tuple],
    prefix_decls: str,
) -> str:
    """Build an ASK query from raw triple patterns and prefix declarations."""
    bnode_counter: dict = {}
    patterns = []
    for s, p, o in triples:
        s_str = _term_to_sparql(s, bnode_counter)
        p_str = _term_to_sparql(p, bnode_counter)
        o_str = _term_to_sparql(o, bnode_counter)
        patterns.append(f"  {s_str} {p_str} {o_str} .")
    body = "\n".join(patterns)
    return f"{prefix_decls}\nASK {{\n{body}\n}}"


def _strip_filters_algebra(sparql: str) -> str | None:
    """Use rdflib's algebra to extract base graph pattern without filters.

    Parses the SPARQL, collects all BGP triples from the algebra tree
    (ignoring Filter, Extend, OrderBy, Slice nodes), and rebuilds as an ASK query.
    Returns None if parsing fails or no triples found.
    """
    try:
        parsed = parseQuery(sparql)
        q = translateQuery(parsed)
        triples = _collect_bgp_triples(q.algebra)
        if not triples:
            return None

        prefix_decls = []
        for match in re.finditer(r"PREFIX\s+\w+:\s*<[^>]+>", sparql, re.IGNORECASE):
            prefix_decls.append(match.group(0))
        prefix_str = "\n".join(prefix_decls)

        return _build_ask_from_triples(triples, prefix_str)
    except Exception:
        return None


def _extract_filter_clauses(sparql: str) -> list[tuple[int, int, str]]:
    """Extract FILTER clause positions and text using brace/paren counting.

    Returns list of (start, end, filter_text) tuples.
    Handles nested parentheses and braces correctly.
    """
    filters: list[tuple[int, int, str]] = []
    upper = sparql.upper()
    i = 0
    while i < len(upper):
        # Find next FILTER keyword
        idx = upper.find("FILTER", i)
        if idx == -1:
            break
        # Verify it's a keyword (not inside a URI or string)
        if idx > 0 and upper[idx - 1].isalnum():
            i = idx + 6
            continue

        # Find the opening delimiter after FILTER (skip whitespace and NOT EXISTS)
        j = idx + 6
        while j < len(sparql) and sparql[j] in " \t\n\r":
            j += 1

        if j >= len(sparql):
            break

        # Determine delimiter type
        if sparql[j] == "(":
            open_char, close_char = "(", ")"
        elif upper[j:].startswith("NOT") or upper[j:].startswith("EXISTS"):
            # FILTER NOT EXISTS { ... } or FILTER EXISTS { ... }
            brace_start = sparql.find("{", j)
            if brace_start == -1:
                i = j
                continue
            j = brace_start
            open_char, close_char = "{", "}"
        else:
            i = j
            continue

        # Count delimiters to find matching close
        depth = 0
        k = j
        while k < len(sparql):
            if sparql[k] == open_char:
                depth += 1
            elif sparql[k] == close_char:
                depth -= 1
                if depth == 0:
                    filters.append((idx, k + 1, sparql[idx:k + 1]))
                    break
            k += 1

        i = k + 1 if k < len(sparql) else len(sparql)
    return filters


def _run_probes(
    sparql: str,
    store,
    budget_ms: int,
) -> tuple[list[str], dict[str, bool]]:
    """Budget-capped diagnostic ASK queries."""
    if store is None:
        return [], {}

    from linked_past.core.store import execute_ask

    hints: list[str] = []
    probe_results: dict[str, bool] = {}
    t0 = time.monotonic()

    def budget_remaining() -> int:
        elapsed = (time.monotonic() - t0) * 1000
        return int(budget_ms - elapsed)

    # Probe 1: ASK on base pattern (no filters) using algebra-based stripping
    ask_sparql = _strip_filters_algebra(sparql)
    if ask_sparql and budget_remaining() > 0:
        try:
            base_matches = execute_ask(store, ask_sparql)
            probe_results["base_pattern_matches"] = base_matches
            if base_matches:
                hints.append(
                    "Diagnostic: The base graph pattern matches data, but filters "
                    "exclude all results. Check your FILTER conditions."
                )
            else:
                hints.append(
                    "Diagnostic: No entities match the base graph pattern (before "
                    "any filters). The triple patterns themselves have no matches — "
                    "check class names, predicates, and join paths."
                )
        except Exception as e:
            logger.debug("Base pattern probe failed: %s", e)

    return hints, probe_results
```

- [ ] **Step 3b: Add edge case tests for nested filters and OPTIONAL**

```python
def test_strip_filters_nested_parens(tmp_path):
    """_strip_filters_algebra handles nested parentheses in FILTER."""
    store_path = tmp_path / "store"
    store = create_store(store_path)
    ttl = tmp_path / "data.ttl"
    ttl.write_text(SAMPLE_TURTLE)
    load_rdf(store, ttl)
    sd = build_schema_dict(SCHEMAS, PREFIXES)
    sparql = (
        "PREFIX ex: <http://example.org/>\n"
        "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n"
        "SELECT ?w WHERE { ?w a ex:Widget ; rdfs:label ?l . "
        'FILTER(?l = "X" && (?l != "Y" || ?l != "Z")) }'
    )
    result = diagnose_empty_result(sparql, store, sd, PREFIXES)
    # Should successfully probe the base pattern (Widget exists)
    assert result.probe_results.get("base_pattern_matches") is True


def test_strip_filters_with_optional(tmp_path):
    """Base pattern ASK should not require OPTIONAL patterns."""
    store_path = tmp_path / "store"
    store = create_store(store_path)
    ttl = tmp_path / "data.ttl"
    ttl.write_text(SAMPLE_TURTLE)
    load_rdf(store, ttl)
    sd = build_schema_dict(SCHEMAS, PREFIXES)
    # Widget exists but has no hasColor. OPTIONAL { hasColor } should not
    # make the base pattern fail — only required patterns matter.
    sparql = (
        "PREFIX ex: <http://example.org/>\n"
        "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n"
        "SELECT ?w ?c WHERE { ?w a ex:Widget . "
        "OPTIONAL { ?w ex:hasColor ?c } "
        'FILTER(?c = "red") }'
    )
    result = diagnose_empty_result(sparql, store, sd, PREFIXES)
    # Base pattern (just ?w a ex:Widget) should match — OPTIONAL excluded
    assert result.probe_results.get("base_pattern_matches") is True
    assert any("filter" in h.lower() for h in result.hints)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/linked-past/tests/test_core_validate.py::test_probe_base_pattern_matches packages/linked-past/tests/test_core_validate.py::test_probe_base_pattern_no_match packages/linked-past/tests/test_core_validate.py::test_strip_filters_nested_parens packages/linked-past/tests/test_core_validate.py::test_strip_filters_with_optional -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/linked-past/linked_past/core/validate.py packages/linked-past/tests/test_core_validate.py
git commit -m "feat: base pattern ASK probe for empty results"
```

---

### Task 8: Probe — filter isolation

**Files:**
- Modify: `packages/linked-past/linked_past/core/validate.py` (`_run_probes`)
- Test: `packages/linked-past/tests/test_core_validate.py`

- [ ] **Step 1: Write failing test**

```python
def test_probe_identifies_restrictive_filter(tmp_path):
    """When stripping a specific filter produces results, identify it."""
    store_path = tmp_path / "store"
    store = create_store(store_path)
    ttl = tmp_path / "data.ttl"
    # Widget One has label "One"
    ttl.write_text(SAMPLE_TURTLE)
    load_rdf(store, ttl)
    sd = build_schema_dict(SCHEMAS, PREFIXES)
    sparql = (
        "PREFIX ex: <http://example.org/>\n"
        "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n"
        'SELECT ?w WHERE { ?w a ex:Widget ; rdfs:label ?l . FILTER(?l = "Nonexistent") }'
    )
    result = diagnose_empty_result(sparql, store, sd, PREFIXES)
    # Should identify the specific filter
    assert any("Nonexistent" in h or "filter" in h.lower() for h in result.hints)
    assert any(k.startswith("filter_") for k in result.probe_results)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/linked-past/tests/test_core_validate.py::test_probe_identifies_restrictive_filter -v`
Expected: FAIL (no `filter_` keys in probe_results)

- [ ] **Step 3: Implement filter isolation**

Add to `_run_probes`, after the base pattern probe, inside the `if base_matches:` branch.

Uses `_extract_filter_clauses()` (brace-counting, defined in Task 7) to correctly handle nested parens/braces. After textually removing one filter, converts SELECT→ASK using `_select_to_ask()` which preserves the remaining filters intact (unlike `_strip_filters_algebra` which would remove all of them):

```python
def _select_to_ask(sparql: str) -> str | None:
    """Convert a SELECT query to ASK by replacing the projection.

    Removes SELECT ... WHERE, ORDER BY, LIMIT, OFFSET but keeps
    all FILTER, OPTIONAL, and other WHERE-clause content intact.
    Returns None if the query can't be converted.
    """
    try:
        # Replace SELECT ... WHERE with ASK WHERE
        result = re.sub(
            r"SELECT\s+.*?(?=WHERE)",
            "ASK ",
            sparql,
            count=1,
            flags=re.IGNORECASE | re.DOTALL,
        )
        # Remove trailing ORDER BY, LIMIT, OFFSET (outside the WHERE block)
        # Find the last } and strip everything after it except whitespace
        last_brace = result.rfind("}")
        if last_brace == -1:
            return None
        result = result[:last_brace + 1]
        return result
    except Exception:
        return None
```

Add this helper before `_run_probes`, then use it in the filter isolation:

```python
            if base_matches and budget_remaining() > 0:
                # Probe 2: Strip individual filters to find the culprit
                filters = _extract_filter_clauses(sparql)
                for i, (start, end, filter_text) in enumerate(filters):
                    if budget_remaining() <= 0:
                        hints.append(
                            f"Diagnostic: Budget exhausted after checking {i}/{len(filters)} filters."
                        )
                        break
                    # Rebuild query without this one filter, keep other filters intact
                    stripped = sparql[:start] + sparql[end:]
                    stripped_ask = _select_to_ask(stripped)
                    if not stripped_ask:
                        continue
                    try:
                        matches = execute_ask(store, stripped_ask)
                        probe_results[f"filter_{i}_stripped_matches"] = matches
                        if matches:
                            display = filter_text.strip()
                            if len(display) > 100:
                                display = display[:100] + "..."
                            hints.append(
                                f"Diagnostic: Removing `{display}` produces results. "
                                f"This filter is likely too restrictive."
                            )
                    except Exception as e:
                        logger.debug("Filter isolation probe %d failed: %s", i, e)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/linked-past/tests/test_core_validate.py::test_probe_identifies_restrictive_filter -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/linked-past/linked_past/core/validate.py packages/linked-past/tests/test_core_validate.py
git commit -m "feat: filter isolation probe for empty results"
```

---

### Task 9: Probe — join decomposition

**Files:**
- Modify: `packages/linked-past/linked_past/core/validate.py` (`_run_probes`)
- Test: `packages/linked-past/tests/test_core_validate.py`

- [ ] **Step 1: Write failing test**

```python
def test_probe_join_decomposition(tmp_path):
    """When base pattern fails, identify which triple pattern has no matches."""
    store_path = tmp_path / "store"
    store = create_store(store_path)
    ttl = tmp_path / "data.ttl"
    ttl.write_text(SAMPLE_TURTLE)
    load_rdf(store, ttl)
    sd = build_schema_dict(SCHEMAS, PREFIXES)
    # Widget exists, but ex:hasColor is not in the data
    sparql = (
        "PREFIX ex: <http://example.org/>\n"
        "SELECT ?w ?c WHERE { ?w a ex:Widget ; ex:hasColor ?c }"
    )
    result = diagnose_empty_result(sparql, store, sd, PREFIXES)
    assert result.probe_results.get("base_pattern_matches") is False
    # Should identify hasColor as the failing pattern
    assert any("hasColor" in h for h in result.hints)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/linked-past/tests/test_core_validate.py::test_probe_join_decomposition -v`
Expected: FAIL (no join-specific hint)

- [ ] **Step 3: Implement join decomposition**

Add to `_run_probes`, in the `else` branch after `base_pattern_matches is False`. Uses `_collect_bgp_triples` and `_build_ask_from_triples` (defined in Task 7) instead of manual string formatting:

```python
            else:
                # Probe 3: Join decomposition — check individual triple patterns
                try:
                    parsed = parseQuery(sparql)
                    q = translateQuery(parsed)
                    triples = _collect_bgp_triples(q.algebra)
                except Exception:
                    triples = []

                prefix_decls = []
                for match in re.finditer(r"PREFIX\s+\w+:\s*<[^>]+>", sparql, re.IGNORECASE):
                    prefix_decls.append(match.group(0))
                prefix_str = "\n".join(prefix_decls)

                for i, triple in enumerate(triples):
                    if budget_remaining() <= 0:
                        break
                    single_ask = _build_ask_from_triples([triple], prefix_str)
                    s, p, o = triple
                    # Build display strings for the hint
                    s_str = f"?{s}" if isinstance(s, Variable) else f"<{s}>"
                    p_str = f"?{p}" if isinstance(p, Variable) else f"<{p}>"
                    o_str = f"?{o}" if isinstance(o, Variable) else (
                        f"<{o}>" if isinstance(o, URIRef) else f'"{o}"'
                    )
                    try:
                        matches = execute_ask(store, single_ask)
                        probe_results[f"triple_{i}_matches"] = matches
                        if not matches:
                            hints.append(
                                f"Diagnostic: The pattern `{s_str} {p_str} {o_str}` has no "
                                f"matches in the store. This is where the join breaks."
                            )
                    except Exception as e:
                        logger.debug("Join decomposition probe %d failed: %s", i, e)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/linked-past/tests/test_core_validate.py::test_probe_join_decomposition -v`
Expected: PASS

- [ ] **Step 5: Run all validate tests**

Run: `uv run pytest packages/linked-past/tests/test_core_validate.py -v`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add packages/linked-past/linked_past/core/validate.py packages/linked-past/tests/test_core_validate.py
git commit -m "feat: join decomposition probe for empty results"
```

---

### Task 10: Wire into validate_and_execute and server.py

**Files:**
- Modify: `packages/linked-past/linked_past/core/validate.py:499-524` (`validate_and_execute`)
- Modify: `packages/linked-past/linked_past/core/server.py:635` (pass `dataset`)
- Test: `packages/linked-past/tests/test_core_validate.py`

- [ ] **Step 1: Write failing test**

```python
def test_validate_and_execute_empty_result_diagnostics(tmp_path):
    """validate_and_execute should include diagnostics when result is empty."""
    store_path = tmp_path / "store"
    store = create_store(store_path)
    ttl = tmp_path / "data.ttl"
    ttl.write_text(SAMPLE_TURTLE)
    load_rdf(store, ttl)
    sd = build_schema_dict(SCHEMAS, PREFIXES)
    result = validate_and_execute(
        "PREFIX ex: <http://example.org/>\n"
        "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n"
        'SELECT ?w WHERE { ?w a ex:Widget ; rdfs:label ?l . FILTER(?l = "Nonexistent") }',
        store, sd, PREFIXES,
    )
    assert result.success is True
    assert result.rows == []
    # Should have at least a diagnostic hint (from probes)
    assert any("Diagnostic:" in e for e in result.errors)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/linked-past/tests/test_core_validate.py::test_validate_and_execute_empty_result_diagnostics -v`
Expected: FAIL (no "Diagnostic:" in errors)

- [ ] **Step 3: Wire diagnostics into validate_and_execute**

Modify `validate_and_execute` in `validate.py`:

```python
def validate_and_execute(
    sparql: str,
    store,
    schema_dict: dict,
    prefix_map: dict[str, str],
    dataset: str | None = None,
) -> QueryResult:
    """Validate and execute a SPARQL query through all three tiers."""
    fixed_sparql, parse_errors = parse_and_fix_prefixes(sparql, prefix_map)
    if parse_errors:
        return QueryResult(success=False, sparql=fixed_sparql, errors=parse_errors)

    # Semantic hints are non-blocking — unknown classes/predicates are warnings, not errors
    semantic_hints = validate_semantics(fixed_sparql, schema_dict)

    try:
        from linked_past.core.store import execute_query

        # Compress result URIs: dataset prefixes + query-declared prefixes (query wins on conflict)
        result_prefixes = dict(prefix_map)
        for match in re.finditer(r"PREFIX\s+(\w+):\s*<([^>]+)>", fixed_sparql, re.IGNORECASE):
            result_prefixes[match.group(1)] = match.group(2)
        rows = execute_query(store, fixed_sparql, prefix_map=result_prefixes)
    except Exception as e:
        return QueryResult(success=False, sparql=fixed_sparql, errors=[f"Query execution error: {e}"])

    # Empty-result diagnostics
    if not rows:
        diagnostics = diagnose_empty_result(
            fixed_sparql, store, schema_dict, prefix_map,
            dataset=dataset,
            semantic_hints=semantic_hints,
        )
        semantic_hints.extend(diagnostics.hints)

    return QueryResult(success=True, sparql=fixed_sparql, rows=rows, errors=semantic_hints)
```

- [ ] **Step 4: Update server.py to pass dataset**

In `packages/linked-past/linked_past/core/server.py`, change line 635 from:

```python
                asyncio.to_thread(validate_and_execute, sparql, store, schema_dict, prefix_map),
```

to:

```python
                asyncio.to_thread(validate_and_execute, sparql, store, schema_dict, prefix_map, dataset),
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest packages/linked-past/tests/test_core_validate.py::test_validate_and_execute_empty_result_diagnostics -v`
Expected: PASS

- [ ] **Step 6: Run full test suite**

Run: `uv run pytest packages/linked-past/tests/test_core_validate.py packages/linked-past/tests/test_core_store.py -v`
Expected: All pass

- [ ] **Step 7: Commit**

```bash
git add packages/linked-past/linked_past/core/validate.py packages/linked-past/linked_past/core/server.py packages/linked-past/tests/test_core_validate.py
git commit -m "feat: wire empty-result diagnostics into validate_and_execute"
```

---

### Task 11: Zero-result JSONL logging

**Files:**
- Modify: `packages/linked-past/linked_past/core/validate.py`
- Test: `packages/linked-past/tests/test_core_validate.py`

- [ ] **Step 1: Write failing test**

```python
import json


def test_log_zero_result_writes_jsonl(tmp_path, monkeypatch):
    """log_zero_result should append a JSON line to the diagnostics file."""
    monkeypatch.setenv("LINKED_PAST_DATA_DIR", str(tmp_path))
    from linked_past.core.validate import log_zero_result
    log_zero_result(
        dataset="dprr",
        sparql="SELECT ?x WHERE { ?x a <http://example.org/Nothing> }",
        diagnostics=DiagnosticResult(
            hints=["Diagnostic: no matches"],
            probe_results={"base_pattern_matches": False},
        ),
        semantic_hints=["Hint: unknown class"],
        duration_ms=42,
    )
    log_file = tmp_path / "diagnostics" / "zero_results.jsonl"
    assert log_file.exists()
    lines = log_file.read_text().strip().split("\n")
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["dataset"] == "dprr"
    assert entry["duration_ms"] == 42
    assert "timestamp" in entry
    assert entry["diagnostics"] == ["Diagnostic: no matches"]
    assert entry["probe_results"] == {"base_pattern_matches": False}


def test_log_zero_result_appends(tmp_path, monkeypatch):
    """Multiple calls should append, not overwrite."""
    monkeypatch.setenv("LINKED_PAST_DATA_DIR", str(tmp_path))
    from linked_past.core.validate import log_zero_result
    diag = DiagnosticResult(hints=[], probe_results={})
    log_zero_result("dprr", "SELECT 1", diag, [], 10)
    log_zero_result("dprr", "SELECT 2", diag, [], 20)
    log_file = tmp_path / "diagnostics" / "zero_results.jsonl"
    lines = log_file.read_text().strip().split("\n")
    assert len(lines) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/linked-past/tests/test_core_validate.py::test_log_zero_result_writes_jsonl packages/linked-past/tests/test_core_validate.py::test_log_zero_result_appends -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement log_zero_result**

Add to `validate.py`:

```python
import json
from datetime import datetime, timezone


def log_zero_result(
    dataset: str | None,
    sparql: str,
    diagnostics: DiagnosticResult,
    semantic_hints: list[str],
    duration_ms: int,
) -> None:
    """Append a zero-result query entry to the diagnostics JSONL log.

    Fire-and-forget: logs a warning on failure, never raises.
    """
    try:
        from linked_past.core.store import get_data_dir

        log_dir = get_data_dir() / "diagnostics"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "zero_results.jsonl"

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "dataset": dataset,
            "sparql": sparql,
            "diagnostics": diagnostics.hints,
            "probe_results": diagnostics.probe_results,
            "semantic_hints": semantic_hints,
            "duration_ms": duration_ms,
        }

        with open(log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        logger.warning("Failed to log zero-result query: %s", e)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/linked-past/tests/test_core_validate.py::test_log_zero_result_writes_jsonl packages/linked-past/tests/test_core_validate.py::test_log_zero_result_appends -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/linked-past/linked_past/core/validate.py packages/linked-past/tests/test_core_validate.py
git commit -m "feat: JSONL logging for zero-result queries"
```

---

### Task 12: Wire JSONL logging into validate_and_execute

**Files:**
- Modify: `packages/linked-past/linked_past/core/validate.py` (`validate_and_execute`)
- Test: `packages/linked-past/tests/test_core_validate.py`

- [ ] **Step 1: Write failing test**

```python
def test_validate_and_execute_logs_zero_result(tmp_path, monkeypatch):
    """validate_and_execute should log to JSONL when result is empty."""
    data_dir = tmp_path / "data"
    monkeypatch.setenv("LINKED_PAST_DATA_DIR", str(data_dir))
    store_path = tmp_path / "store"
    store = create_store(store_path)
    ttl = tmp_path / "data.ttl"
    ttl.write_text(SAMPLE_TURTLE)
    load_rdf(store, ttl)
    sd = build_schema_dict(SCHEMAS, PREFIXES)
    result = validate_and_execute(
        "PREFIX ex: <http://example.org/>\nSELECT ?w WHERE { ?w a ex:Gadget }",
        store, sd, PREFIXES, dataset="test",
    )
    assert result.rows == []
    log_file = data_dir / "diagnostics" / "zero_results.jsonl"
    assert log_file.exists()
    entry = json.loads(log_file.read_text().strip())
    assert entry["dataset"] == "test"


def test_validate_and_execute_no_log_when_results(tmp_path, monkeypatch):
    """validate_and_execute should NOT log when results are returned."""
    data_dir = tmp_path / "data"
    monkeypatch.setenv("LINKED_PAST_DATA_DIR", str(data_dir))
    store_path = tmp_path / "store"
    store = create_store(store_path)
    ttl = tmp_path / "data.ttl"
    ttl.write_text(SAMPLE_TURTLE)
    load_rdf(store, ttl)
    sd = build_schema_dict(SCHEMAS, PREFIXES)
    result = validate_and_execute(
        "PREFIX ex: <http://example.org/>\nSELECT ?w WHERE { ?w a ex:Widget }",
        store, sd, PREFIXES,
    )
    assert len(result.rows) > 0
    log_file = data_dir / "diagnostics" / "zero_results.jsonl"
    assert not log_file.exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/linked-past/tests/test_core_validate.py::test_validate_and_execute_logs_zero_result packages/linked-past/tests/test_core_validate.py::test_validate_and_execute_no_log_when_results -v`
Expected: FAIL (no log file created)

- [ ] **Step 3: Add logging call to validate_and_execute**

In `validate_and_execute`, add the logging call inside the `if not rows:` block, after `semantic_hints.extend(diagnostics.hints)`:

Also add `import time` at the top of validate.py (if not already present from Task 7) and add timing at the start of `validate_and_execute`:

```python
def validate_and_execute(
    sparql: str,
    store,
    schema_dict: dict,
    prefix_map: dict[str, str],
    dataset: str | None = None,
) -> QueryResult:
    """Validate and execute a SPARQL query through all three tiers."""
    t0 = time.monotonic()
    fixed_sparql, parse_errors = parse_and_fix_prefixes(sparql, prefix_map)
    # ... (existing code unchanged) ...

    # Empty-result diagnostics
    if not rows:
        diagnostics = diagnose_empty_result(
            fixed_sparql, store, schema_dict, prefix_map,
            dataset=dataset,
            semantic_hints=semantic_hints,
        )
        semantic_hints.extend(diagnostics.hints)
        log_zero_result(
            dataset=dataset,
            sparql=fixed_sparql,
            diagnostics=diagnostics,
            semantic_hints=semantic_hints,
            duration_ms=int((time.monotonic() - t0) * 1000),
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/linked-past/tests/test_core_validate.py::test_validate_and_execute_logs_zero_result packages/linked-past/tests/test_core_validate.py::test_validate_and_execute_no_log_when_results -v`
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `uv run pytest packages/linked-past/tests/ -v`
Expected: All pass (existing tests should not be affected — the only changed signature is `validate_and_execute` which gets a new optional `dataset` parameter)

- [ ] **Step 6: Commit**

```bash
git add packages/linked-past/linked_past/core/validate.py packages/linked-past/tests/test_core_validate.py
git commit -m "feat: wire JSONL logging into validate_and_execute for zero-result queries"
```

---

### Task 13: Heuristic — string literal vs URI mismatch

**Files:**
- Modify: `packages/linked-past/linked_past/core/validate.py` (`_run_heuristics`)
- Test: `packages/linked-past/tests/test_core_validate.py`

- [ ] **Step 1: Write failing test**

```python
def test_heuristic_string_vs_uri_mismatch():
    """Detect FILTER comparing a URI-range variable to a string literal."""
    schemas = {
        "PostAssertion": {
            "uri": "ex:PostAssertion",
            "properties": [
                {"pred": "ex:hasOffice", "range": "ex:Office"},
            ],
        },
    }
    sd = build_schema_dict(schemas, PREFIXES)
    sparql = (
        "PREFIX ex: <http://example.org/>\n"
        'SELECT ?pa WHERE { ?pa a ex:PostAssertion ; ex:hasOffice ?o . FILTER(?o = "consul") }'
    )
    result = diagnose_empty_result(sparql, None, sd, PREFIXES)
    assert any("uri" in h.lower() and "string" in h.lower() for h in result.hints)


def test_heuristic_no_mismatch_string_range():
    """No warning when comparing string-range variable to string literal."""
    schemas = {
        "Person": {
            "uri": "ex:Person",
            "properties": [
                {"pred": "ex:hasName", "range": "xsd:string"},
            ],
        },
    }
    sd = build_schema_dict(schemas, PREFIXES)
    sparql = (
        "PREFIX ex: <http://example.org/>\n"
        'SELECT ?p WHERE { ?p a ex:Person ; ex:hasName ?n . FILTER(?n = "Cicero") }'
    )
    result = diagnose_empty_result(sparql, None, sd, PREFIXES)
    assert not any("uri" in h.lower() and "string" in h.lower() for h in result.hints)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/linked-past/tests/test_core_validate.py::test_heuristic_string_vs_uri_mismatch packages/linked-past/tests/test_core_validate.py::test_heuristic_no_mismatch_string_range -v`
Expected: FAIL

- [ ] **Step 3: Implement string vs URI mismatch detection**

Add to `_run_heuristics` after the gYear check:

```python
    # 5. String literal vs URI mismatch in FILTER
    # Build map of variable -> predicate range types
    var_range_types: dict[str, list[str]] = {}
    for s, p, o in triples:
        if isinstance(p, URIRef) and isinstance(o, Variable) and isinstance(s, Variable):
            pred_uri = str(p)
            s_name = str(s)
            # Find types of s, then look up range of predicate
            for class_uri in var_types.get(s_name, []):
                if class_uri not in schema_dict:
                    continue
                pred_info = schema_dict[class_uri].get(pred_uri)
                if isinstance(pred_info, dict):
                    for range_uri in pred_info.get("ranges", []):
                        var_range_types.setdefault(str(o), []).append(range_uri)

    # Look for FILTER(?var = "string") where var has a URI range
    string_filter = re.compile(
        r"""FILTER\s*\(.*?\?(\w+)\s*=\s*"([^"]*)"(?:\^\^[^ )]*)?""",
        re.IGNORECASE,
    )
    for match in string_filter.finditer(sparql):
        var_name = match.group(1)
        ranges = var_range_types.get(var_name, [])
        for range_uri in ranges:
            # If range is not an XSD type, it's a URI range (another class)
            if not range_uri.startswith(_XSD_NS):
                range_local = _local_name(range_uri)
                hints.append(
                    f"Diagnostic: ?{var_name} has range {range_local} (a URI/entity), "
                    f"but you're comparing it to a string literal. Use the entity URI "
                    f"or match via rdfs:label on the linked entity."
                )
                break
```

Note: `triples`, `var_types`, and `var_preds` are all computed once at the top of `_run_heuristics` (from Task 3) and shared by all heuristic checks.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/linked-past/tests/test_core_validate.py::test_heuristic_string_vs_uri_mismatch packages/linked-past/tests/test_core_validate.py::test_heuristic_no_mismatch_string_range -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/linked-past/linked_past/core/validate.py packages/linked-past/tests/test_core_validate.py
git commit -m "feat: heuristic for string literal vs URI range mismatch"
```

---

### Task 14: Full integration test and lint

**Files:**
- Test: `packages/linked-past/tests/test_core_validate.py`
- Test: `packages/linked-past/tests/test_core_store.py`

- [ ] **Step 1: Run all validate and store tests**

Run: `uv run pytest packages/linked-past/tests/test_core_validate.py packages/linked-past/tests/test_core_store.py -v`
Expected: All pass

- [ ] **Step 2: Run full test suite**

Run: `uv run pytest`
Expected: All pass (no regressions)

- [ ] **Step 3: Run linter**

Run: `uv run ruff check .`
Expected: No errors

- [ ] **Step 4: Fix any issues found**

If ruff reports issues, fix them (typically: unused imports, line length, etc.)

- [ ] **Step 5: Final commit**

```bash
git add packages/linked-past/linked_past/core/validate.py packages/linked-past/linked_past/core/store.py packages/linked-past/linked_past/core/server.py packages/linked-past/tests/test_core_validate.py packages/linked-past/tests/test_core_store.py
git commit -m "chore: lint fixes for empty-result diagnostics"
```
