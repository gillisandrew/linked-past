---
name: entity-enrichment
description: Use when linking persons, places, or concepts between datasets (e.g., DPRR↔Nomisma, Pleiades↔TM) or when the linkage graph needs new cross-references. Produces curated YAML linkage entries with scholarly provenance.
---

# Entity Enrichment Skill

Cross-dataset entity matching through structured evidence gathering and human-in-loop verification. Produces YAML linkage entries for the linkage graph. The worked examples are DPRR→Nomisma and DPRR→Pleiades; the phases apply to any source/target pair.

## Tools

With the MCP server running, use `query`, `search_entities(query_text=..., dataset=...)`, and `explore_entity`. Without it, the same operations from the shell:

- SPARQL: `get_read_only_store(get_data_dir() / "<dataset>" / "store").query(...)` from `linked_past.core.store`
- Search: `SearchIndex(get_data_dir() / "search.db").search("<name>", dataset="<dataset>", doc_type="entity_label")` from `linked_past.core.search`
- Explore: `SELECT ?p ?o WHERE { <uri> ?p ?o }` in the owning dataset's store; a URI with no rows does not resolve

## When to Use

- "Link DPRR persons to Nomisma" or "Find matching entities across datasets"
- "Enrich the linkage graph" or "Add cross-references"
- After loading a new dataset and wanting to connect it to existing ones
- When a user notices a missing cross-reference during exploration

## Workflow

### Phase 1: Scope

Ask the user which datasets to link and what entity type (persons, places, periods). Agree on:
- **Source dataset** (e.g., DPRR)
- **Target dataset** (e.g., Nomisma)
- **Entity slice** (e.g., moneyers, provincial governors, all persons)
- **Relationship type** (e.g., `skos:closeMatch` for same-person-different-facet, `owl:sameAs` for identity)

### Phase 1b: Does the source already publish the links?

Before generating candidates, query the source store for `skos:exactMatch`, `skos:closeMatch`, or `owl:sameAs` objects in the target's namespace:

```sparql
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
SELECT ?s ?p ?o WHERE { ?s ?p ?o . FILTER(?p IN (skos:exactMatch, skos:closeMatch, <http://www.w3.org/2002/07/owl#sameAs>)) FILTER(STRSTARTS(STR(?o), "<target namespace>")) }
```

If it does:
- `find_links` and `explore_entity` already surface those at query time; no YAML is needed for browsing.
- Write a YAML file only to feed the meta-entity index (it seeds from linkage YAML and Wikidata concordances, not from store triples) or to record that each link was verified. Use `method: upstream_assertion`, name the upstream file and date in `basis`, and skip Phases 2–5: the candidate list is the upstream link set and verification is one resolve check per target (Phase 7).

### Phase 2: Candidate Generation

Query the source dataset for entities likely to have matches in the target. Select the entity class with its label and any dating or reference predicates; the two queries below are the DPRR-specific instances of that pattern.

**For DPRR→Nomisma persons (moneyers):**
```sparql
PREFIX vocab: <http://romanrepublic.ac.uk/rdf/ontology#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT DISTINCT ?person ?name ?officeLabel ?date ?source WHERE {
  ?pa vocab:isAboutPerson ?person ;
      vocab:hasOffice ?office ;
      vocab:hasDateStart ?date .
  ?office rdfs:label ?officeLabel .
  ?person vocab:hasPersonName ?name .
  FILTER(REGEX(?officeLabel, "moneyer|monetalis|IIIvir|tresvir", "i"))
  OPTIONAL { ?pa vocab:hasSecondarySource ?src . ?src rdfs:label ?source }
}
ORDER BY ?date
```

**For DPRR→Pleiades places (provinces):**
```sparql
PREFIX vocab: <http://romanrepublic.ac.uk/rdf/ontology#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT DISTINCT ?province ?label WHERE {
  ?province a vocab:Province ; rdfs:label ?label .
}
ORDER BY ?label
```

### Phase 3: Match Search

For each candidate, search the target dataset using `search_entities`:

```
search_entities(query_text="{person_name}", dataset="{target_dataset}")
```

If no results, try variations:
- Nomen only (e.g., "Annius" instead of "C. Annius T.f. T.n. Luscus")
- Cognomen (e.g., "Brutus")
- Known numismatic attribution name

### Phase 4: Evidence Assembly

For each candidate pair, gather evidence using `explore_entity` on both URIs:

```
explore_entity("{source_uri}")
explore_entity("{target_uri}")
```

Document:
- **Name match:** Do the names refer to the same person?
- **Date overlap:** Do active periods align?
- **Shared references:** Do both cite the same RRC number, Broughton MRR entry, or other source?
- **Role consistency:** Is the DPRR office consistent with the Nomisma authority role?

### Phase 5: Present Batch for Review

Present candidates as a markdown table:

```markdown
| # | DPRR Person | Nomisma Match | Confidence | Evidence |
|---|-------------|---------------|------------|----------|
| 1 | Person/1740 (C. Annius) | nm:c_annius | confirmed | RRC 366; DPRR moneyer 82 BC |
| 2 | Person/XXXX (Name) | nm:id | probable | Name + date match; no RRC citation |
| 3 | Person/YYYY (Name) | ❌ no match | — | No Nomisma entity found |
```

**Confidence criteria:**
- **confirmed** — DPRR cites RRC for a moneyer post AND the Nomisma URI is the RRC authority for the same person
- **probable** — Strong name + date match but no direct RRC citation chain, or Nomisma URI covers a broader identity

Wait for user to accept/reject/adjust each row.

### Phase 6: Write YAML

For accepted links, append to `linked_past/linkages/<source>_<target>.yaml`. Every `*.yaml` in that directory is loaded, and `metadata.confidence` is the default for its links. Add a `_<confidence>` suffix only when one pair is split across confidence levels, as `dprr_nomisma_confirmed.yaml` and `dprr_nomisma_probable.yaml` are; single-confidence pairs use the bare name (`dprr_pleiades.yaml`, `kerameikos_pleiades.yaml`).

A new file starts with this metadata block:

```yaml
metadata:
  source_dataset: <source>
  target_dataset: <target>
  relationship: "skos:closeMatch"
  confidence: confirmed
  method: manual_alignment        # or upstream_assertion, automated_name_matching
  basis: "<what the evidence was, with edition or file and date>"
  author: linked-past project
  date: "<YYYY-MM-DD>"
links:
```

For `upstream_assertion`, set `relationship` to the predicate upstream actually asserted (`skos:exactMatch` if that is what the source publishes); do not downgrade or upgrade it.

Pleiades targets use the `#this` form, `https://pleiades.stoa.org/places/<id>#this`: that is the Place subject in the store, and the bare URI is the document about it. Other datasets use the entity URI exactly as it appears as a subject in their store.

Use this format per link:
```yaml
  - source: "http://romanrepublic.ac.uk/rdf/entity/Person/{ID}"
    target: "http://nomisma.org/id/{nomisma_id}"
    note: "{one-line evidence summary}"
```

If a link has different confidence than the file default, either:
- Put it in the other file, or
- Add `confidence: probable` to the link entry (per-link override is supported)

### Phase 7: Verify and Commit

1. Verify each target URI exists: `explore_entity("{target_uri}")`, or the store lookup from the Tools section
2. Drop links where the target doesn't resolve
3. Run `uv run pytest packages/linked-past/tests/test_linkage.py -q`
4. Do not commit unless the user asks. Propose the message: `feat: add {N} {source}↔{target} cross-links ({slice})`, listing rejected candidates so they aren't re-proposed.

## Batch Size

Process 10-20 candidates per batch. Larger batches lose context. If the candidate set is large (100+), slice by:
- Date range (e.g., "moneyers 150-100 BC")
- Office type (e.g., "all tresviri monetales")
- Province (e.g., "Hispanic mint authorities")

## Output Artifacts

- YAML linkage entries in `linked_past/linkages/`
- A proposed commit message with provenance (committed only on request)
- Links available in the server on next restart (or hot-reload if implemented)

## Anti-Patterns

- **Don't guess URIs** — always verify with `search_entities`, `explore_entity`, or a store lookup
- **Don't re-derive links the source already publishes** — Phase 1b: upstream `exactMatch` sets are the candidate list, not a starting point for name matching
- **Don't assume name = match** — Roman naming is ambiguous; multiple persons share names
- **Don't skip evidence gathering** — even "obvious" matches need documented basis
- **Don't batch too large** — human review quality drops after ~20 candidates
