# Dataset Onboarding Skills Design

Date: 2026-09-04
Status: Approved

## Goal

Teach an agent to do what was done by hand for the eight current datasets:
take an upstream scholarly RDF source, get it through ingest, cleaning,
validation, plugin and context authoring, search indexing, and linking, and
leave the repository in a state where tests, lint, and docs are all current.

The deliverable is a set of project-scoped Claude Code skills under
`.claude/skills/`, one small plugin hook so that search-index enrichment no
longer requires editing core server code, and a few doc corrections.

## Background

Onboarding a dataset today touches these places, in order:

1. `datasets.yaml` entry (refs, license, citation, threshold, source URL).
2. An ingest script under `scripts/` (generic for RDF/XML and JSON-LD,
   bespoke for tarballs, SPARQL endpoints, N3) and optionally a scheduled
   GitHub workflow. Output is a raw Turtle artifact on the OCI registry.
3. `scripts/clean_dataset.py` and `scripts/validate_dataset.py`, driven by the
   sanitize routines in `linked-past-store`. Upstream breakage is fixed at the
   ingest stage when it is source-format specific and at the clean stage when
   it is generic. `docs/data-lifecycle.md` records every class of breakage met
   so far.
4. A plugin package under `packages/linked-past/linked_past/datasets/{name}/`
   with `plugin.py` and four YAML files in `context/`: `prefixes.yaml`,
   `schemas.yaml`, `examples.yaml`, `tips.yaml`. These are what the model reads
   to build queries.
5. Search indexing. Entity labels are indexed automatically from a fixed set of
   label predicates plus any schema property whose name contains `name`,
   `label`, or `title`. Datasets whose labels are meaningless without context
   (coin types in CRRO and OCRE) get enriched rows from a hardcoded branch in
   `linked_past/core/server.py`.
6. Cross-dataset links via the existing `entity-enrichment` skill and the
   YAML files in `linked_past/linkages/`.
7. Tests: the `patched_app_context` fixture in
   `packages/linked-past/tests/conftest.py` holds a hardcoded map of plugin
   classes, so a new dataset must be added there. The parametrized checks in
   `tests/test_plugins.py` cover attributes, prefixes, schema, validation, and
   load for every plugin.
8. Docs: README dataset list and tool counts, the data-lifecycle catalog when a
   new breakage class is found.

Two existing problems are fixed as part of this work:

- The existing skill file is `.claude/skills/entity-enrichment/entity-enrichment.md`.
  Claude Code looks for `SKILL.md`, so the skill is not being loaded.
- `CLAUDE.md` says three test files need fetch patches for a new plugin. That
  is stale: the single conftest fixture is the only place.

## Skills

All skills follow the superpowers `writing-skills` conventions: YAML
frontmatter with `name` and a `description` that starts with "Use when" and
states only triggering conditions; an Overview; When to Use; the procedure;
common mistakes; a closing checklist. Heavy reference material goes in a
sibling file in the same skill folder. Skills point at repository files rather
than duplicating their content, and cite `docs/data-lifecycle.md` as the
canonical issue catalog.

### onboarding-dataset (orchestrator)

Trigger: "add dataset X", "onboard a new source", "we want Y in linked-past".

Contents:

- Preflight questions the agent must settle with the user before touching
  files: dataset short name, license and whether it permits redistribution,
  citation in BibTeX, source URL and format, expected size, whether the source
  is versioned or a rolling dump.
- Stage sequence with the skill to invoke for each stage and the artifact
  that marks the stage done:
  1. `ingesting-rdf-source` produces a raw OCI artifact and a `datasets.yaml`
     entry.
  2. `cleaning-rdf-dumps` produces a clean OCI artifact that passes strict
     verification and the triple-count threshold.
  3. `authoring-dataset-context` produces the plugin package with all four
     YAML files, and every example runs against the local store.
  4. `enriching-search-index` is conditional: run only if `search_entities`
     cannot find representative entities by the names a scholar would use.
  5. `entity-enrichment` is conditional: run when the dataset shares entities
     with an existing one.
- Definition of done: conftest map updated, `uv run pytest` and
  `uv run ruff check .` pass, README dataset table updated, data-lifecycle
  catalog updated if a new breakage class appeared, and the Clean Datasets
  workflow's dataset choice list includes the new name.
- Reference file `stage-map.md`: a table of every file touched during
  onboarding, grouped by stage, with the current examples for each (which
  script, which plugin) so the agent can copy the closest match.

### ingesting-rdf-source

Trigger: writing or changing an ingest script, adding a `datasets.yaml`
entry, pushing a raw artifact, setting up a scheduled ingest workflow.

Contents:

- Decision procedure for the ingest path: generic script when the source is a
  single RDF/XML or JSON-LD URL; bespoke script when the source is a tarball,
  a SPARQL endpoint, an N3 dump, or needs authentication or paging; scheduled
  workflow when upstream publishes on a cadence.
- `datasets.yaml` field reference and which fields the generic script requires.
- How to run an ingest locally without pushing (dry run to a temp directory,
  inspect triple counts and a sample of subjects), and how to push to the raw
  ref once satisfied. Pushing is an external side effect and requires the
  user's confirmation.
- Rule: ingest owns source-format-specific fixes only. Anything that would
  apply to any Turtle file belongs in the clean stage.
- Reference file `source-recipes.md`: one recipe per source shape drawn from
  the existing scripts. RDF/XML with HTML entity injection and IRI rewrite
  (`ingest_generic.py`), JSON-LD via rdflib, N3 to Turtle
  (`convert_n3_to_ttl.py`), multi-file tarball concatenation
  (`ingest_pleiades.py` and its workflow), SPARQL endpoint extraction
  (`extract_from_endpoint.py`, `ingest_edh.py`), and blocked user agents.

Out of scope: non-RDF sources that need an ontology designed. The skill says
so and stops there.

### cleaning-rdf-dumps

Trigger: strict parse fails, `validate_dataset` fails, triple count is under
threshold, schema diff shows unexpected churn, or a new dataset is being
cleaned for the first time.

Contents:

- Triage procedure. Reproduce with a strict pyoxigraph parse, capture the
  first error with its line, and classify it into one of four levels: XML
  (breaks the XML parser), IRI (valid XML, invalid IRI), Turtle (valid RDF/XML,
  breaks a strict Turtle parser), semantic (parses, wrong triples).
- Placement rule: fix at the earliest stage that owns the quirk. XML and
  source-specific IRI issues go in the ingest script; generic Turtle issues go
  in the store package's sanitize step; semantic issues usually go in schema
  YAML or the materialization code. Never hand-edit a Turtle artifact.
- Loop: fix, re-run clean and validate, count how many occurrences the fix
  touched, and record the count so it can be checked on the next upstream
  release.
- Setting `min_triple_count` at roughly ninety percent of the observed count
  so a broken upstream release fails loudly, and reading the schema diff.
- Requirement to add any new breakage class to the catalog in
  `docs/data-lifecycle.md` in the same change.
- Reference file `issue-catalog.md`: the existing catalog reorganised by
  symptom (what the parser error looks like) leading to the fix and the file
  where that fix already lives.

### authoring-dataset-context

Trigger: creating a plugin package, writing or improving any of the four
context YAML files, a user reports the model writing bad queries for a
dataset, or `get_schema` output is thin for a dataset.

Contents:

- Plugin class checklist: the attributes the parametrized plugin tests
  require, when to override `get_version_info`, and that `fetch` and `load`
  should not be overridden without a reason.
- Deriving `schemas.yaml` from `_schema.yaml` and `_void.ttl`. Hand-write only
  the classes a scholar would ask about; leave long-tail classes to the auto
  schema merge. Each property gets a range and a comment that says what the
  values actually look like, not what the ontology says they should.
- `prefixes.yaml` rules: verify each namespace against the data with a query,
  since upstream ontologies drift (the EDH LAWD 1.0 case).
- What makes a good example: phrased as the question a user would ask, one
  concept per example, uses only prefixes declared inline, always has a
  `LIMIT`, and together the examples cover every hand-written class.
- What makes a good tip: a fact that would otherwise cost the model a failed
  query. Date encoding, label language tags, predicates that look like one
  ontology but are another, coverage gaps in the data. Tips are tagged with
  the classes they apply to so the validator surfaces them.
- Verification loop: execute every example against the local store and
  require a non-empty result, run the plugin tests, then ask the server's
  `validate_sparql` for a deliberately wrong query and confirm the tips come
  back.
- Reference file `context-yaml-reference.md`: the exact field set for each
  YAML file, a skeleton plugin, and a skeleton of each YAML file.

### enriching-search-index

Trigger: `search_entities` cannot find entities by the names a scholar would
use, a dataset's labels are codes or catalogue numbers, or a dataset should
contribute to the meta-entity index.

Contents:

- How indexing works: the fixed label predicates, the schema-driven predicate
  discovery, SKOS concept indexing, the fingerprint cache and when to run
  `reindex`.
- Diagnosis: pick five entities a scholar would search for, search for them,
  and note which fail. If the failure is a missing predicate, fix it in
  `schemas.yaml` by naming the property so the discovery rule picks it up. If
  the failure is that the label needs context from another dataset, implement
  the plugin hook.
- The plugin hook: signature, the row format, the requirement to tolerate a
  missing sibling dataset, and how to test it with a small fixture.
- Meta-entity index: where the linkage graph and Wikidata concordances feed
  it, and the EDH-specific extension in `meta_entities.py` as the current
  example of a per-dataset bridge. That code is documented, not refactored.

### entity-enrichment (existing)

Rename `entity-enrichment.md` to `SKILL.md`. No content changes beyond
fixing the frontmatter if needed.

## Plugin hook

Add to `DatasetPlugin` in `packages/linked-past/linked_past/datasets/base.py`:

```python
def extra_search_entries(self, store: Store, registry) -> list[tuple[str, str]]:
    """Return additional (doc_type, text) rows for the search index.

    Called after automatic label indexing. Rows use the same text format
    as entity labels: "label\turi". Return [] when nothing to add. Must
    tolerate sibling datasets being uninitialised (registry.get_store
    raises KeyError).
    """
    return []
```

`_index_dataset` in `server.py` calls the hook after label indexing and
before SKOS indexing, batches the rows through `search.add_batch`, and logs
the count. Exceptions from the hook are logged as warnings, matching the
existing behaviour for the coin branch.

The coin issuer enrichment moves to a helper,
`linked_past/datasets/coin_types.py`, exposing
`issuer_enriched_labels(dataset, store, registry) -> list[tuple[str, str]]`.
`CRROPlugin` and `OCREPlugin` implement `extra_search_entries` by calling it.
The hardcoded `if name in ("crro", "ocre")` branch is deleted.

Tests:

- `tests/test_base_plugin.py`: default hook returns an empty list.
- `tests/test_plugins.py` or a new `tests/test_coin_types.py`: a two-store
  fixture (a CRRO store with one type series item pointing at an issuer, a
  Nomisma store with that issuer's English preferred label) yields one row
  containing both the coin label and the issuer name. A second case with
  Nomisma absent yields an empty list and no exception.
- `tests/test_search.py` or `tests/test_server.py`: `_index_dataset` includes
  rows returned by a stub plugin's hook.

## Docs and corrections

- `CLAUDE.md`: replace the three-test-file note with the conftest fixture
  note. Add a short section listing the skills and that `onboarding-dataset`
  is the entry point.
- `docs/data-lifecycle.md`: no content changes. Skills link to it.
- `README.md`: no change unless the plugin hook changes tool counts, which it
  does not.

## Testing the skills

Each skill is checked two ways.

Read-through: a subagent is given the skill and asked to list the files it
would touch and the commands it would run for a named hypothetical dataset.
The answer is compared against `stage-map.md`. Any file the subagent misses
or invents is a defect in the skill.

Pressure test, for `authoring-dataset-context` and `cleaning-rdf-dumps`
only: a subagent is run twice on the same scenario in a scratch copy of the
repository, once without the skill and once with it, and the rationalizations
it uses in the baseline run are recorded and addressed in the skill. Scenarios:

- Context: given a small synthetic Turtle file with a date property stored as
  zero-padded strings and a label predicate under a non-obvious namespace,
  write the four YAML files. The baseline is expected to skip the date tip and
  miss the label predicate.
- Cleaning: given a Turtle file with an over-long language subtag and a bare
  DOI IRI, get it to pass strict verification. The baseline is expected to
  hand-edit the file or patch the wrong stage.

Nothing in these tests pushes to the OCI registry.

## Out of scope

- Non-RDF sources needing an ontology design.
- Refactoring the EDH branch in `meta_entities.py` into a hook.
- Changing the search index schema or the fingerprint logic.
- Rewriting the existing entity-enrichment skill.

## Files

New:

- `.claude/skills/onboarding-dataset/SKILL.md`, `stage-map.md`
- `.claude/skills/ingesting-rdf-source/SKILL.md`, `source-recipes.md`
- `.claude/skills/cleaning-rdf-dumps/SKILL.md`, `issue-catalog.md`
- `.claude/skills/authoring-dataset-context/SKILL.md`, `context-yaml-reference.md`
- `.claude/skills/enriching-search-index/SKILL.md`
- `packages/linked-past/linked_past/datasets/coin_types.py`
- tests as listed above

Changed:

- `.claude/skills/entity-enrichment/entity-enrichment.md` renamed to `SKILL.md`
- `packages/linked-past/linked_past/datasets/base.py`
- `packages/linked-past/linked_past/datasets/crro/plugin.py`
- `packages/linked-past/linked_past/datasets/ocre/plugin.py`
- `packages/linked-past/linked_past/core/server.py`
- `CLAUDE.md`
