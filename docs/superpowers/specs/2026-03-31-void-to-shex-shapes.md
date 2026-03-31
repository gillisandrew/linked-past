# VoID-to-ShEx Shape Generation for Search Index

**Date:** 2026-03-31
**Status:** Draft

## Problem

`get_schema` returns a flat list of classes with comments, but doesn't show how classes connect via properties. The agent has to guess join patterns (e.g., PostAssertion → Person via `isAboutPerson`), leading to wasted validation round trips.

## Design

### Shape Generation

A new function `generate_shex_shapes(schemas, tips, prefix_map)` in `ontology.py` produces compact ShEx-like shape strings from the merged schema dict. For each class:

```
# Person: A historical person from the Roman Republic period.
# TIP: Multiple PostAssertions per office — use COUNT(DISTINCT ?person).
vocab:Person {
  a [ vocab:Person ] ;
  vocab:hasPersonName xsd:string ;  # Full display name
  vocab:hasOffice [ vocab:Office ] ;  # Links to Office entity
  vocab:hasEraFrom xsd:integer ;  # Negative = BC
  vocab:isPatrician xsd:boolean ;  # Only true stored; absence = not patrician
}
```

Comments are merged in priority order:
1. Hand-written `schemas.yaml` property comments (highest — domain expertise)
2. `rdfs:comment` from ontology (fallback if no hand-written comment)
3. Tips from `tips.yaml` that reference the class (appended as `# TIP:` lines at the top)

The output is not formally valid ShEx — it's a compact, LLM-readable summary of class structure with inline domain knowledge.

### Search Index Integration

During `_build_search_index` at server startup, shape strings are added as `shex_shape` doc_type documents, one per class:

```python
shapes = generate_shex_shapes(plugin._schemas, plugin._tips, plugin._prefixes)
for cls_name, shape_text in shapes.items():
    search.add(name, "shex_shape", shape_text)
```

FTS5 matches on any term in the shape. A search for "office consul date" matches the PostAssertion shape because it contains `hasOffice`, `hasDateStart`, and the consul tip text.

Shapes surface in `analyze_question`'s "Relevant Schemas" section — no new tools needed.

### Generation Timing

Shapes are generated at server startup during `_build_search_index`, not at packaging time. This keeps packaging unchanged and ensures shapes incorporate the merged schema (hand-written + auto-generated) plus tips, all of which are only available at runtime.

## Files Changed

| File | Change |
|------|--------|
| `packages/linked-past-store/linked_past_store/ontology.py` | Add `generate_shex_shapes(schemas, tips, prefix_map)` function |
| `packages/linked-past/linked_past/core/server.py` | Call `generate_shex_shapes` in `_build_search_index`, add shapes to index |

## Scope

**In scope:**
- `generate_shex_shapes` function
- Merge hand-written comments, ontology comments, and tips into shape text
- Index shapes in FTS5 search

**Out of scope:**
- Formal ShEx validation
- Shipping shapes as OCI sidecars
- New MCP tools
