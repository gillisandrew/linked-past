---
name: entity-enrichment
description: Cross-dataset entity matching workflow. Use when linking persons, places, or concepts between datasets (e.g., DPRR↔Nomisma, Pleiades↔TM). Produces curated YAML linkage entries with scholarly provenance.
---

# Entity Enrichment Skill

Cross-dataset entity matching through structured evidence gathering and human-in-loop verification. Produces YAML linkage entries for the linkage graph.

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

### Phase 2: Candidate Generation

Query the source dataset for entities likely to have matches in the target. Use the `query` MCP tool.

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
search_entities("{person_name}", "{target_dataset}")
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

For accepted links, append to the appropriate YAML file:
- `linked_past/linkages/dprr_nomisma_confirmed.yaml` for confirmed
- `linked_past/linkages/dprr_nomisma_probable.yaml` for probable

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

1. Verify each target URI exists: `explore_entity("{target_uri}")`
2. Drop links where the target doesn't resolve
3. Commit: `git commit -m "feat: add {N} DPRR↔{target} cross-links ({slice})"`

Note rejected candidates in the commit message or a comment so they aren't re-proposed.

## Batch Size

Process 10-20 candidates per batch. Larger batches lose context. If the candidate set is large (100+), slice by:
- Date range (e.g., "moneyers 150-100 BC")
- Office type (e.g., "all tresviri monetales")
- Province (e.g., "Hispanic mint authorities")

## Output Artifacts

- YAML linkage entries in `linked_past/linkages/`
- Git commit with provenance in the message
- Links available in the server on next restart (or hot-reload if implemented)

## Anti-Patterns

- **Don't guess URIs** — always verify with `search_entities` or `explore_entity`
- **Don't assume name = match** — Roman naming is ambiguous; multiple persons share names
- **Don't skip evidence gathering** — even "obvious" matches need documented basis
- **Don't batch too large** — human review quality drops after ~20 candidates
