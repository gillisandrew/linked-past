# DPRR MCP Tool — Usability Feedback Report

**Date:** 2026-02-25
**Context:** First-time use of the DPRR MCP tools (`get_schema`, `validate_sparql`, `execute_sparql`) to answer the question "Who was consul in 120 BC?"

---

## Summary

A straightforward query took **11 SPARQL executions** and significant trial-and-error before returning results. Every issue traced back to mismatches between what the schema/examples promise and what the actual RDF data contains. The tools themselves work fine mechanically — the problem is that the documentation steers the user into writing queries that silently return zero rows.

---

## Issue 1: Schema says `rdfs:label` on Person, but Person has no `rdfs:label`

**Severity:** Critical

The ShEx schema declares `rdfs:label [ xsd:string ]` on `vocab:Person`, and every example query uses `?person rdfs:label ?name` to get a person's display name. In reality, Person entities have **no `rdfs:label`** at all. The actual property is `vocab:hasPersonName`.

This is the single most damaging issue. Any query that joins on `?person rdfs:label ?name` (which is every example in the docs) will silently return zero rows when combined with other required patterns, because the join fails. The query *validates* successfully, *executes* without error, and returns an empty result set with no indication of what went wrong.

**Suggestion:** Either add `rdfs:label` triples to Person entities in the RDF store, or update the schema and all examples to use `vocab:hasPersonName`.

---

## Issue 2: Office labels include a "Office: " prefix not mentioned in docs

**Severity:** High

The examples use bare labels like `"consul"` and `"praetor"`:
```sparql
?office rdfs:label "consul" .
```

The actual labels in the store are prefixed: `"Office: consul"`, `"Office: consul suffectus"`, etc. Same pattern appears for other entity types (e.g. `"Praenomen: C."`, `"Secondary Source: Broughton MRR I"`).

A user following the examples will get zero results for any office-name filter.

**Suggestion:** Either strip the `"Office: "` prefix from the stored labels, or update all examples to use the prefixed form. At minimum, document this convention prominently.

---

## Issue 3: Date comparisons require explicit `xsd:integer` casting

**Severity:** High

The schema says dates are `xsd:integer` and the docs say "use integer comparison in FILTERs." A natural SPARQL integer filter like:
```sparql
FILTER(?dateStart = -120)
```
returns zero rows. So does the string form `"-120"`. The only syntax that works is:
```sparql
FILTER(?dateStart = "-120"^^xsd:integer)
```

This appears to be a serialization/parsing issue — the RDF store has the values typed as `xsd:integer`, but the SPARQL engine doesn't implicitly coerce the untyped literal `-120` to match. This is non-obvious and contradicts standard SPARQL behavior in most triple stores.

**Suggestion:** Investigate whether this is a bug in the RDF store or query engine. If it's by design, update the examples and schema docs to always show the `^^xsd:integer` cast. The current examples use bare `FILTER(?dateStart = -63)` which won't work.

---

## Issue 4: `validate_sparql` doesn't catch semantic mismatches

**Severity:** Medium

The validator checks syntax and that classes/predicates exist in the ontology — but it happily validates queries that will return zero results due to the issues above. For example, a query using `?person rdfs:label ?name` passes validation even though no Person has `rdfs:label`.

This is understandable (full semantic validation would require querying the data), but it means the validation step provides false confidence.

**Suggestion:** Consider adding warnings for common pitfalls. For example, if the validator sees `rdfs:label` used on a Person pattern, it could warn that `hasPersonName` is the correct property. Even a few heuristic warnings would save significant debugging time.

---

## Issue 5: Multi-valued properties on PostAssertion are not documented

**Severity:** Low

A single PostAssertion can have multiple `hasDateStart` values (observed on C. Marius's consul assertion: `-104`, `-100`, `-141`). The schema declares `hasDateStart [ xsd:integer ]` with no cardinality annotation, giving the impression it's single-valued. This affects how a user reasons about date filtering and result interpretation.

**Suggestion:** Add a note in the schema or skill docs about multi-valued date properties on PostAssertion, and explain what the multiple values represent (e.g., multiple consulships recorded under the same assertion vs. separate assertions per term).

---

## Overall Assessment

The mechanical infrastructure is solid: `get_schema` returns useful context, `validate_sparql` catches syntax errors, and `execute_sparql` is reliable and fast. The core problem is a **documentation–data mismatch** that makes the example queries non-functional as written. A user who copies an example verbatim and adapts it for their question will get silent empty results and have no clear path to debug.

Fixing Issues 1–3 would make the tool dramatically more usable. The examples would actually work, and the most common query pattern (find people who held office X in year Y) would succeed on the first try instead of requiring 11 iterations of detective work.
