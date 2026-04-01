# Enhanced SPARQL Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add type inference, literal checking, and domain-specific hints to the SPARQL validator so LLMs write correct queries on the first try.

**Architecture:** Enhance `build_schema_dict` to carry rich per-property metadata (ranges, datatype, open_world, count_distinct). Extend `validate_semantics` with recursive variable-chain type inference and pattern-based checks. Add annotations to schemas.yaml. Pass VoID class counts for LIMIT warnings.

**Tech Stack:** Python, rdflib SPARQL algebra (already used), schemas.yaml annotations.

---

## File Structure

| File | Responsibility |
|------|----------------|
| `packages/linked-past/linked_past/core/validate.py` | Enhanced `build_schema_dict`, recursive `validate_semantics`, pattern checks |
| `packages/linked-past/tests/test_core_validate.py` | Tests for all new checks |
| `packages/linked-past/linked_past/datasets/dprr/context/schemas.yaml` | Add `open_world`, `count_distinct` annotations |
| `packages/linked-past/linked_past/datasets/*/context/schemas.yaml` | Same annotations for other datasets |

---

### Task 1: Enhance `build_schema_dict` with Rich Metadata

**Files:**
- Modify: `packages/linked-past/linked_past/core/validate.py:123-136`
- Modify: `packages/linked-past/tests/test_core_validate.py`

- [ ] **Step 1: Write test for enhanced schema dict**

Add to `packages/linked-past/tests/test_core_validate.py`:

```python
def test_build_schema_dict_rich_metadata():
    schemas = {
        "PostAssertion": {
            "uri": "ex:PostAssertion",
            "count_distinct": True,
            "properties": [
                {"pred": "ex:hasDateStart", "range": "xsd:integer"},
                {"pred": "ex:isUncertain", "range": "xsd:boolean", "open_world": True},
                {"pred": "ex:hasOffice", "range": "ex:Office"},
            ],
        },
    }
    sd = build_schema_dict(schemas, PREFIXES)
    pa = sd["http://example.org/PostAssertion"]

    # Keys still work for membership checks (backwards compatible)
    assert "http://example.org/hasDateStart" in pa
    assert "http://example.org/isUncertain" in pa

    # Rich metadata available
    date_info = pa["http://example.org/hasDateStart"]
    assert date_info["ranges"] == ["http://www.w3.org/2001/XMLSchema#integer"]
    assert date_info["datatype"] == "http://www.w3.org/2001/XMLSchema#integer"
    assert date_info.get("open_world") is not True

    uncertain_info = pa["http://example.org/isUncertain"]
    assert uncertain_info["open_world"] is True
    assert uncertain_info["datatype"] == "http://www.w3.org/2001/XMLSchema#boolean"

    office_info = pa["http://example.org/hasOffice"]
    assert office_info["ranges"] == ["http://example.org/Office"]
    assert office_info.get("datatype") is None  # not an xsd type

    # Class-level metadata
    assert pa["_meta"]["count_distinct"] is True
```

- [ ] **Step 2: Implement enhanced `build_schema_dict`**

Replace `build_schema_dict` in `packages/linked-past/linked_past/core/validate.py`:

```python
_XSD_NS = "http://www.w3.org/2001/XMLSchema#"


def build_schema_dict(schemas: dict, prefix_map: dict[str, str]) -> dict:
    """Convert schemas YAML to dict[class_uri][pred_uri] = {ranges, datatype, open_world, ...}.

    Backwards-compatible: callers that check `pred_uri in schema_dict[class]`
    still work because dict keys are predicate URIs.
    """
    schema_dict: dict[str, dict] = {}
    for cls_name, cls_data in schemas.items():
        class_uri = _expand_uri(cls_data["uri"], prefix_map)
        predicates: dict[str, dict] = {}
        for prop in cls_data.get("properties", []):
            pred_uri = _expand_uri(prop["pred"], prefix_map)
            range_uri = _expand_uri(prop.get("range", ""), prefix_map)
            ranges = predicates.get(pred_uri, {}).get("ranges", [])
            if range_uri:
                ranges.append(range_uri)
            pred_info: dict = {
                "ranges": ranges,
                "datatype": range_uri if range_uri.startswith(_XSD_NS) else None,
                "open_world": prop.get("open_world", False),
                "comment": prop.get("comment", ""),
            }
            predicates[pred_uri] = pred_info
        predicates["_meta"] = {
            "count_distinct": cls_data.get("count_distinct", False),
        }
        schema_dict[class_uri] = predicates
    return schema_dict
```

- [ ] **Step 3: Run tests**

Run: `uv run pytest packages/linked-past/tests/test_core_validate.py -v`
Expected: All pass (existing tests still work because they only check key membership)

- [ ] **Step 4: Lint and commit**

```bash
uv run ruff check packages/linked-past/linked_past/core/validate.py packages/linked-past/tests/test_core_validate.py
git add packages/linked-past/linked_past/core/validate.py packages/linked-past/tests/test_core_validate.py
git commit -m "feat: build_schema_dict returns rich per-property metadata (backwards-compatible)"
```

---

### Task 2: Add Annotations to DPRR schemas.yaml

**Files:**
- Modify: `packages/linked-past/linked_past/datasets/dprr/context/schemas.yaml`

- [ ] **Step 1: Add `count_distinct` and `open_world` annotations**

In DPRR's `schemas.yaml`, add `count_distinct: true` to classes where multiple rows per entity exist:

```yaml
  PostAssertion:
    label: "Post Assertion"
    comment: "..."
    uri: "vocab:PostAssertion"
    count_distinct: true
    properties:
      ...
```

Add `count_distinct: true` to: `PostAssertion`, `RelationshipAssertion`, `StatusAssertion`, `DateInformation`, `TribeAssertion`.

Add `open_world: true` to all boolean properties that only store `true`. These are on `Person`:

```yaml
      - pred: "vocab:isPatrician"
        range: "xsd:boolean"
        comment: "Only `true` values are stored."
        open_world: true
      - pred: "vocab:isNobilis"
        range: "xsd:boolean"
        comment: "Only `true` values are stored."
        open_world: true
      - pred: "vocab:isNovus"
        range: "xsd:boolean"
        comment: "Only `true` values are stored."
        open_world: true
```

And all `isUncertain`, `isPraenomenUncertain`, `isNomenUncertain`, `isCognomenUncertain`, `isFiliationUncertain`, `isOtherNamesUncertain`, `isPatricianUncertain` on Person.

And `isUncertain`, `isDateStartUncertain`, `isDateEndUncertain` on PostAssertion, StatusAssertion, TribeAssertion.

And `isUncertain` on DateInformation.

And `isProvinceUncertain` on PostAssertionProvince.

- [ ] **Step 2: Commit**

```bash
git add packages/linked-past/linked_past/datasets/dprr/context/schemas.yaml
git commit -m "feat: annotate DPRR schemas with count_distinct and open_world flags"
```

---

### Task 3: Recursive Variable-Chain Type Inference

**Files:**
- Modify: `packages/linked-past/linked_past/core/validate.py`
- Modify: `packages/linked-past/tests/test_core_validate.py`

- [ ] **Step 1: Write tests for type inference**

Add to `packages/linked-past/tests/test_core_validate.py`:

```python
def test_validate_infers_type_from_range():
    """If ?x hasOffice ?y and hasOffice range is Office, ?y is inferred as Office."""
    schemas = {
        "PostAssertion": {
            "uri": "ex:PostAssertion",
            "properties": [
                {"pred": "ex:hasOffice", "range": "ex:Office"},
                {"pred": "ex:isAboutPerson", "range": "ex:Person"},
            ],
        },
        "Office": {
            "uri": "ex:Office",
            "properties": [
                {"pred": "rdfs:label", "range": "xsd:string"},
                {"pred": "ex:hasAbbreviation", "range": "xsd:string"},
            ],
        },
        "Person": {
            "uri": "ex:Person",
            "properties": [
                {"pred": "ex:hasName", "range": "xsd:string"},
            ],
        },
    }
    sd = build_schema_dict(schemas, PREFIXES)

    # This should NOT produce a hint — hasAbbreviation is valid on Office,
    # and ?office is inferred as Office via hasOffice range
    sparql = (
        "PREFIX ex: <http://example.org/>\n"
        "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n"
        "SELECT ?name WHERE {\n"
        "  ?pa a ex:PostAssertion ; ex:hasOffice ?office .\n"
        "  ?office ex:hasAbbreviation ?abbr .\n"
        "}"
    )
    hints = validate_semantics(sparql, sd)
    assert not any("hasAbbreviation" in h for h in hints)


def test_validate_wrong_predicate_on_inferred_type():
    """Predicate invalid for the inferred type should produce a hint."""
    schemas = {
        "PostAssertion": {
            "uri": "ex:PostAssertion",
            "properties": [
                {"pred": "ex:hasOffice", "range": "ex:Office"},
            ],
        },
        "Office": {
            "uri": "ex:Office",
            "properties": [
                {"pred": "rdfs:label", "range": "xsd:string"},
            ],
        },
    }
    sd = build_schema_dict(schemas, PREFIXES)

    # hasName is NOT valid on Office
    sparql = (
        "PREFIX ex: <http://example.org/>\n"
        "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n"
        "SELECT ?name WHERE {\n"
        "  ?pa a ex:PostAssertion ; ex:hasOffice ?office .\n"
        "  ?office ex:hasName ?name .\n"
        "}"
    )
    hints = validate_semantics(sparql, sd)
    assert any("hasName" in h for h in hints)


def test_validate_predicate_on_wrong_class():
    """hasOffice on Person (instead of PostAssertion) should hint."""
    schemas = {
        "Person": {
            "uri": "ex:Person",
            "properties": [
                {"pred": "ex:hasName", "range": "xsd:string"},
            ],
        },
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
        "SELECT ?o WHERE { ?p a ex:Person ; ex:hasOffice ?o }"
    )
    hints = validate_semantics(sparql, sd)
    assert any("hasOffice" in h and "Person" in h for h in hints)
```

- [ ] **Step 2: Implement recursive type inference**

Replace `validate_semantics` in `packages/linked-past/linked_past/core/validate.py`:

```python
def validate_semantics(
    sparql: str,
    schema_dict: dict,
    class_counts: dict[str, int] | None = None,
) -> list[str]:
    """Validate a SPARQL query against the schema dictionary.

    Returns constructive hints. Performs:
    1. Unknown class/predicate detection (with suggestions)
    2. Recursive type inference through property ranges
    3. Literal datatype checking
    4. Domain-specific pattern checks (LIMIT, COUNT(DISTINCT), open-world booleans)
    """
    hints = []
    try:
        triples = _collect_triples(sparql)
    except Exception:
        return hints

    all_class_uris = set(k for k in schema_dict.keys() if k != "_meta")
    var_types: dict[str, list[str]] = {}

    # Pass 1: Explicit types from rdf:type
    for s, p, o in triples:
        if p == RDF_TYPE and isinstance(o, URIRef):
            class_uri = str(o)
            if class_uri not in all_class_uris:
                local_name = _local_name(class_uri)
                valid_classes = sorted(_local_name(uri) for uri in all_class_uris)
                suggestion = _suggest(local_name, valid_classes)
                hints.append(
                    f"Hint: Class '{local_name}' not in this dataset's schema. "
                    f"Available classes: {', '.join(valid_classes[:15])}.{suggestion}"
                )
            if isinstance(s, Variable):
                var_types.setdefault(str(s), []).append(class_uri)

    # Pass 2: Infer types from property ranges
    max_infer_rounds = 10
    for _ in range(max_infer_rounds):
        new_inferences = False
        for s, p, o in triples:
            if p == RDF_TYPE or not isinstance(p, URIRef) or not isinstance(o, Variable):
                continue
            if not isinstance(s, Variable):
                continue
            pred_uri = str(p)
            if pred_uri in _UNIVERSAL_PREDS:
                continue
            s_name = str(s)
            o_name = str(o)
            # Don't skip entirely — variable may have multiple types from different predicates
            for class_uri in var_types.get(s_name, []):
                if class_uri not in schema_dict:
                    continue
                pred_info = schema_dict[class_uri].get(pred_uri)
                if pred_info is None or pred_info == schema_dict[class_uri].get("_meta"):
                    continue
                ranges = pred_info.get("ranges", []) if isinstance(pred_info, dict) else pred_info
                for range_uri in ranges:
                    if range_uri in all_class_uris and range_uri not in var_types.get(o_name, []):
                        var_types.setdefault(o_name, []).append(range_uri)
                        new_inferences = True
        if not new_inferences:
            break

    # Pass 3: Validate predicates against typed variables
    for s, p, o in triples:
        if p == RDF_TYPE or not isinstance(p, URIRef) or not isinstance(s, Variable):
            continue
        var_name = str(s)
        if var_name not in var_types:
            continue
        pred_uri = str(p)
        if pred_uri in _UNIVERSAL_PREDS:
            continue
        for class_uri in var_types[var_name]:
            if class_uri not in schema_dict:
                continue
            valid_preds = {k: v for k, v in schema_dict[class_uri].items() if k != "_meta"}
            if pred_uri not in valid_preds:
                pred_local = _local_name(pred_uri)
                class_local = _local_name(class_uri)
                valid_local = sorted(_local_name(uri) for uri in valid_preds)
                suggestion = _suggest(pred_local, valid_local)
                # Check if this predicate belongs to another class (join hint)
                owner_classes = []
                for other_class, other_preds in schema_dict.items():
                    if pred_uri in other_preds and other_class != class_uri:
                        owner_classes.append(_local_name(other_class))
                join_hint = ""
                if owner_classes:
                    join_hint = f" This predicate belongs to: {', '.join(owner_classes)}."
                hints.append(
                    f"Hint: '{pred_local}' not a known predicate for {class_local}. "
                    f"Available: {', '.join(valid_local[:15])}.{suggestion}{join_hint}"
                )

    # Pass 4: Literal datatype checking in triple patterns
    hints.extend(_check_literal_datatypes(triples, var_types, schema_dict))

    # Pass 5: Domain-specific checks
    hints.extend(_check_open_world_booleans(sparql, triples, var_types, schema_dict))
    hints.extend(_check_count_distinct(sparql, var_types, schema_dict))
    hints.extend(_check_limit(sparql, var_types, schema_dict, class_counts))
    hints.extend(_check_uncertainty_flags(triples, var_types, schema_dict))

    return hints
```

- [ ] **Step 3: Implement literal datatype and domain-specific check helpers**

Add to `packages/linked-past/linked_past/core/validate.py`:

```python
from rdflib.term import Literal


def _check_literal_datatypes(
    triples: list[tuple],
    var_types: dict[str, list[str]],
    schema_dict: dict,
) -> list[str]:
    """Detect literal type mismatches in triple patterns."""
    hints = []
    for s, p, o in triples:
        if not isinstance(p, URIRef) or not isinstance(s, Variable):
            continue
        if not isinstance(o, Literal):
            continue
        pred_uri = str(p)
        s_name = str(s)
        for class_uri in var_types.get(s_name, []):
            if class_uri not in schema_dict:
                continue
            pred_info = schema_dict[class_uri].get(pred_uri)
            if not isinstance(pred_info, dict):
                continue
            expected_dt = pred_info.get("datatype")
            if not expected_dt:
                continue
            actual_dt = str(o.datatype) if o.datatype else None
            if actual_dt and actual_dt != expected_dt:
                pred_local = _local_name(pred_uri)
                expected_local = _local_name(expected_dt)
                actual_local = _local_name(actual_dt) if actual_dt else "untyped"
                hints.append(
                    f"Hint: '{pred_local}' expects {expected_local} but got {actual_local}. "
                    f"Example: use -63 (integer) instead of \"63 BC\" (string)."
                )
            elif not actual_dt and expected_dt.endswith("integer"):
                # Untyped literal where integer is expected (e.g., "63 BC" without ^^xsd:string)
                try:
                    int(str(o))
                except ValueError:
                    pred_local = _local_name(pred_uri)
                    hints.append(
                        f"Hint: '{pred_local}' expects xsd:integer but got string \"{o}\". "
                        f"Use an integer value (negative for BC, e.g., -63)."
                    )
    return hints


```

Also add:

```python
def _check_open_world_booleans(
    sparql: str,
    triples: list[tuple],
    var_types: dict[str, list[str]],
    schema_dict: dict,
) -> list[str]:
    """Detect FILTER(?var = false) on open-world boolean properties."""
    hints = []
    # Look for patterns like "= false" or '= "false"' in FILTER
    false_pattern = re.compile(
        r"FILTER\s*\(\s*\?(\w+)\s*=\s*(?:false|\"false\")", re.IGNORECASE
    )
    for match in false_pattern.finditer(sparql):
        var_name = match.group(1)
        # Find which predicates bind this variable
        for s, p, o in triples:
            if isinstance(o, Variable) and str(o) == var_name and isinstance(s, Variable) and isinstance(p, URIRef):
                pred_uri = str(p)
                s_name = str(s)
                for class_uri in var_types.get(s_name, []):
                    if class_uri not in schema_dict:
                        continue
                    pred_info = schema_dict[class_uri].get(pred_uri)
                    if isinstance(pred_info, dict) and pred_info.get("open_world"):
                        pred_local = _local_name(pred_uri)
                        hints.append(
                            f"Hint: '{pred_local}' only stores true values (open-world boolean). "
                            f"FILTER(?{var_name} = false) returns 0 rows. "
                            f"Use: FILTER NOT EXISTS {{ ?{s_name} <{pred_uri}> true }}"
                        )
    return hints


def _check_count_distinct(
    sparql: str,
    var_types: dict[str, list[str]],
    schema_dict: dict,
) -> list[str]:
    """Detect COUNT(?var) without DISTINCT on classes marked count_distinct."""
    hints = []
    # Match COUNT(?var) but not COUNT(DISTINCT ?var)
    count_pattern = re.compile(r"COUNT\s*\(\s*(?!DISTINCT\b)\?(\w+)\s*\)", re.IGNORECASE)
    for match in count_pattern.finditer(sparql):
        var_name = match.group(1)
        for class_uri in var_types.get(var_name, []):
            if class_uri not in schema_dict:
                continue
            meta = schema_dict[class_uri].get("_meta", {})
            if meta.get("count_distinct"):
                class_local = _local_name(class_uri)
                hints.append(
                    f"Hint: {class_local} can have multiple rows per entity (e.g. one per source). "
                    f"Use COUNT(DISTINCT ?{var_name}) instead of COUNT(?{var_name})."
                )
    return hints


def _check_limit(
    sparql: str,
    var_types: dict[str, list[str]],
    schema_dict: dict,
    class_counts: dict[str, int] | None,
) -> list[str]:
    """Warn when SELECT has no LIMIT and target class has many instances."""
    hints = []
    if class_counts is None:
        return hints
    sparql_upper = sparql.upper()
    if "LIMIT" in sparql_upper or "COUNT" in sparql_upper or "ASK" in sparql_upper:
        return hints  # has LIMIT, is aggregate, or is ASK — no warning
    # Find the largest class in the query
    max_count = 0
    max_class = ""
    for var_name, types in var_types.items():
        for class_uri in types:
            count = class_counts.get(class_uri, 0)
            if count > max_count:
                max_count = count
                max_class = _local_name(class_uri)
    if max_count > 1000:
        hints.append(
            f"Hint: Query targets {max_class} (~{max_count:,} instances) with no LIMIT. "
            f"Consider adding LIMIT 100 for exploration, or use COUNT/GROUP BY for aggregation."
        )
    return hints


def _check_uncertainty_flags(
    triples: list[tuple],
    var_types: dict[str, list[str]],
    schema_dict: dict,
) -> list[str]:
    """Suggest surfacing uncertainty flags when querying assertion classes."""
    hints = []
    # Collect which open_world predicates are already referenced in the query
    used_preds: set[str] = set()
    for s, p, o in triples:
        if isinstance(p, URIRef):
            used_preds.add(str(p))

    # For each typed variable, check if its class has open_world flags not in the query
    seen_classes: set[str] = set()
    for var_name, types in var_types.items():
        for class_uri in types:
            if class_uri in seen_classes or class_uri not in schema_dict:
                continue
            seen_classes.add(class_uri)
            flags = []
            for pred_uri, pred_info in schema_dict[class_uri].items():
                if pred_uri == "_meta":
                    continue
                if isinstance(pred_info, dict) and pred_info.get("open_world") and pred_uri not in used_preds:
                    flags.append(_local_name(pred_uri))
            if flags:
                class_local = _local_name(class_uri)
                hints.append(
                    f"Hint: {class_local} has uncertainty flags not in your query: "
                    f"{', '.join(flags)}. Consider OPTIONAL {{ ?{var_name} ... }} to surface them, "
                    f"or FILTER NOT EXISTS {{ ... true }} to exclude uncertain data."
                )
    return hints
```

- [ ] **Step 4: Write tests for literal datatype and domain-specific checks**

Add to `packages/linked-past/tests/test_core_validate.py`:

```python
def test_literal_datatype_mismatch():
    schemas = {
        "PostAssertion": {
            "uri": "ex:PostAssertion",
            "properties": [
                {"pred": "ex:hasDateStart", "range": "xsd:integer"},
            ],
        },
    }
    sd = build_schema_dict(schemas, PREFIXES)
    # String literal where integer is expected
    sparql = (
        "PREFIX ex: <http://example.org/>\n"
        'SELECT ?pa WHERE { ?pa a ex:PostAssertion ; ex:hasDateStart "63 BC" }'
    )
    hints = validate_semantics(sparql, sd)
    assert any("integer" in h.lower() for h in hints)


def test_literal_datatype_correct():
    schemas = {
        "PostAssertion": {
            "uri": "ex:PostAssertion",
            "properties": [
                {"pred": "ex:hasDateStart", "range": "xsd:integer"},
            ],
        },
    }
    sd = build_schema_dict(schemas, PREFIXES)
    # Integer literal — correct
    sparql = (
        "PREFIX ex: <http://example.org/>\n"
        "SELECT ?pa WHERE { ?pa a ex:PostAssertion ; ex:hasDateStart -63 }"
    )
    hints = validate_semantics(sparql, sd)
    assert not any("integer" in h.lower() for h in hints)


def test_open_world_boolean_hint():
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
    hints = validate_semantics(sparql, sd)
    assert any("open-world" in h and "FILTER NOT EXISTS" in h for h in hints)


def test_open_world_no_false_positive():
    schemas = {
        "Person": {
            "uri": "ex:Person",
            "properties": [
                {"pred": "ex:isPatrician", "range": "xsd:boolean", "open_world": True},
            ],
        },
    }
    sd = build_schema_dict(schemas, PREFIXES)
    # Filtering = true is fine
    sparql = (
        "PREFIX ex: <http://example.org/>\n"
        "SELECT ?p WHERE { ?p a ex:Person ; ex:isPatrician true }"
    )
    hints = validate_semantics(sparql, sd)
    assert not any("open-world" in h for h in hints)


def test_count_distinct_hint():
    schemas = {
        "PostAssertion": {
            "uri": "ex:PostAssertion",
            "count_distinct": True,
            "properties": [
                {"pred": "ex:isAboutPerson", "range": "ex:Person"},
            ],
        },
    }
    sd = build_schema_dict(schemas, PREFIXES)
    sparql = (
        "PREFIX ex: <http://example.org/>\n"
        "SELECT (COUNT(?pa) AS ?n) WHERE { ?pa a ex:PostAssertion }"
    )
    hints = validate_semantics(sparql, sd)
    assert any("COUNT(DISTINCT" in h for h in hints)


def test_count_distinct_no_false_positive():
    schemas = {
        "PostAssertion": {
            "uri": "ex:PostAssertion",
            "count_distinct": True,
            "properties": [],
        },
    }
    sd = build_schema_dict(schemas, PREFIXES)
    sparql = (
        "PREFIX ex: <http://example.org/>\n"
        "SELECT (COUNT(DISTINCT ?pa) AS ?n) WHERE { ?pa a ex:PostAssertion }"
    )
    hints = validate_semantics(sparql, sd)
    assert not any("COUNT(DISTINCT" in h for h in hints)


def test_limit_warning():
    schemas = {
        "Person": {
            "uri": "ex:Person",
            "properties": [],
        },
    }
    sd = build_schema_dict(schemas, PREFIXES)
    class_counts = {"http://example.org/Person": 5000}
    sparql = (
        "PREFIX ex: <http://example.org/>\n"
        "SELECT ?p WHERE { ?p a ex:Person }"
    )
    hints = validate_semantics(sparql, sd, class_counts=class_counts)
    assert any("LIMIT" in h and "5,000" in h for h in hints)


def test_limit_no_warning_when_present():
    schemas = {
        "Person": {
            "uri": "ex:Person",
            "properties": [],
        },
    }
    sd = build_schema_dict(schemas, PREFIXES)
    class_counts = {"http://example.org/Person": 5000}
    sparql = (
        "PREFIX ex: <http://example.org/>\n"
        "SELECT ?p WHERE { ?p a ex:Person } LIMIT 100"
    )
    hints = validate_semantics(sparql, sd, class_counts=class_counts)
    assert not any("LIMIT" in h for h in hints)


def test_uncertainty_flags_hint():
    schemas = {
        "PostAssertion": {
            "uri": "ex:PostAssertion",
            "properties": [
                {"pred": "ex:hasOffice", "range": "ex:Office"},
                {"pred": "ex:isUncertain", "range": "xsd:boolean", "open_world": True},
                {"pred": "ex:isDateUncertain", "range": "xsd:boolean", "open_world": True},
            ],
        },
    }
    sd = build_schema_dict(schemas, PREFIXES)
    # Query uses PostAssertion but does NOT reference any uncertainty flags
    sparql = (
        "PREFIX ex: <http://example.org/>\n"
        "SELECT ?pa WHERE { ?pa a ex:PostAssertion ; ex:hasOffice ?o }"
    )
    hints = validate_semantics(sparql, sd)
    assert any("uncertainty" in h.lower() and "isUncertain" in h for h in hints)


def test_uncertainty_flags_no_hint_when_used():
    schemas = {
        "PostAssertion": {
            "uri": "ex:PostAssertion",
            "properties": [
                {"pred": "ex:hasOffice", "range": "ex:Office"},
                {"pred": "ex:isUncertain", "range": "xsd:boolean", "open_world": True},
            ],
        },
    }
    sd = build_schema_dict(schemas, PREFIXES)
    # Query already references isUncertain — no hint needed
    sparql = (
        "PREFIX ex: <http://example.org/>\n"
        "SELECT ?pa WHERE { ?pa a ex:PostAssertion ; ex:hasOffice ?o . FILTER NOT EXISTS { ?pa ex:isUncertain true } }"
    )
    hints = validate_semantics(sparql, sd)
    assert not any("uncertainty" in h.lower() for h in hints)
```

- [ ] **Step 5: Run all tests**

Run: `uv run pytest packages/linked-past/tests/test_core_validate.py -v`
Expected: All pass

- [ ] **Step 6: Lint and commit**

```bash
uv run ruff check packages/linked-past/linked_past/core/validate.py packages/linked-past/tests/test_core_validate.py
git add packages/linked-past/linked_past/core/validate.py packages/linked-past/tests/test_core_validate.py
git commit -m "feat: recursive type inference, literal checks, domain-specific hints in validator"
```

---

### Task 4: Wire VoID Class Counts into Validation

**Files:**
- Modify: `packages/linked-past/linked_past/core/server.py`

- [ ] **Step 1: Pass class counts to validate_and_execute**

In `packages/linked-past/linked_past/core/server.py`, find the `validate_sparql` tool (search for `def validate_sparql`). It calls `plugin.validate(sparql)`. Each plugin's `validate` calls `validate_semantics(sparql, self._schema_dict)`.

The simplest path: pass class counts through the plugin. Add to `packages/linked-past/linked_past/datasets/base.py` after `set_auto_schema`:

```python
    def set_void_class_counts(self, class_counts: dict[str, int]) -> None:
        """Store VoID class counts for validation hints."""
        self._class_counts = class_counts
```

In each plugin's `validate` method, pass class counts:

```python
    def validate(self, sparql: str) -> ValidationResult:
        class_counts = getattr(self, "_class_counts", None)
        hints = validate_semantics(sparql, self._schema_dict, class_counts=class_counts)
        return ValidationResult(valid=True, sparql=sparql, suggestions=hints)
```

In `registry.py`'s `_load_void`, after storing VoID metadata, extract class counts and pass to plugin:

```python
            if void_meta:
                meta = self._metadata.setdefault(name, {})
                meta["void"] = void_meta
                # Pass class counts to plugin for validation
                plugin = self._plugins.get(name)
                if plugin and "classPartitions" in void_meta:
                    counts = {cp["class"]: int(cp["entities"]) for cp in void_meta["classPartitions"]}
                    plugin.set_void_class_counts(counts)
```

- [ ] **Step 2: Lint and commit**

```bash
uv run ruff check packages/linked-past/linked_past/core/server.py packages/linked-past/linked_past/datasets/base.py packages/linked-past/linked_past/core/registry.py
git add packages/linked-past/linked_past/core/server.py packages/linked-past/linked_past/datasets/base.py packages/linked-past/linked_past/core/registry.py packages/linked-past/linked_past/datasets/*/plugin.py
git commit -m "feat: pass VoID class counts to validator for LIMIT warnings"
```

---

### Task 5: Annotate Remaining Datasets

**Files:**
- Modify: `packages/linked-past/linked_past/datasets/*/context/schemas.yaml` (6 remaining)

- [ ] **Step 1: Add annotations to each dataset**

For each dataset, add `open_world: true` to boolean properties that only store true values, and `count_distinct: true` to classes with multiple rows per entity.

**EDH:** No `count_distinct` or `open_world` — EDH inscriptions are 1:1.

**Pleiades:** No annotations needed — no boolean flags, no multi-row classes.

**Nomisma/CRRO/OCRE:** Add `count_distinct: true` to classes that aggregate (if any). Most numismatic data is 1:1 per coin type. Check each schema.

**PeriodO:** No annotations needed.

For datasets where no annotations apply, no changes needed — the defaults (`count_distinct: false`, `open_world: false`) are correct.

- [ ] **Step 2: Commit**

```bash
git add packages/linked-past/linked_past/datasets/*/context/schemas.yaml
git commit -m "feat: annotate remaining dataset schemas with validation flags"
```

---

### Task 6: Full Test Suite + End-to-End

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest packages/linked-past/tests/ packages/linked-past-store/tests/ -v --tb=short`
Expected: All pass

- [ ] **Step 2: End-to-end test with MCP tools**

```python
uv run python -c "
from linked_past.core.server import build_app_context
ctx = build_app_context(skip_search=False)
plugin = ctx.registry.get_plugin('dprr')

# Test: open-world boolean
r1 = plugin.validate('PREFIX vocab: <http://romanrepublic.ac.uk/rdf/ontology#>\nSELECT ?p WHERE { ?p a vocab:Person ; vocab:isPatrician ?v . FILTER(?v = false) }')
print('Open-world:', [s for s in r1.suggestions if 'open-world' in s])

# Test: COUNT without DISTINCT
r2 = plugin.validate('PREFIX vocab: <http://romanrepublic.ac.uk/rdf/ontology#>\nSELECT (COUNT(?pa) AS ?n) WHERE { ?pa a vocab:PostAssertion }')
print('COUNT(DISTINCT):', [s for s in r2.suggestions if 'COUNT' in s])

# Test: no LIMIT
r3 = plugin.validate('PREFIX vocab: <http://romanrepublic.ac.uk/rdf/ontology#>\nSELECT ?p ?name WHERE { ?p a vocab:Person ; vocab:hasPersonName ?name }')
print('LIMIT:', [s for s in r3.suggestions if 'LIMIT' in s])

# Test: wrong class for predicate
r4 = plugin.validate('PREFIX vocab: <http://romanrepublic.ac.uk/rdf/ontology#>\nSELECT ?o WHERE { ?p a vocab:Person ; vocab:hasOffice ?o }')
print('Wrong class:', [s for s in r4.suggestions if 'hasOffice' in s])
"
```
