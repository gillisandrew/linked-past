# Dataset Onboarding Skills Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship five project-scoped Claude Code skills that teach an agent to onboard a new RDF dataset end to end, plus a plugin hook so search-index enrichment no longer lives in core server code.

**Architecture:** Skills live in `.claude/skills/<name>/SKILL.md` with sibling reference files; they point at repository files instead of duplicating them. One new method on `DatasetPlugin` (`extra_search_entries`) replaces the hardcoded CRRO/OCRE branch in `_index_dataset`, with the coin logic moved to `linked_past/datasets/coin_types.py`. A small pytest guards skill file layout so the existing misnamed skill cannot recur.

**Tech Stack:** Python 3.13, uv workspace, pytest, pyoxigraph, SQLite FTS5 (`SearchIndex`), YAML, Claude Code skills (agentskills.io frontmatter).

**Spec:** `docs/superpowers/specs/2026-09-04-dataset-onboarding-skills-design.md`

## Global Constraints

- Run tests with `uv run pytest` from the repo root; lint with `uv run ruff check .` (line length 120, rules E F I W).
- Skill frontmatter: `name` and `description` only; `description` contains "Use when" and states triggering conditions only; frontmatter under 1024 characters.
- Skills reference `docs/data-lifecycle.md` as the canonical issue catalog and do not duplicate it wholesale.
- Nothing in this plan pushes to the OCI registry. Any command that would push is shown in skills with an explicit "confirm with the user first" note.
- The hook row format matches existing entity labels exactly: `f"{label}\t{uri}"` with `doc_type == "entity_label"`.
- Do not change search index schema, fingerprint logic, or `meta_entities.py`.
- Commit after every task with the trailer `Claude-Session: https://claude.ai/code/session_01AdwTsiDXfysqGNF1rV4498`.

---

### Task 1: Skill file layout test and rename of the existing skill

**Files:**
- Create: `scripts/tests/test_skill_files.py`
- Rename: `.claude/skills/entity-enrichment/entity-enrichment.md` to `.claude/skills/entity-enrichment/SKILL.md`

**Interfaces:**
- Produces: a test that every directory under `.claude/skills/` has a `SKILL.md` with valid frontmatter. Later tasks add skills and this test must keep passing.

- [ ] **Step 1: Write the failing test**

```python
"""Guard the layout of project skills under .claude/skills/.

Claude Code only loads a skill whose entry file is named SKILL.md. The
frontmatter rules follow the superpowers writing-skills conventions.
"""

from pathlib import Path

import pytest
import yaml

SKILLS_DIR = Path(__file__).resolve().parent.parent.parent / ".claude" / "skills"
SKILL_DIRS = sorted(p for p in SKILLS_DIR.iterdir() if p.is_dir())


def _frontmatter(path: Path) -> dict:
    text = path.read_text()
    assert text.startswith("---\n"), f"{path} must start with YAML frontmatter"
    end = text.index("\n---", 4)
    block = text[4:end]
    assert len(block) <= 1024, f"{path} frontmatter exceeds 1024 characters"
    return yaml.safe_load(block)


@pytest.mark.parametrize("skill_dir", SKILL_DIRS, ids=lambda p: p.name)
def test_skill_dir_has_skill_md(skill_dir):
    assert (skill_dir / "SKILL.md").is_file(), f"{skill_dir.name} has no SKILL.md"


@pytest.mark.parametrize("skill_dir", SKILL_DIRS, ids=lambda p: p.name)
def test_skill_frontmatter(skill_dir):
    fm = _frontmatter(skill_dir / "SKILL.md")
    assert fm["name"] == skill_dir.name
    assert "Use when" in fm["description"]
    assert set(fm) <= {"name", "description"}, f"unexpected frontmatter keys: {set(fm)}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest scripts/tests/test_skill_files.py -v`
Expected: `test_skill_dir_has_skill_md[entity-enrichment]` FAILS with "entity-enrichment has no SKILL.md"; the frontmatter test errors on the missing file.

- [ ] **Step 3: Rename the skill file**

```bash
git mv .claude/skills/entity-enrichment/entity-enrichment.md .claude/skills/entity-enrichment/SKILL.md
```

The existing frontmatter is `name: entity-enrichment` and a description containing "Use when linking persons, places, or concepts between datasets", so no content edit is needed.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest scripts/tests/test_skill_files.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/tests/test_skill_files.py .claude/skills/entity-enrichment/
git commit -m "fix: rename entity-enrichment skill to SKILL.md and guard skill layout

Claude-Session: https://claude.ai/code/session_01AdwTsiDXfysqGNF1rV4498"
```

---

### Task 2: `extra_search_entries` hook on `DatasetPlugin`

**Files:**
- Modify: `packages/linked-past/linked_past/datasets/base.py` (after `get_relevant_tips`, before the "Version / update" section, around line 213)
- Test: `packages/linked-past/tests/test_base_plugin.py`

**Interfaces:**
- Produces: `DatasetPlugin.extra_search_entries(self, store, registry) -> list[tuple[str, str]]`, returning `(doc_type, text)` rows. Default returns `[]`. Tasks 3 and 4 depend on this exact name and return shape.

- [ ] **Step 1: Write the failing test**

Append to `packages/linked-past/tests/test_base_plugin.py`:

```python
@patch("linked_past.datasets.base.DatasetPlugin.__init__", return_value=None)
def test_extra_search_entries_default_is_empty(mock_init):
    plugin = FakePlugin.__new__(FakePlugin)
    assert plugin.extra_search_entries(store=None, registry=None) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/linked-past/tests/test_base_plugin.py::test_extra_search_entries_default_is_empty -v`
Expected: FAIL with `AttributeError: 'FakePlugin' object has no attribute 'extra_search_entries'`.

- [ ] **Step 3: Add the hook**

In `base.py`, after the `get_relevant_tips` method and before the `# Version / update` banner:

```python
    # ------------------------------------------------------------------
    # Search index enrichment
    # ------------------------------------------------------------------

    def extra_search_entries(self, store: Store, registry) -> list[tuple[str, str]]:
        """Return additional ``(doc_type, text)`` rows for the search index.

        Called by the server after automatic label indexing. Use it when a
        dataset's labels are meaningless without context from elsewhere
        (e.g. coin types that need their issuer's name). Rows use the same
        text format as entity labels: ``f"{label}\\t{uri}"`` with
        ``doc_type == "entity_label"``.

        Must tolerate sibling datasets being uninitialised:
        ``registry.get_store(name)`` raises ``KeyError`` and ``registry``
        may be ``None``. Return ``[]`` when there is nothing to add.
        """
        return []
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/linked-past/tests/test_base_plugin.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add packages/linked-past/linked_past/datasets/base.py packages/linked-past/tests/test_base_plugin.py
git commit -m "feat: add DatasetPlugin.extra_search_entries hook

Claude-Session: https://claude.ai/code/session_01AdwTsiDXfysqGNF1rV4498"
```

---

### Task 3: Coin issuer enrichment helper and CRRO/OCRE hook implementations

**Files:**
- Create: `packages/linked-past/linked_past/datasets/coin_types.py`
- Modify: `packages/linked-past/linked_past/datasets/crro/plugin.py`
- Modify: `packages/linked-past/linked_past/datasets/ocre/plugin.py`
- Test: `packages/linked-past/tests/test_coin_types.py`

**Interfaces:**
- Consumes: `DatasetPlugin.extra_search_entries` from Task 2.
- Produces: `issuer_enriched_labels(dataset: str, store: Store, registry) -> list[tuple[str, str]]`. `CRROPlugin.extra_search_entries` and `OCREPlugin.extra_search_entries` call it. Task 4 removes the equivalent branch from the server.

- [ ] **Step 1: Write the failing tests**

```python
"""Tests for issuer-name enrichment of coin type labels."""

from pyoxigraph import RdfFormat, Store

from linked_past.datasets.coin_types import issuer_enriched_labels
from linked_past.datasets.crro.plugin import CRROPlugin
from linked_past.datasets.ocre.plugin import OCREPlugin

CRRO_TURTLE = """\
@prefix nmo: <http://nomisma.org/ontology#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
<http://numismatics.org/crro/id/rrc-366.1> a nmo:TypeSeriesItem ;
    skos:prefLabel "RRC 366/1" ;
    nmo:hasIssuer <http://nomisma.org/id/c_annius> .
<http://numismatics.org/crro/id/rrc-1.1> a nmo:TypeSeriesItem ;
    skos:prefLabel "RRC 1/1" ;
    nmo:hasIssuer <http://nomisma.org/id/unknown_issuer> .
"""

NOMISMA_TURTLE = """\
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
<http://nomisma.org/id/c_annius> skos:prefLabel "C. Annius"@en , "Gaius Annius"@de .
<http://nomisma.org/id/unknown_issuer> skos:prefLabel "Unbekannt"@de .
"""


class FakeRegistry:
    def __init__(self, stores: dict[str, Store]):
        self._stores = stores

    def get_store(self, name: str) -> Store:
        if name not in self._stores:
            raise KeyError(name)
        return self._stores[name]


def _store(turtle: str) -> Store:
    store = Store()
    store.bulk_load(turtle.encode(), format=RdfFormat.TURTLE)
    return store


def test_enriches_label_with_english_issuer_name():
    crro = _store(CRRO_TURTLE)
    registry = FakeRegistry({"nomisma": _store(NOMISMA_TURTLE)})

    rows = issuer_enriched_labels("crro", crro, registry)

    assert rows == [("entity_label", "RRC 366/1 — C. Annius\thttp://numismatics.org/crro/id/rrc-366.1")]


def test_issuer_without_english_label_is_skipped():
    crro = _store(CRRO_TURTLE)
    registry = FakeRegistry({"nomisma": _store(NOMISMA_TURTLE)})

    rows = issuer_enriched_labels("crro", crro, registry)

    assert all("rrc-1.1" not in text for _, text in rows)


def test_missing_nomisma_returns_empty():
    crro = _store(CRRO_TURTLE)
    assert issuer_enriched_labels("crro", crro, FakeRegistry({})) == []
    assert issuer_enriched_labels("crro", crro, None) == []


def test_crro_and_ocre_plugins_use_helper():
    crro = _store(CRRO_TURTLE)
    registry = FakeRegistry({"nomisma": _store(NOMISMA_TURTLE)})

    assert len(CRROPlugin().extra_search_entries(crro, registry)) == 1
    assert len(OCREPlugin().extra_search_entries(crro, registry)) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/linked-past/tests/test_coin_types.py -v`
Expected: collection error `ModuleNotFoundError: No module named 'linked_past.datasets.coin_types'`.

- [ ] **Step 3: Create the helper**

`packages/linked-past/linked_past/datasets/coin_types.py`:

```python
"""Search-index enrichment shared by Nomisma-based coin type corpora (CRRO, OCRE).

Coin type labels are catalogue numbers ("RRC 366/1") that no scholar searches
for by themselves. This helper appends the issuer's English name from the
Nomisma store so ``search_entities("Annius")`` finds the type.
"""

from __future__ import annotations

import logging

from pyoxigraph import Store

logger = logging.getLogger(__name__)

_ISSUER_QUERY = (
    "PREFIX nmo: <http://nomisma.org/ontology#> "
    "PREFIX skos: <http://www.w3.org/2004/02/skos/core#> "
    "SELECT DISTINCT ?coin ?coinLabel ?issuer WHERE { "
    "  ?coin a nmo:TypeSeriesItem ; "
    "        skos:prefLabel ?coinLabel ; "
    "        nmo:hasIssuer ?issuer . "
    "}"
)

_LABEL_QUERY = (
    "SELECT ?label WHERE {{ <{issuer}> <http://www.w3.org/2004/02/skos/core#prefLabel> ?label . "
    "FILTER(lang(?label) = 'en' || lang(?label) = '') }} LIMIT 1"
)


def issuer_enriched_labels(dataset: str, store: Store, registry) -> list[tuple[str, str]]:
    """Return ``("entity_label", "<coin label> — <issuer name>\\t<coin uri>")`` rows.

    Returns ``[]`` when the Nomisma store is not initialised.
    """
    if registry is None:
        return []
    try:
        nomisma_store = registry.get_store("nomisma")
    except KeyError:
        logger.info("skip issuer enrichment dataset=%s reason=nomisma not initialized", dataset)
        return []

    rows: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for coin, coin_label, issuer in store.query(_ISSUER_QUERY):
        labels = list(nomisma_store.query(_LABEL_QUERY.format(issuer=issuer.value)))
        if not labels:
            continue
        enriched = f"{coin_label.value} — {labels[0][0].value}"
        key = (coin.value, enriched)
        if key in seen:
            continue
        seen.add(key)
        rows.append(("entity_label", f"{enriched}\t{coin.value}"))
    logger.info("issuer enrichment dataset=%s rows=%d", dataset, len(rows))
    return rows
```

- [ ] **Step 4: Wire the plugins**

Add to both `CRROPlugin` and `OCREPlugin` (after `get_version_info`):

```python
    def extra_search_entries(self, store: Store, registry) -> list[tuple[str, str]]:
        from linked_past.datasets.coin_types import issuer_enriched_labels

        return issuer_enriched_labels(self.name, store, registry)
```

Add `from pyoxigraph import Store` to each plugin's imports.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest packages/linked-past/tests/test_coin_types.py packages/linked-past/tests/test_plugins.py -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add packages/linked-past/linked_past/datasets/coin_types.py packages/linked-past/linked_past/datasets/crro/plugin.py packages/linked-past/linked_past/datasets/ocre/plugin.py packages/linked-past/tests/test_coin_types.py
git commit -m "feat: move coin issuer enrichment into CRRO/OCRE plugins

Claude-Session: https://claude.ai/code/session_01AdwTsiDXfysqGNF1rV4498"
```

---

### Task 4: Server calls the hook and drops the hardcoded branch

**Files:**
- Modify: `packages/linked-past/linked_past/core/server.py:132-169` (the block starting `# Enrich coin type labels with issuer/authority names from Nomisma (cross-dataset)` and ending just before `# Index SKOS vocabulary terms`)
- Test: `packages/linked-past/tests/test_index_dataset.py`

**Interfaces:**
- Consumes: `plugin.extra_search_entries(store, registry)` from Task 2.

- [ ] **Step 1: Write the failing tests**

```python
"""Tests for _index_dataset's use of the plugin enrichment hook."""

from pyoxigraph import Store

from linked_past.core.search import SearchIndex
from linked_past.core.server import _index_dataset


class StubPlugin:
    display_name = "Stub"
    description = "A stub dataset"

    def extra_search_entries(self, store, registry):
        return [("entity_label", "RRC 366/1 — C. Annius\thttp://example.org/coin/366")]


class ExplodingPlugin(StubPlugin):
    def extra_search_entries(self, store, registry):
        raise RuntimeError("boom")


def test_index_dataset_includes_plugin_extra_entries():
    search = SearchIndex()
    _index_dataset(search, "stub", StubPlugin(), Store(), registry=None)

    results = search.search("Annius", dataset="stub", doc_type="entity_label")

    assert any("coin/366" in r["text"] for r in results)
    search.close()


def test_index_dataset_survives_hook_failure():
    search = SearchIndex()
    _index_dataset(search, "stub", ExplodingPlugin(), Store(), registry=None)

    results = search.search("stub dataset", dataset="stub", doc_type="dataset")

    assert len(results) == 1
    search.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/linked-past/tests/test_index_dataset.py -v`
Expected: `test_index_dataset_includes_plugin_extra_entries` FAILS (no rows found); the second test passes already because the old code never calls the hook. That is acceptable for a removal-plus-replacement.

- [ ] **Step 3: Replace the hardcoded block**

Delete lines 132-169 of `server.py` (from the `# Enrich coin type labels` comment through the `logger.warning("Failed to enrich %s with issuer names: %s", name, e)` line) and put this in their place:

```python
    # Dataset-specific enrichment rows (e.g. coin types with issuer names)
    try:
        extra = plugin.extra_search_entries(store, registry) if hasattr(plugin, "extra_search_entries") else []
        if extra:
            search.add_batch([(name, doc_type, text) for doc_type, text in extra])
        logger.info("Indexed %d extra search entries for %s", len(extra), name)
    except Exception as e:
        logger.warning("Failed to index extra search entries for %s: %s", name, e)
```

- [ ] **Step 4: Run the full suite and lint**

Run: `uv run pytest -q && uv run ruff check .`
Expected: all pass, no lint errors. Confirm with `grep -n '"crro", "ocre"' packages/linked-past/linked_past/core/server.py` that the old branch is gone (no output).

- [ ] **Step 5: Commit**

```bash
git add packages/linked-past/linked_past/core/server.py packages/linked-past/tests/test_index_dataset.py
git commit -m "refactor: index dataset enrichment rows via plugin hook

Claude-Session: https://claude.ai/code/session_01AdwTsiDXfysqGNF1rV4498"
```

---

### Task 5: CLAUDE.md corrections

**Files:**
- Modify: `CLAUDE.md` (Testing section, and add a Skills section)

- [ ] **Step 1: Replace the stale test note**

Replace the line

```
- When adding a new dataset plugin, add fetch patches to `tests/test_server.py`, `tests/test_linked_past_integration.py`, and `tests/test_multi_dataset_integration.py`.
```

with

```
- When adding a new dataset plugin, add it to `ALL_DATASETS` and the plugin-class map in the `patched_app_context` fixture in `packages/linked-past/tests/conftest.py`, and add a `PLUGIN_SPECS` entry in `tests/test_plugins.py`.
```

- [ ] **Step 2: Add a Skills section at the end of CLAUDE.md**

```
## Skills

Project skills live in `.claude/skills/`. `onboarding-dataset` is the entry point for adding a dataset and routes to the stage skills: `ingesting-rdf-source`, `cleaning-rdf-dumps`, `authoring-dataset-context`, `enriching-search-index`, `entity-enrichment`. Each skill must be a `SKILL.md` (enforced by `scripts/tests/test_skill_files.py`).
```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: correct plugin test guidance and list project skills

Claude-Session: https://claude.ai/code/session_01AdwTsiDXfysqGNF1rV4498"
```

---

### Task 6: `onboarding-dataset` skill

**Files:**
- Create: `.claude/skills/onboarding-dataset/SKILL.md`
- Create: `.claude/skills/onboarding-dataset/stage-map.md`

**Interfaces:**
- Produces: skill names referenced verbatim by other skills: `ingesting-rdf-source`, `cleaning-rdf-dumps`, `authoring-dataset-context`, `enriching-search-index`, `entity-enrichment`.

- [ ] **Step 1: Write SKILL.md**

````markdown
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
````

- [ ] **Step 2: Write stage-map.md**

````markdown
# Stage Map: every file touched when onboarding a dataset

Copy the closest existing example rather than starting from a blank file.

## Stage 1: Ingest

| File | Purpose | Closest example |
|------|---------|-----------------|
| `datasets.yaml` | Single source of truth: refs, license, citation, threshold, fetch settings | `crro` (generic RDF/XML), `pleiades` (bespoke) |
| `scripts/ingest_generic.py` | Handles `fetch_url` + `source_format` in {`rdf-xml`, `json-ld`, `turtle`} | used by crro, ocre, rpc |
| `scripts/ingest_<name>.py` | Bespoke download/convert/push | `ingest_dprr.py` (tarball), `ingest_periodo.py` (JSON-LD), `ingest_nomisma.py` (RDF/XML with URI repair), `ingest_edh.py` (local zip), `ingest_pleiades.py` (multi-file Turtle) |
| `scripts/extract_from_endpoint.py` | Dump a SPARQL endpoint to Turtle | DPRR endpoint behind a bot shield |
| `scripts/convert_n3_to_ttl.py`, `scripts/rebind_prefixes.py` | N3 to Turtle; namespace rebinding | DPRR |
| `.github/workflows/ingest-<name>.yml` | Scheduled ingest | `ingest-pleiades.yml` |
| `scripts/pipeline_config.py` | `load_dataset_config`, `build_annotations` (do not edit; import) | |

## Stage 2: Clean

| File | Purpose | Closest example |
|------|---------|-----------------|
| `scripts/clean_dataset.py` | Pull raw, sanitize, verify, VoID, schema, ontology sidecar, diff, push clean | generic; driven by `datasets.yaml` |
| `scripts/validate_dataset.py` | Pull clean, verify, enforce `min_triple_count` | generic |
| `packages/linked-past-store/linked_past_store/sanitize.py` | Generic Turtle fixes (`_regex_fixes`) | BCP 47 tags, bare DOIs |
| `scripts/fix_pleiades_refs.py` | Example of a dataset-specific repair applied at ingest | Pleiades |
| `docs/data-lifecycle.md` | Catalog of upstream data issues; add a row for any new class | |
| `.github/workflows/clean-datasets.yml` | Add the dataset to the `options` list | |

## Stage 3: Context

| File | Purpose | Closest example |
|------|---------|-----------------|
| `packages/linked-past/linked_past/datasets/<name>/__init__.py` | Empty package marker | any |
| `packages/linked-past/linked_past/datasets/<name>/plugin.py` | `DatasetPlugin` subclass with metadata attributes | `edh/plugin.py` (minimal), `crro/plugin.py` (with `get_version_info` and `extra_search_entries`) |
| `packages/linked-past/linked_past/datasets/<name>/context/prefixes.yaml` | Prefix map | `edh/context/prefixes.yaml` |
| `.../context/schemas.yaml` | Hand-written classes and properties | `edh/context/schemas.yaml` |
| `.../context/examples.yaml` | Question + SPARQL pairs | `edh/context/examples.yaml` |
| `.../context/tips.yaml` | Query quirks tagged by class | `edh/context/tips.yaml` |
| `packages/linked-past/linked_past/datasets/__init__.py` | Import + `__all__` entry | |
| `packages/linked-past/linked_past/core/registry.py` | `_URI_NAMESPACES` entry | |
| `packages/linked-past/tests/conftest.py` | `ALL_DATASETS` + plugin map | |
| `packages/linked-past/tests/test_plugins.py` | `PLUGIN_SPECS` entry | |

## Stage 4: Index

| File | Purpose | Closest example |
|------|---------|-----------------|
| `.../datasets/<name>/plugin.py` `extra_search_entries` | Enriched search rows | `crro/plugin.py` via `datasets/coin_types.py` |
| `packages/linked-past/linked_past/core/server.py` `_index_dataset` | Automatic label indexing (read, do not edit) | |

## Stage 5: Link

| File | Purpose | Closest example |
|------|---------|-----------------|
| `packages/linked-past/linked_past/linkages/<src>_<dst>_<confidence>.yaml` | Curated links | `dprr_nomisma_confirmed.yaml` |
| `packages/linked-past/linked_past/linkages/wikidata/*.ttl` | Wikidata concordances | |

## Docs

| File | Purpose |
|------|---------|
| `README.md` | Dataset count and list |
| `docs/data-lifecycle.md` | Issue catalog |
````

- [ ] **Step 3: Verify layout test passes**

Run: `uv run pytest scripts/tests/test_skill_files.py -v`
Expected: 4 passed (two skills, two tests each).

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/onboarding-dataset/
git commit -m "docs(skills): add onboarding-dataset orchestrator skill

Claude-Session: https://claude.ai/code/session_01AdwTsiDXfysqGNF1rV4498"
```

---

### Task 7: `ingesting-rdf-source` skill

**Files:**
- Create: `.claude/skills/ingesting-rdf-source/SKILL.md`
- Create: `.claude/skills/ingesting-rdf-source/source-recipes.md`

- [ ] **Step 1: Write SKILL.md**

````markdown
---
name: ingesting-rdf-source
description: Use when writing or changing an ingest script, adding a datasets.yaml entry, pushing a raw dataset artifact to the OCI registry, or setting up a scheduled ingest workflow for an RDF source (Turtle, RDF/XML, JSON-LD, N3, tarball, SPARQL endpoint).
---

# Ingesting an RDF Source

## Overview

Ingest turns an upstream publication into one raw Turtle file on the OCI
registry at `raw_ref`. It owns only source-format-specific fixes. Anything that
would apply to any Turtle file belongs to the clean stage.

## When to Use

- New dataset: no `datasets.yaml` entry yet.
- Upstream changed packaging (new URL, new format, new tarball layout).
- Ingest fails before a Turtle file exists (download, XML parse, conversion).
- NOT for: Turtle that exists but fails strict verification (use `cleaning-rdf-dumps`).

## Procedure

### 1. Pick the ingest path

```
single RDF/XML, JSON-LD, or Turtle URL     -> scripts/ingest_generic.py, no new code
tarball / zip / multi-file directory        -> bespoke scripts/ingest_<name>.py
SPARQL endpoint                             -> scripts/extract_from_endpoint.py pattern, then bespoke push
N3 or wrong namespaces                      -> convert_n3_to_ttl.py / rebind_prefixes.py, then bespoke push
upstream republishes on a schedule          -> also add .github/workflows/ingest-<name>.yml
```

Recipes for each are in `source-recipes.md`.

### 2. Add the `datasets.yaml` entry

Required for every dataset:

```yaml
<name>:
  raw_ref: ghcr.io/gillisandrew/linked-past/raw/<name>:latest
  clean_ref: ghcr.io/gillisandrew/linked-past/datasets/<name>:latest
  ingest_script: scripts/ingest_<name>.py        # or scripts/ingest_generic.py
  min_triple_count: 0                             # set after first clean run
  license: <SPDX id>
  source_url: <landing page>
  description: "<one line, shown in discover_datasets>"
  citation: |
    @misc{...}
```

Add for the generic script: `fetch_url` and `source_format` (`rdf-xml`, `json-ld`, `turtle`).
Add `ontology_url` when the data uses an external ontology whose axioms
matter for inference (CRRO, OCRE, RPC point at `http://nomisma.org/ontology.ttl`).

`scripts/pipeline_config.py` reads this file. `build_annotations(ds, name)`
turns it into OCI annotations; do not construct annotations by hand.

### 3. Dry run without pushing

Never push on the first run. Download and convert into a scratch directory,
then inspect:

```bash
uv run python - <<'EOF'
from pathlib import Path
from linked_past_store import verify_turtle
r = verify_turtle(Path("scratch/<name>.ttl"))
print(r.triple_count, r.errors[:3])
EOF
head -c 2000 scratch/<name>.ttl
grep -c '^<' scratch/<name>.ttl      # rough subject count
```

For the generic script, the cheapest dry run is to call its conversion
steps in a REPL or to temporarily point `raw_ref` at a local registry.
For bespoke scripts, structure `main()` so the push is the final statement
and can be skipped with an environment variable or a `--no-push` argument.

Record the triple count. `min_triple_count` will be set to about 90% of it
in the clean stage.

### 4. Push the raw artifact

Pushing is an outward-facing side effect. Confirm with the user first, then:

```bash
uv run python -m scripts.ingest_<name>          # or: -m scripts.ingest_generic <name>
```

`push_dataset(ref, path, annotations=...)` from `linked_past_store` does the
upload and returns the digest. It needs registry credentials (`oras login ghcr.io`).

### 5. Optional: scheduled workflow

Copy `.github/workflows/ingest-pleiades.yml`. Keep `workflow_dispatch` so it
can be run by hand, set `permissions: packages: write`, and log in with
`oras login ghcr.io` using `GITHUB_TOKEN`.

## Rules

- Ingest owns source-format fixes only: XML entities, IRI whitespace, placeholder IRIs, wrong namespaces, tarball concatenation. Generic Turtle fixes go in `linked_past_store/sanitize.py`.
- Send `User-Agent: linked-past/1.0`; some hosts block Python's default agent with HTTP 403.
- Keep the raw artifact as close to upstream as parses. The clean stage records what it changed; ingest changes are invisible downstream unless the script prints counts.
- Print the count of every fix applied so it can be compared on the next upstream release.

## Common Mistakes

- Converting RDF/XML with lenient tools and never running a strict parse, so breakage surfaces in the clean stage with no line numbers.
- Hand-writing OCI annotations instead of `build_annotations`.
- Pushing a test run to `raw_ref:latest`, which the next clean run will pick up.
````

- [ ] **Step 2: Write source-recipes.md**

````markdown
# Source Recipes

Each recipe names the script that already does this. Read that script before
writing a new one.

## RDF/XML at a URL (CRRO, OCRE, RPC)

`scripts/ingest_generic.py` with `source_format: rdf-xml`. It injects a
DOCTYPE declaring `&nbsp;` so files using HTML entities parse, converts with
`rapper`, and pushes. Known gaps handled elsewhere: placeholder IRIs (`-`,
`—`), trailing whitespace in IRIs, interior spaces (see
`docs/data-lifecycle.md`, "IRI-level issues"). If a new RDF/XML source hits
one of those, extend the generic script's rewrite step rather than adding a
bespoke script.

## JSON-LD at a URL (PeriodO)

`scripts/ingest_generic.py` with `source_format: json-ld`, or
`scripts/ingest_periodo.py` when the download needs a custom step. Conversion
is `rdflib.Graph().parse(format="json-ld")` then `serialize(format="turtle")`.
JSON-LD contexts fetched over the network can fail silently; verify the
triple count is in the expected range.

## Turtle in a release tarball (DPRR)

`scripts/ingest_dprr.py`: download the tarball, extract the single `.ttl`,
push. Pattern: `tarfile.open(...).extractall(tmpdir)` then locate the file
by suffix rather than by a hardcoded name.

## Many Turtle files in a git checkout (Pleiades)

`scripts/ingest_pleiades.py` and `.github/workflows/ingest-pleiades.yml`:
sparse-checkout the upstream repo, concatenate the files in sorted order with
a `# Source:` comment before each, apply source-specific IRI repairs
(`%23` to `#`, missing `place-types/` segment, truncated subresource
references via `scripts/fix_pleiades_refs.py`), push. Concatenation is safe
because each file declares its own prefixes.

## Local zip that cannot be downloaded (EDH)

`scripts/ingest_edh.py`: reads `edh_linked_data.zip` from the repo root
(gitignored, obtained by hand), extracts all Turtle files, pushes them as a
multi-layer artifact. The plugin's default `load` handles multi-file
datasets by loading every non-underscore `.ttl` in the dataset directory.

## SPARQL endpoint (DPRR before the release tarball existed)

`scripts/extract_from_endpoint.py`: page through `CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o } LIMIT n OFFSET m`
until a page returns fewer than `n` triples, append each page to one file.
The DPRR endpoint sits behind a proof-of-work bot shield; the script prompts
for a browser session cookie when direct requests fail. Expect endpoints to
cap result sizes; keep the page size at or below the cap.

## N3 export with the wrong namespace (DPRR)

`scripts/convert_n3_to_ttl.py` parses N3 with rdflib and re-serializes as
Turtle; `scripts/rebind_prefixes.py` rebinds prefixes to the documented
namespaces. Namespace choice matters because the plugin's `prefixes.yaml`
and every example depend on it.

## RDF/XML with Unicode replacement characters in IRIs (Nomisma)

`scripts/ingest_nomisma.py`: after conversion, corrects two known DBpedia
IRIs where Turkish characters were lost upstream, and strips any remaining
lines containing U+FFFD. A replacement character in an IRI is unrecoverable
in general; correct known cases, drop the rest, and print the count.
````

- [ ] **Step 3: Verify layout test and commit**

Run: `uv run pytest scripts/tests/test_skill_files.py -q`
Expected: pass.

```bash
git add .claude/skills/ingesting-rdf-source/
git commit -m "docs(skills): add ingesting-rdf-source skill

Claude-Session: https://claude.ai/code/session_01AdwTsiDXfysqGNF1rV4498"
```

---

### Task 8: `cleaning-rdf-dumps` skill

**Files:**
- Create: `.claude/skills/cleaning-rdf-dumps/SKILL.md`
- Create: `.claude/skills/cleaning-rdf-dumps/issue-catalog.md`

- [ ] **Step 1: Write SKILL.md**

````markdown
---
name: cleaning-rdf-dumps
description: Use when a dataset's Turtle fails strict parsing, validate_dataset fails, the triple count is under threshold, the schema diff shows unexpected churn, or a new dataset is being cleaned for the first time. Covers classifying upstream data breakage and deciding which pipeline stage owns the fix.
---

# Cleaning RDF Dumps

## Overview

Upstream scholarly datasets are not written for strict parsers. The clean
stage (`scripts/clean_dataset.py`) turns the raw artifact into one that
pyoxigraph loads without error, plus VoID and schema sidecars. When it
fails, the job is to classify the breakage and fix it at the earliest stage
that owns that kind of problem. Never hand-edit an artifact.

## When to Use

- `clean_dataset` or `validate_dataset` exits non-zero.
- `verify_turtle` reports errors for a file the ingest produced.
- The schema diff printed by `clean_dataset` shows classes vanishing.
- NOT for: download or conversion failures before a Turtle file exists (use `ingesting-rdf-source`).

## Procedure

### 1. Reproduce with a strict parse and capture the first error

```bash
uv run python - <<'EOF'
from linked_past_store import verify_turtle
r = verify_turtle("scratch/<name>.ttl")
print(r.triple_count)
for e in r.errors: print(e)
EOF
```

pyoxigraph errors name a line and column. Look at that line:

```bash
sed -n '<line-2>,<line+2>p' scratch/<name>.ttl
```

### 2. Classify the breakage

| Level | Symptom | Owner |
|-------|---------|-------|
| XML | The XML parser fails before RDF is considered (undefined entity, bad UTF-8) | Ingest script (`ingesting-rdf-source`) |
| IRI | Valid XML, IRI violates RFC 3987 (spaces, placeholder `-`, U+FFFD, missing scheme) | Ingest script when source-specific; `sanitize.py` when any Turtle could have it |
| Turtle | Valid RDF/XML, strict Turtle parser rejects (language subtag over 8 chars, percent-encoded `#`) | `linked_past_store/sanitize.py` `_regex_fixes` |
| Semantic | Parses, but the triples are wrong (dangling references, duplicate literals, wrong namespace) | Ingest script for reference repair; schema YAML for namespace; `store.materialize` for inference artifacts |

Look the symptom up in `issue-catalog.md` before writing a fix. Most have
been seen before and the fix already exists in one of those files.

### 3. Fix at the owning stage

- `sanitize.py`: add a compiled regex and apply it in `_regex_fixes`; return the count so `SanitizeResult.fixes` stays accurate. Add a test in `packages/linked-past-store/tests/`.
- Ingest script: apply the fix to the raw text before push and print the count.
- Never edit the Turtle by hand, and never commit a patched artifact. The next upstream release must go through the same code.

### 4. Re-run and record counts

```bash
uv run python -m scripts.clean_dataset <name>       # pulls raw, sanitizes, verifies, pushes clean (confirm push with user)
uv run python -m scripts.validate_dataset <name>
```

`clean_dataset` prints the number of fixes and the schema diff against the
previous version. Copy the fix count into the `docs/data-lifecycle.md`
catalog row so the next release can be compared.

### 5. Set the threshold

`min_triple_count` in `datasets.yaml` should be about 90% of the verified
count, rounded down to a clean number. Too tight fails on harmless upstream
edits; too loose lets a truncated download through.

### 6. Read the schema diff

Removed classes or a class whose count fell by more than half almost always
mean a conversion error, not an upstream change. Check before pushing.

### 7. Catalog it

Any breakage class not already in `docs/data-lifecycle.md` gets a row in the
matching table (XML, IRI, Turtle, semantic) in the same change as the fix.

## Rules

- Fix at the earliest stage that owns the quirk; a generic fix in `sanitize.py` runs for every dataset, so it must be safe for all of them.
- Every fix prints or returns a count.
- Strict parse after every fix. Lenient tools (`rapper`) hide problems; pyoxigraph is the arbiter.

## Common Mistakes

- Using `sed` on the artifact and moving on. The fix vanishes on the next ingest.
- Putting a Pleiades-only IRI repair into `sanitize.py`, where it runs against every dataset.
- Replacing an over-long language tag with `@en` instead of a private-use tag, losing information.
- Treating a lower triple count as "upstream shrank" without checking the schema diff.
````

- [ ] **Step 2: Write issue-catalog.md**

````markdown
# Issue Catalog by Symptom

The canonical catalog is the "Catalog of upstream data issues" section of
`docs/data-lifecycle.md`. This file indexes it by what you see in the parser
error, and says where the fix already lives.

## The XML parser fails

| You see | Cause | Fix lives in |
|---------|-------|--------------|
| `undefined entity` naming `nbsp`, `mdash`, `ndash` | HTML entities in RDF/XML text | `scripts/ingest_generic.py` DOCTYPE injection |
| HTTP 403 on download | Host blocks default Python user agent | `scripts/ingest_generic.py` sends `User-Agent: linked-past/1.0` |

## The IRI is rejected

| You see | Cause | Fix lives in |
|---------|-------|--------------|
| Invalid IRI `-` or `—` | Placeholder values in `rdf:resource` | Ingest rewrite: drop the attribute |
| IRI ending in a space | Trailing whitespace upstream | Ingest rewrite: strip |
| IRI with an interior space | Unencoded local names | Ingest rewrite: percent-encode to `%20` |
| IRI containing U+FFFD | Characters lost upstream | `scripts/ingest_nomisma.py`: correct known cases, drop the rest |
| `<doi.org/10....>` rejected | Bare DOI without scheme | `linked_past_store/sanitize.py` `_BARE_DOI` |

## The Turtle parser rejects a line

| You see | Cause | Fix lives in |
|---------|-------|--------------|
| Error on a literal with `@` followed by a long tag | BCP 47 subtag over 8 characters (`@etruscan-in-latin-characters`) | `sanitize.py` `_LANG_TAG` and `_fix_lang_tag`: known tags map to private-use forms like `@x-etruscan-latn`; unknown tags drop oversized subtags |
| Parses, but subjects like `.../433134%23this` never match `#this` | Percent-encoded fragment | `scripts/ingest_pleiades.py` and workflow: `%23` to `#` |
| Parses, but `/vocabularies/abbey` has no definition | Missing path segment | `scripts/ingest_pleiades.py`: insert `place-types/` |

## It parses but the data is wrong

| You see | Cause | Fix lives in |
|---------|-------|--------------|
| `hasLocation` / `hasName` objects have no triples | Truncated subresource references (`/places/<slug>` instead of `/places/<id>/<slug>`) | `scripts/fix_pleiades_refs.py` at ingest |
| Duplicate labels, one tagged `@en` and one untagged | Language tags dropped during materialization | `linked_past/core/store.py` `materialize` preserves `Literal.language` and `.datatype` |
| Predicate under `http://lawd.info/ontology/1.0/` does not match `lawd:` prefix | Upstream uses a versioned namespace | `prefixes.yaml` plus a tip explaining the versioned IRI (EDH) |
| Diagnostic lines like `rapper: Parsing ...` inside the Turtle | rapper wrote to stdout | `sanitize.py` `_RAPPER_LOG` strip |

## Deciding where a new fix goes

```
Would the same regex be correct on every other dataset?   yes -> sanitize.py
Is it about the source's serialization or packaging?      yes -> ingest script
Is it a namespace or ontology mismatch?                   yes -> prefixes.yaml / schemas.yaml + a tip
Is it an inference artifact?                              yes -> store.materialize
```
````

- [ ] **Step 3: Verify layout test and commit**

Run: `uv run pytest scripts/tests/test_skill_files.py -q`
Expected: pass.

```bash
git add .claude/skills/cleaning-rdf-dumps/
git commit -m "docs(skills): add cleaning-rdf-dumps skill

Claude-Session: https://claude.ai/code/session_01AdwTsiDXfysqGNF1rV4498"
```

---

### Task 9: `authoring-dataset-context` skill

**Files:**
- Create: `.claude/skills/authoring-dataset-context/SKILL.md`
- Create: `.claude/skills/authoring-dataset-context/context-yaml-reference.md`

- [ ] **Step 1: Write SKILL.md**

````markdown
---
name: authoring-dataset-context
description: Use when creating a dataset plugin package, writing or improving prefixes.yaml, schemas.yaml, examples.yaml, or tips.yaml, when a user reports the model writing bad SPARQL for a dataset, or when get_schema output for a dataset is thin.
---

# Authoring Dataset Context

## Overview

The four YAML files in a plugin's `context/` directory are everything the
model gets about a dataset: what classes exist, what predicates and value
shapes they have, worked queries, and the quirks that would otherwise cost a
failed query. Write them from the cleaned data, not from the upstream
ontology document. Then prove every example runs.

## When to Use

- New plugin package (after the clean stage has produced `_schema.yaml` and `_void.ttl`).
- A query the model wrote failed for a reason the data made predictable.
- `get_schema` for a dataset shows only auto-detected classes.
- NOT for: search misses by name (use `enriching-search-index`).

## Procedure

### 1. Get the data locally

```bash
uv run linked-past-server update <name>     # pulls clean artifact, builds store
ls "${LINKED_PAST_DATA_DIR:-$HOME/.local/share/linked-past}/<name>"   # <name>.ttl _void.ttl _schema.yaml
```

### 2. Create the plugin package

`packages/linked-past/linked_past/datasets/<name>/__init__.py` (empty),
`plugin.py`, and `context/` with the four files. Skeletons are in
`context-yaml-reference.md`. The parametrized tests in
`tests/test_plugins.py` require: `name`, `display_name`, `description`,
`citation`, `license`, `url`, `time_coverage`, `spatial_coverage`,
`oci_dataset = "datasets/<name>"`. Do not override `fetch` or `load` unless
the dataset needs a different loading rule; the base `load` already handles
multi-file datasets, the ontology sidecar, and materialization.

### 3. Write `prefixes.yaml` from the data

List every namespace that appears in the data with a short prefix. Verify
each one with a query rather than trusting the ontology documentation:

```sparql
SELECT ?p (COUNT(*) AS ?n) WHERE { ?s ?p ?o } GROUP BY ?p ORDER BY DESC(?n) LIMIT 50
```

If a predicate lives under a versioned or unexpected namespace (EDH's
`http://lawd.info/ontology/1.0/foundAt`), keep the standard prefix for the
standard namespace and write a tip about the odd one.

### 4. Write `schemas.yaml` from `_schema.yaml` and VoID

Open `_schema.yaml` and `_void.ttl`. Hand-write only the classes a scholar
would ask about, typically three to eight. Long-tail classes stay in the
auto schema, which the registry merges in at load time. For each class:

- `uri` in prefixed form, `label`, and a `comment` that says what an
  instance is in this dataset's terms.
- Every property a query would plausibly touch, with `range` and a `comment`
  that describes what the values actually look like (`"string like '0071'"`,
  `"links to a Nomisma concept URI"`), because that is what the model needs
  to write a `FILTER`.

Check each property's real range:

```sparql
SELECT ?o WHERE { ?s a <ClassURI> ; <PredicateURI> ?o } LIMIT 5
```

### 5. Write `examples.yaml`

Each example is a `question` phrased the way a user would ask it, and a
`sparql` block that:

- declares every prefix it uses inline (examples are copied verbatim),
- targets one concept,
- ends with `LIMIT`,
- returns a human-readable label column, not only URIs.

Together the examples must touch every hand-written class; the validator
matches examples to queries by class. Aim for six to twelve.

### 6. Write `tips.yaml`

A tip is a fact that would otherwise cost the model a failed query. Sources:
every surprise you hit in steps 3 to 5. Typical tips: date encoding and how
to compare it, which label predicate carries language tags, predicates that
look like one ontology but are another, coverage gaps ("no inscriptions
before 50 BC"), which of two similar text fields to search. Tag each tip with
the `classes` it applies to; an empty list makes it a cross-cutting tip shown
in `get_schema`.

### 7. Verify

Run every example against the store and require rows:

```bash
uv run python - <<'EOF'
import yaml
from pathlib import Path
from linked_past.core.store import get_read_only_store, get_data_dir
name = "<name>"
store = get_read_only_store(get_data_dir() / name / "store")
examples = yaml.safe_load(Path(f"packages/linked-past/linked_past/datasets/{name}/context/examples.yaml").read_text())["examples"]
for ex in examples:
    rows = list(store.query(ex["sparql"]))
    print(f"{len(rows):5d}  {ex['question']}")
    assert rows, f"empty result: {ex['question']}"
EOF
```

Then:

```bash
uv run pytest packages/linked-past/tests/test_plugins.py -q
```

Then start the server, call `validate_sparql` with a deliberately wrong
query against one of your classes, and confirm your tips appear in the
response.

### 8. Register the plugin

`datasets/__init__.py` import and `__all__`; `registry.py` `_URI_NAMESPACES`;
`tests/conftest.py` map; `tests/test_plugins.py` `PLUGIN_SPECS` with a
two-triple sample that instantiates one hand-written class.

## Common Mistakes

- Copying class lists from the ontology PDF. Half of them have zero instances.
- Property comments that restate the ontology ("the start date") instead of the value shape ("xsd:string like '-0044', zero-padded, negative is BC").
- Examples with a prefix used but not declared; they fail when copied.
- Examples without `LIMIT`; the model copies them and floods the viewer.
- Tips that are general SPARQL advice. If it is true of every dataset it is not a tip.
- Not tagging tips with classes, so they never surface during validation.
````

- [ ] **Step 2: Write context-yaml-reference.md**

````markdown
# Context YAML Reference

Loaders are in `packages/linked-past/linked_past/core/context.py`. Each file
has one top-level key; the loader reads exactly that key.

## plugin.py skeleton

```python
"""<Display name> dataset plugin."""

from __future__ import annotations

from linked_past.datasets.base import DatasetPlugin


class <Name>Plugin(DatasetPlugin):
    name = "<name>"
    display_name = "<Display Name (ACRONYM)>"
    description = "<two sentences: what it contains, how many things, what period>"
    citation = "<Authors, Title, URL. License.>"
    license = "<CC BY 4.0>"
    url = "<landing page>"
    time_coverage = "<e.g. 509-31 BC>"
    spatial_coverage = "<e.g. Roman Republic>"
    oci_dataset = "datasets/<name>"
    oci_version = "latest"
```

Override `get_version_info(self, data_dir)` only to report a different
`source_url` (see `crro/plugin.py`). Override `extra_search_entries` per the
`enriching-search-index` skill.

## prefixes.yaml

Top-level key `prefixes`, a map of prefix to namespace. Always include
`rdf`, `rdfs`, `xsd`, `skos`, `dcterms` because the auto-repair in
validation inserts missing `PREFIX` lines from this map.

```yaml
prefixes:
  ex: "http://example.org/ontology#"
  rdfs: "http://www.w3.org/2000/01/rdf-schema#"
  rdf: "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
  xsd: "http://www.w3.org/2001/XMLSchema#"
  skos: "http://www.w3.org/2004/02/skos/core#"
  dcterms: "http://purl.org/dc/terms/"
```

## schemas.yaml

Top-level key `classes`, a map of class name to:

| Field | Required | Meaning |
|-------|----------|---------|
| `uri` | yes | Prefixed class IRI; rendered in `get_schema` and used to match queries to examples and tips |
| `label` | yes | Human label |
| `comment` | yes | What an instance is in this dataset |
| `properties` | yes | List of `{pred, range, comment}` |

`range` is a prefixed datatype or class (`xsd:string`, `xsd:anyURI`,
`ex:Person`). The validator uses `pred` names: any property whose name
contains `name`, `label`, or `title` is also used by the search indexer as a
label predicate.

```yaml
classes:
  Inscription:
    label: "Inscription"
    comment: "A Latin inscription with transcription, date, and findspot."
    uri: "epi:Inscription"
    properties:
      - pred: "skos:prefLabel"
        range: "xsd:string"
        comment: "Type and findspot summary, e.g. 'epitaph found at Roma (Latium)'"
      - pred: "nmo:hasStartDate"
        range: "xsd:string"
        comment: "Earliest date as a zero-padded string like '0071'; negative means BC"
```

## examples.yaml

Top-level key `examples`, a list of `{question, sparql}`. The loader adds a
`classes` field at runtime by scanning the SPARQL for class IRIs from
`schemas.yaml`.

```yaml
examples:
  - question: "Find all epitaphs"
    sparql: |
      PREFIX epi: <http://edh-www.adw.uni-heidelberg.de/lod/ontology#>
      PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
      SELECT ?insc ?label
      WHERE {
        ?insc a epi:Inscription ;
              skos:prefLabel ?label ;
              epi:representsTypeOfInscription ?type .
        FILTER(CONTAINS(LCASE(STR(?type)), "epitaph"))
      }
      LIMIT 100
```

## tips.yaml

Top-level key `tips`, a list of `{title, body, classes}`. `title` is a short
snake_case handle; `body` may be multi-line and may contain a SPARQL
fragment; `classes` lists class names from `schemas.yaml` (empty list for
cross-cutting).

```yaml
tips:
  - title: "date_as_string"
    body: |
      nmo:hasStartDate is an xsd:string like '0071', not an integer.
      Compare as strings: FILTER(STR(?startDate) <= "-0001").
      Coverage begins around 2 BC; do not expect Republican-era results.
    classes: ["Inscription"]
```

## What the tests check

`tests/test_plugins.py` instantiates every plugin in `PLUGIN_SPECS` and
asserts: the metadata attributes exist and `license` matches; the required
prefix is present; the schema rendering mentions the listed class keywords;
a valid query validates; an unknown class is a warning not an error; the
sample Turtle loads with a positive count; `get_version_info` reports
`turtle`.
````

- [ ] **Step 3: Verify layout test and commit**

Run: `uv run pytest scripts/tests/test_skill_files.py -q`
Expected: pass.

```bash
git add .claude/skills/authoring-dataset-context/
git commit -m "docs(skills): add authoring-dataset-context skill

Claude-Session: https://claude.ai/code/session_01AdwTsiDXfysqGNF1rV4498"
```

---

### Task 10: `enriching-search-index` skill

**Files:**
- Create: `.claude/skills/enriching-search-index/SKILL.md`

**Interfaces:**
- Consumes: `DatasetPlugin.extra_search_entries` (Task 2), `issuer_enriched_labels` (Task 3).

- [ ] **Step 1: Write SKILL.md**

````markdown
---
name: enriching-search-index
description: Use when search_entities cannot find entities by the names a scholar would use, when a dataset's labels are catalogue numbers or codes, when a label predicate is not being indexed, or when a dataset should contribute to the meta-entity index.
---

# Enriching the Search Index

## Overview

`search_entities` runs over an FTS5 index built at startup by
`_index_dataset` in `linked_past/core/server.py`. Most datasets are findable
with no work because their labels are names. Enrichment is for the rest:
labels that are codes, names that live under an unusual predicate, or
entities that need a word from another dataset to be searchable.

## When to Use

- Five representative searches (below) miss.
- A dataset's `skos:prefLabel` values look like `RRC 366/1` or `HD000001`.
- NOT for: cross-dataset identity links (use `entity-enrichment`); bad SPARQL (use `authoring-dataset-context`).

## How indexing works (read before changing anything)

Per dataset, `_index_dataset` adds:

1. `dataset`, `example`, `tip`, `schema_label`, `schema_comment`, `shex_shape` rows from the plugin's YAML.
2. `entity_label` rows, `"{label}\t{uri}"`, for every value of a fixed predicate list (`rdfs:label`, `skos:prefLabel`, `skos:altLabel`, `dcterms:title`, two Pleiades name predicates) plus every property in `schemas.yaml` whose `pred` name contains `name`, `label`, or `title`.
3. Rows returned by the plugin's `extra_search_entries(store, registry)` hook.
4. `skos_vocab` rows summarising each SKOS concept scheme.

The index is cached with a fingerprint. After changing anything above run:

```bash
uv run linked-past-server reindex
```

## Procedure

### 1. Diagnose with five searches

Pick five entities a scholar would search for, using the names they would
type (a person's cognomen, a place's ancient name, a coin's issuer). Run
`search_entities(name, dataset)` for each. Note which miss, then look at the
entity with `explore_entity` to see which predicate carries the name.

### 2. Choose the fix

```
name is under a predicate not in the fixed list ->
    add that property to schemas.yaml with a pred name containing "name"/"label"/"title"
    (no code change; the indexer discovers it)

label needs a word from another dataset (issuer, findspot, period) ->
    implement extra_search_entries on the plugin

label needs a computed form from the same dataset (e.g. name without prefix) ->
    implement extra_search_entries; no registry lookup needed
```

### 3. Implement the hook

Signature on `DatasetPlugin`:

```python
def extra_search_entries(self, store: Store, registry) -> list[tuple[str, str]]:
    """Return (doc_type, text) rows. text is f"{label}\t{uri}" for entity_label."""
```

Rules: return `[]` if `registry` is `None` or `registry.get_store(other)`
raises `KeyError` (the sibling dataset may not be installed); dedupe on
`(uri, label)`; log the row count. The worked example is
`linked_past/datasets/coin_types.py`, used by `crro/plugin.py` and
`ocre/plugin.py`: it joins each coin type's `nmo:hasIssuer` to the issuer's
English `skos:prefLabel` in the Nomisma store and emits
`"RRC 366/1 — C. Annius\t<coin uri>"`.

Keep the hook's queries cheap. It runs for every entity at every reindex;
one query for the batch plus one small lookup per row is the ceiling.

### 4. Test it

Follow `tests/test_coin_types.py`: build in-memory `pyoxigraph.Store`
objects from a few lines of Turtle, wrap them in a fake registry whose
`get_store` raises `KeyError` for missing names, and assert on the exact
rows. Add a case where the sibling store is absent and expect `[]`.

### 5. Reindex and re-run the five searches

```bash
uv run linked-past-server reindex
```

Report which of the five now hit.

## Meta-entity index

`meta_entities.db` clusters the same real-world entity across datasets. It is
seeded from the curated linkage YAML and Wikidata concordances, then extended
by dataset-specific bridges; the EDH bridge in
`linked_past/core/meta_entities.py` (`_extend_with_edh`) is the current
example. A new dataset joins the meta-entity index by contributing linkage
YAML (`entity-enrichment` skill) or Wikidata concordances; adding another
bridge in `meta_entities.py` is a code change and out of this skill's scope.
`_uri_to_dataset` there uses `DatasetRegistry._URI_NAMESPACES`, so the
dataset's namespace must be registered.

## Common Mistakes

- Indexing full text fields (inscription bodies, descriptions). They drown the label matches. The indexer deliberately excludes `editionText`.
- Enriching by editing `_index_dataset` with a dataset-name check. Use the hook.
- Forgetting `reindex`; the fingerprint cache serves the old index.
- A hook that raises when a sibling dataset is missing. The server logs and continues, but the enrichment silently disappears.
````

- [ ] **Step 2: Verify layout test and commit**

Run: `uv run pytest scripts/tests/test_skill_files.py -q`
Expected: pass (six skills).

```bash
git add .claude/skills/enriching-search-index/
git commit -m "docs(skills): add enriching-search-index skill

Claude-Session: https://claude.ai/code/session_01AdwTsiDXfysqGNF1rV4498"
```

---

### Task 11: Verify the skills with subagents and close gaps

**Files:**
- Modify: any `.claude/skills/*/SKILL.md` or reference file that a check exposes as wrong or incomplete.
- Create (scratch only, not committed): synthetic fixtures under the session scratchpad directory.

**Interfaces:**
- Consumes: all five skills.

- [ ] **Step 1: Read-through check for every skill**

For each of `onboarding-dataset`, `ingesting-rdf-source`, `cleaning-rdf-dumps`, `authoring-dataset-context`, `enriching-search-index`, dispatch a subagent (general-purpose, read-only tools) with this prompt, substituting the skill name:

```
Read .claude/skills/<skill>/SKILL.md and any files it references in that
directory. A dataset named "lgpn" (Lexicon of Greek Personal Names) is being
onboarded; the source is a single RDF/XML file at
https://example.org/lgpn.rdf under CC BY 4.0. Without reading any other
repository files, list (1) every repository file this skill would have you
create or modify, with the exact path, and (2) every shell command it would
have you run, in order. Do not perform anything. Report only the two lists.
```

Compare each answer against `stage-map.md`. A file the subagent missed that
the skill should have led it to, a path it invented, or a command with the
wrong module path is a defect: fix the skill text, not the answer.

- [ ] **Step 2: Baseline pressure test, context authoring**

Write the synthetic fixture to `<scratchpad>/fake/fake.ttl`:

```turtle
@prefix fk: <http://example.org/fake/ontology#> .
@prefix fkn: <http://example.org/fake/names/> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

<http://example.org/fake/person/1> a fk:Person ;
    fkn:attestedForm "Marcus Tullius Cicero" ;
    fk:birthYear "-0106" ;
    fk:deathYear "-0043" .
<http://example.org/fake/person/2> a fk:Person ;
    fkn:attestedForm "Gaius Iulius Caesar" ;
    fk:birthYear "-0100" ;
    fk:deathYear "-0044" .
<http://example.org/fake/office/1> a fk:Office ;
    rdfs:label "consul" ;
    fk:heldBy <http://example.org/fake/person/1> ;
    fk:year "-0063" .
```

Dispatch a subagent with `isolation: "worktree"` and this prompt (no mention of skills):

```
In this repository, write the four context YAML files (prefixes, schemas,
examples, tips) and a plugin.py for a new dataset named "fake" whose data is
the Turtle file at <scratchpad>/fake/fake.ttl. Put them under
packages/linked-past/linked_past/datasets/fake/. Do not run the server or
push anything. When done, print each file.
```

Record, from the output: did it capture `fkn:attestedForm` as a label-like
property in `schemas.yaml`; did it write a tip about the zero-padded
negative-year string encoding; did every example declare its prefixes and
end with `LIMIT`; did it register the plugin anywhere. Write the
rationalizations it used (for example "dates are self-explanatory") into a
scratch note.

- [ ] **Step 3: Skill run, context authoring**

Same fixture and prompt, in a fresh worktree subagent, prefixed with:

```
Before starting, read .claude/skills/authoring-dataset-context/SKILL.md and
its reference file and follow them exactly.
```

Success criteria: `schemas.yaml` includes `fkn:attestedForm` with a value
comment; `tips.yaml` has a tip about string years with a `FILTER` example
tagged `["Person"]`; every example has inline prefixes and `LIMIT`; the
subagent attempted the verification loop or explained that the store did
not exist. Any criterion missed becomes a fix in the skill (usually a new
line in Common Mistakes or a sharper step), then re-run Step 3 once.

- [ ] **Step 4: Baseline pressure test, cleaning**

Write `<scratchpad>/broken/broken.ttl`:

```turtle
@prefix ex: <http://example.org/> .
@prefix dcterms: <http://purl.org/dc/terms/> .

ex:place1 dcterms:title "Vatl"@etruscan-in-latin-characters ;
    dcterms:references <doi.org/10.5281/zenodo.1193921> .
```

Dispatch a worktree subagent (no mention of skills):

```
The file <scratchpad>/broken/broken.ttl is a raw dump for a new dataset and
fails linked_past_store.verify_turtle. Make the pipeline produce a version
that passes strict verification. Do not push anything. Report what you
changed and where.
```

Record: did it edit the Turtle by hand; did it classify the two problems;
did it find that `sanitize_turtle` already fixes both; did it propose
putting a fix in the right file.

- [ ] **Step 5: Skill run, cleaning**

Same prompt, prefixed with:

```
Before starting, read .claude/skills/cleaning-rdf-dumps/SKILL.md and
issue-catalog.md in that directory and follow them exactly.
```

Success criteria: it runs `verify_turtle`, classifies the language tag as
Turtle-level and the DOI as IRI-level, discovers both fixes already live in
`sanitize.py` and runs `sanitize_turtle` rather than editing the file, and
does not propose a catalog row because both classes exist. Fix the skill for
any miss and re-run once.

- [ ] **Step 6: Run the full suite and commit fixes**

Run: `uv run pytest -q && uv run ruff check .`
Expected: pass.

```bash
git add .claude/skills/
git commit -m "docs(skills): tighten skills after subagent verification

Claude-Session: https://claude.ai/code/session_01AdwTsiDXfysqGNF1rV4498"
```

If no skill needed changes, skip the commit and say so in the report.
