# Empty-Result Diagnostics

**Date:** 2026-04-01
**Status:** Approved

## Summary

When a valid SPARQL query returns 0 rows, automatically diagnose *why* and return actionable hints alongside the empty result. This helps LLMs self-correct without an extra round-trip, and logs zero-result queries to a JSONL file for mining pain points.

## Architecture

`validate_and_execute()` gains a post-execution diagnostic step that fires only when rows are empty. Two layers run in sequence:

1. **Heuristic pass** (zero-cost) — AST + schema analysis catches known anti-patterns.
2. **Probe pass** (budget-capped at 500ms) — Cheap follow-up queries isolate which part of the query causes emptiness.

Diagnostics are appended to the existing `QueryResult.errors` list (same channel as semantic hints). No new MCP tools, no changes to the public API.

## Heuristic Checks (Zero-Cost)

All derived from the SPARQL AST, `schema_dict`, and dataset identity. No queries executed.

### 1. Date range sanity

If a FILTER constrains a date predicate (e.g., `hasEraFrom > 100`), check the schema comment for that predicate. DPRR annotates "negative = BC" in the YAML. If the filter uses positive integers on a predicate where data is predominantly negative (BC dates), hint:

> "hasEraFrom uses negative integers for BC dates. Your filter `> 100` means 'after 100 AD'. Did you mean `< -100`?"

### 2. Nomisma datetime padding

Nomisma uses ISO 8601 dates with left-padded years (e.g., `"-0044-03-15"^^xsd:date` for 44 BC). Detect FILTER expressions on predicates whose schema range is `xsd:date` or `xsd:dateTime` and check if the literal value looks unpadded or uses bare year comparison. Hint:

> "Nomisma dates use left-padded ISO 8601 (e.g., `"-0044-03-15"^^xsd:date` for 44 BC). Your filter value `"-44"` won't match. Use 4-digit zero-padded years with full date format."

Requires dataset identity to be passed into the diagnostic function.

### 3. Open-world boolean escalation

The pre-execution validator already warns about `FILTER(?x = false)` on open-world booleans, but those are non-blocking. If the query returned 0 rows and has this pattern, escalate:

> "This query returned 0 rows. The open-world boolean warning above is likely the cause."

### 4. Contradictory type constraints

If the query binds a variable to two different `rdf:type` classes (e.g., `?x a Person` and `?x a PostAssertion`), hint that no entity satisfies both types simultaneously.

### 5. String literal vs URI mismatch

If a FILTER compares a variable to a string literal but the schema says the predicate's range is a URI (or vice versa), flag it.

## Probe Pass (Budget-Capped, 500ms)

When heuristics alone aren't conclusive, run diagnostic queries against the store.

### Probe strategy (priority order)

1. **Base pattern ASK** — Extract all triple patterns (BGP), drop all FILTERs, HAVING, ORDER BY, LIMIT. Wrap as `ASK { ... }`.
   - If false: "No entities match the base graph pattern (before any filters)." Proceed to join decomposition.
   - If true: The filters are the problem. Proceed to filter isolation.

2. **Filter isolation** — Extract individual FILTER clauses. For each, rebuild the query with that single filter removed, run as ASK. First filter whose removal produces matches gets flagged:
   > "Removing `FILTER(?era > 100)` produces results. This filter is likely too restrictive."

3. **Join decomposition** (if base pattern fails) — Split triple patterns into individual `ASK { ?s ?p ?o }` checks to find which join has no matches:
   > "The pattern `?person vocab:hasPostAssertion ?post` matches, but `?post vocab:hasProvince ?prov` matches nothing — the join between PostAssertion and Province may need an intermediate class."

### Budget enforcement

Track elapsed time before each probe. Skip remaining probes if budget exhausted. Report what was checked and what was skipped.

### AST manipulation

Use rdflib's parsed algebra to strip filters and decompose patterns. No regex on SPARQL strings for structural changes.

## Zero-Result Query Log

When a query returns 0 rows, log the query and diagnostics to a JSONL file for later analysis.

**Location:** `{data_dir}/diagnostics/zero_results.jsonl` — follows the existing XDG data directory convention.

**Schema:**
```json
{
  "timestamp": "2026-04-01T14:23:01Z",
  "dataset": "dprr",
  "sparql": "SELECT ...",
  "diagnostics": ["hint1", "hint2"],
  "probe_results": {"base_pattern_matches": true, "filter_0_stripped_matches": true},
  "semantic_hints": ["pre-execution hint1"],
  "duration_ms": 342
}
```

**Write path:** Fire-and-forget append after diagnostics run. Non-blocking — if the write fails, log a warning and move on. No rotation or cleanup.

## Integration

### Changes to existing signatures

- `validate_and_execute()` gains `dataset: str | None = None` parameter
- `query()` in server.py passes `dataset` through

### New functions in `validate.py`

- `diagnose_empty_result(sparql, store, schema_dict, prefix_map, dataset, semantic_hints, budget_ms) -> DiagnosticResult` — orchestrates heuristics + probes
- `_run_heuristics(sparql, schema_dict, prefix_map, dataset, semantic_hints) -> list[str]` — zero-cost AST checks
- `_run_probes(sparql, store, schema_dict, budget_ms) -> ProbeResults` — budget-capped follow-up queries

### New dataclass

```python
@dataclass
class DiagnosticResult:
    hints: list[str]
    probe_results: dict[str, bool]
```

### New logging function

- `log_zero_result(dataset, sparql, diagnostics, semantic_hints, duration_ms)` — fire-and-forget JSONL append

### Unchanged

- MCP tool signatures (query, validate_sparql)
- Plugin API
- `QueryResult` dataclass
- `validate_sparql` tool behavior (diagnostics only fire on execution, not validation-only)

## Flow

```
query() called
  -> validate_and_execute(sparql, store, schema_dict, prefix_map, dataset)
       -> parse_and_fix_prefixes()
       -> validate_semantics()
       -> execute_query()
       -> if 0 rows:
            -> diagnose_empty_result()
                 -> _run_heuristics()    # free
                 -> _run_probes()        # up to 500ms
            -> log_zero_result()         # fire-and-forget
       -> return QueryResult (hints in errors list)
```
