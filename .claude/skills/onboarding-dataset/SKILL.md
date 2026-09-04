---
name: onboarding-dataset
description: Use when adding a new dataset to linked-past ("add dataset X", "onboard a source", "get Y into the server"), or when a dataset was partially onboarded and needs finishing. Not for improving one tip or one linkage on an existing dataset.
---

# Onboarding a Dataset

## Overview

Adding a dataset is a fixed sequence of stages. Each stage has an artifact that
proves it is done, and each has its own skill. This skill is the preflight, the
router, and the definition of done. Do the stages in order: the plugin's schema
comes from the cleaned data, so you cannot author context before the data is
clean.

## When to Use

- "Add dataset X", "can we get Y into linked-past", "onboard this SPARQL endpoint".
- A dataset exists in `datasets.yaml` but has no plugin, or has a plugin but no examples.
- NOT for: improving tips on an existing dataset (use `authoring-dataset-context`),
  adding cross-links (use `entity-enrichment`), fixing a parse error on an
  existing dataset (use `cleaning-rdf-dumps`).

## Preflight (settle with the user before touching files)

| Question | Why it matters |
|----------|----------------|
| Short name (lowercase letters only) | Used as OCI path, directory, plugin `name`, `LINKED_PAST_DATASETS` value |
| License, as an SPDX id (`CC-BY-4.0`, `ODbL-1.0`, `CC0-1.0`) | Must permit redistribution; it is stamped on the OCI artifact |
| Citation as BibTeX | Rendered into artifact annotations and the `citation` attribute |
| Source URL, serialization, and packaging (single file, tarball, endpoint) | Chooses the ingest path |
| Rough size (MB, triples) | Sets `min_triple_count` and warns about load time |
| Update cadence | Decides whether a scheduled workflow is worth it |
| Shares entities or an ontology with an existing dataset? | Sets `ontology_url`; queues linking |

Non-RDF sources (CSV, JSON APIs without an RDF export) are out of scope. Say so
and stop rather than inventing an ontology.

## Stage Sequence

| # | Stage | Skill | Done when |
|---|-------|-------|-----------|
| 1 | Ingest | `ingesting-rdf-source` | `datasets.yaml` entry exists; raw artifact at `raw_ref` (user confirmed the push) |
| 2 | Clean | `cleaning-rdf-dumps` | `python -m scripts.clean_dataset <name>` and `validate_dataset` pass; clean artifact at `clean_ref` |
| 3 | Context | `authoring-dataset-context` | Plugin package with four YAML files; every example returns rows against the local store; `uv run pytest packages/linked-past/tests/test_plugins.py` passes |
| 4 | Index | `enriching-search-index` | Only if `search_entities` misses entities a scholar would search for by name |
| 5 | Link | `entity-enrichment` | Only if the dataset shares entities with an existing one |

Stages 4 and 5 are conditional. Say explicitly in your report whether each was
needed and why.

## Registry touchpoints no stage skill owns

These are easy to forget and each one fails a different test or tool:

- `packages/linked-past/linked_past/datasets/__init__.py`: import the plugin class and add it to `__all__`, or `discover_plugins()` never sees it.
- `packages/linked-past/linked_past/core/registry.py` `_URI_NAMESPACES`: add the dataset's entity namespace, or `dataset_for_uri` and the meta-entity index cannot attribute its URIs.
- `packages/linked-past/tests/conftest.py`: add the name to `ALL_DATASETS` and the class path to the map in `patched_app_context`.
- `packages/linked-past/tests/test_plugins.py`: add a `PLUGIN_SPECS` tuple with a two-triple sample.
- `.github/workflows/clean-datasets.yml`: add the name to the `dataset` choice list.
- `README.md`: dataset count and list in the Packages table and the repository tree.

See `stage-map.md` for the full file list with the closest existing example for each.

## Definition of Done

```bash
uv run pytest -q
uv run ruff check .
uv run linked-past-server status          # shows the new dataset with a triple count
```

Plus: every example in `examples.yaml` was executed and returned rows;
`docs/data-lifecycle.md` gained a row if a new breakage class appeared;
the user confirmed both OCI pushes.

## Common Mistakes

- Writing `schemas.yaml` from the upstream ontology document instead of from the cleaned data. The data always differs. Use `_schema.yaml` and VoID counts.
- Starting the plugin before the clean stage passes, then rewriting it.
- Pushing to `ghcr.io` without asking. Pushes are visible to every user on next `update`.
- Adding the plugin but not the conftest map, then debugging a `KeyError` in integration tests.
- Setting `min_triple_count` to the exact observed count, so the next upstream release fails validation on a rounding change.
