# Enhanced SPARQL Validation

**Date:** 2026-03-31
**Status:** Draft

## Problem

The current validator catches syntax errors and flags unknown classes/predicates, but misses common LLM query mistakes: wrong literal types (`"63 BC"` instead of `-63`), predicates on the wrong class (`?person vocab:hasOffice` instead of `?assertion vocab:hasOffice`), missing LIMIT on large result sets, COUNT without DISTINCT on multi-row classes, and `= false` on open-world boolean properties.

## Design

### Schema Dict Enhancement

`build_schema_dict` returns richer per-property metadata instead of a bare list of range types:

```python
schema_dict[class_uri][pred_uri] = {
    "ranges": ["http://...#Office"],
    "datatype": "xsd:integer",
    "open_world": True,
    "comment": "Start date. Negative = BC.",
}

schema_dict[class_uri]["_meta"] = {
    "count_distinct": True,
}
```

Annotations added to `schemas.yaml` per-property (`open_world: true`) and per-class (`count_distinct: true`). Callers that read `schema_dict[class][pred]` as a list are updated to read `["ranges"]`.

### Recursive Variable-Chain Validation

After collecting explicit types (`?x a vocab:Person`), the validator infers types through property ranges. When `?person vocab:hasOffice ?office` and `hasOffice` has range `vocab:Office`, `?office` is inferred as `Office`. Its predicates are then validated against `Office`'s schema.

Two passes:
1. **Explicit types:** `?x a Class` → `var_types["x"] = [Class]`
2. **Inferred types:** for `?x pred ?y` where `pred`'s range is a class, add `var_types["y"] = [range_class]`. Recurse to validate `?y`'s predicates. Depth capped at 10.

This catches join pattern errors: `?person vocab:hasOffice ?office` hints "hasOffice not a known predicate for Person. Did you mean PostAssertion?"

### Literal Type Checking

For each triple `?s pred literal`, look up `pred`'s `datatype` in the schema dict. If mismatched:
- `xsd:integer` vs string literal → "hasDateStart expects integer, not string. Use -63 instead of '63 BC'."
- `xsd:boolean` vs string `"true"` → "isPatrician expects boolean true, not string 'true'."

For FILTERs: walk filter expressions looking for comparisons where a typed variable is compared to a mismatched literal.

### Domain-Specific Pattern Checks

**LIMIT safety + result size estimation:** SELECT without LIMIT where the target class has >1,000 instances (from VoID class partitions) → "Query targets PostAssertion (~9,807 instances) with no LIMIT. Consider LIMIT 100 or COUNT/GROUP BY."

**COUNT(DISTINCT):** `COUNT(?var)` where `?var` is typed as a class with `count_distinct: true` → "PostAssertion has multiple rows per person. Use COUNT(DISTINCT ?person)."

**Open-world booleans:** `FILTER(?var = false)` where `?var` is bound to a predicate with `open_world: true` → "isPatrician only stores true. Use FILTER NOT EXISTS { ?person vocab:isPatrician true }."

### VoID Integration for Size Estimation

The LIMIT check uses VoID class partitions already loaded in registry metadata:

```python
void_meta = registry.get_metadata(dataset).get("void", {})
class_counts = {cp["class"]: int(cp["entities"]) for cp in void_meta.get("classPartitions", [])}
```

No query plan analysis — just a lookup against pre-computed counts.

## Files Changed

| File | Change |
|------|--------|
| `packages/linked-past/linked_past/core/validate.py` | Enhanced `build_schema_dict`, recursive `validate_semantics`, literal/pattern checks |
| `packages/linked-past/tests/test_core_validate.py` | Tests for each new check type |
| `packages/linked-past/linked_past/datasets/dprr/context/schemas.yaml` | Add `count_distinct`, `open_world` annotations |
| `packages/linked-past/linked_past/datasets/*/context/schemas.yaml` | Add annotations where applicable |
| `packages/linked-past/linked_past/core/server.py` | Pass VoID class counts to validation |

## Scope

**In scope:**
- Schema dict enhancement (richer per-property metadata)
- Recursive variable-chain type inference
- Literal datatype checking (triples + FILTERs)
- LIMIT safety with VoID-based size estimation
- COUNT(DISTINCT) detection
- Open-world boolean detection
- schemas.yaml annotations (`open_world`, `count_distinct`)

**Out of scope:**
- OWL reasoning / entailment
- SHACL validation engine
- Query cost estimation (execution time)
- Automatic query rewriting (hints only, no auto-fix)
