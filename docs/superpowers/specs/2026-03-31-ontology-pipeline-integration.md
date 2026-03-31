# Ontology Pipeline Integration

**Date:** 2026-03-31
**Status:** Draft
**Depends on:** ontology.py module (already built in linked-past-store)

## Problem

`ontology.py` can extract schemas from RDF data (empirically) or OWL/RDFS ontologies, but it's not wired into any workflow. Hand-written `schemas.yaml` files cover 21 DPRR classes; empirical extraction finds 37 domain classes. The 16 missing classes cause unnecessary validation warnings and incomplete `get_schema` output.

## Design

### Packaging Pipeline

Each `package_*.py` script gets a new step after VoID generation:

```
download → sanitize → verify → generate VoID → extract schema → push
```

`extract_schema(data_path=ttl_path)` runs empirical extraction against the verified data file. Output is `_schema.yaml` using the existing `_*` sidecar convention. Ships alongside `_void.ttl` and data in the OCI artifact.

All 7 datasets use empirical extraction uniformly (no special ontology-file handling for now).

### Runtime Loading

Same pattern as `_load_void`. On dataset initialization:

1. Check for `{dataset_dir}/_schema.yaml`
2. Parse YAML and store in `metadata[name]["schema"]` as a dict
3. Plugins access via `registry.get_metadata(name).get("schema")`

Add `_load_schema` method to `DatasetRegistry` alongside `_load_void`, called from both `initialize_dataset` (fresh pull) and `initialize_cached` (existing stores).

### Fallback Merge

Class-level granularity merge in the plugin base class:

```
For each class in auto-generated schema:
    If class exists in hand-written → skip (hand-written wins entirely)
    If class is new → add it to the schema dict
```

No property-level merging. If hand-written covers a class, all its properties and comments are used as-is. Auto-generated classes fill gaps only.

Filter: drop OWL/RDFS metaclasses (URIs under `w3.org`) from the auto-generated schema before merging. These are ontology machinery, not queryable domain classes.

The merge is implemented as a base class method `_merge_schema_dict(hand_written, auto_generated)` that subclasses inherit. `build_schema_dict()` returns the merged result.

### Impact on Existing Tools

- **`validate()`** — Fewer false "unknown class" warnings. No code change; uses merged schema dict.
- **`get_schema()`** — Curated classes displayed first. Auto-generated classes in a separate "## Additional Classes (auto-detected)" section at the bottom.
- **`_build_embeddings()`** — Automatically covers more classes via `plugin._schemas`. No code change.
- **`build_schema_dict()`** — Single point of change: returns merged dict instead of hand-written only.

## Files Changed

| File | Change |
|------|--------|
| `scripts/package_*.py` (all 7) | Add `extract_schema` + `generate_schemas_yaml` step, include `_schema.yaml` in push |
| `packages/linked-past/linked_past/core/registry.py` | Add `_load_schema` method |
| `packages/linked-past/linked_past/datasets/base.py` | Add `_merge_schema_dict` method, update `build_schema_dict` to use merge |
| `packages/linked-past/linked_past/datasets/*/plugin.py` | Each plugin loads auto-generated schema from registry metadata |
| `packages/linked-past-store/linked_past_store/ontology.py` | Add `META_NAMESPACES` filter for w3.org metaclasses |

## Scope

**In scope:**
- Empirical schema extraction during packaging for all 7 datasets
- `_schema.yaml` as OCI sidecar
- Registry loads `_schema.yaml` on init
- Fallback merge in plugin base class
- `get_schema` shows auto-detected classes separately
- Filter metaclasses from empirical extraction

**Out of scope:**
- Formal OWL ontology file handling (DPRR ontology fetch)
- Property-level merge
- Auto-generating `tips.yaml` or `examples.yaml`
- Replacing hand-written schemas
