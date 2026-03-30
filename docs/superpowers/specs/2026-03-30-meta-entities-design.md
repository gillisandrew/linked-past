# Meta-Entity Layer: Unified Entity Resolution for Cross-Dataset NER

**Date:** 2026-03-30
**Status:** Draft

## Problem

An AI agent asking "tell me about Caesar's campaigns in Gaul" needs to find Caesar across DPRR (Person/1957), Nomisma (nm:julius_caesar), Wikidata (Q1048), EDH (37+ inscription attestations), and CRRO (authority on RRC 443-480). Currently the agent must manually chain `search_entities` → `find_links` → `explore_entity` across datasets. There's no single lookup that returns "here's everything we know about this person across all datasets."

## Goal

A meta-entity layer that:
1. Clusters URIs across datasets that refer to the same real-world entity
2. Generates a rich text description from all sources for each cluster
3. Embeds those descriptions for semantic search
4. Resolves natural language mentions to specific URIs in specific datasets

## Non-Goals

- Automated entity matching / reconciliation (clusters are built from existing confirmed links)
- Replacing `search_entities` SPARQL label search (meta-entities augment it, don't replace it)
- Persons only for v1 (places and periods could follow the same pattern later)

---

## Design

### Meta-Entity Schema

```python
@dataclass
class MetaEntity:
    id: str                          # Stable ID, e.g., "person:julius_caesar"
    canonical_name: str              # "Gaius Julius Caesar"
    entity_type: str                 # "person", "place", "period"
    description: str                 # Rich text for embedding (see below)
    date_range: str | None           # "100-44 BC"
    uris: dict[str, list[str]]       # {dataset_name: [uri1, uri2, ...]}
    wikidata_qid: str | None         # "Q1048"
```

### Description Generation

The description is what gets embedded. It should be a dense, natural-language paragraph combining key facts from all sources:

```
Gaius Julius Caesar (100-44 BC). Roman dictator, consul 59 BC,
pontifex maximus 63 BC. Moneyer 49-44 BC (DPRR). Coin authority
for RRC 443-480, denarii and aurei minted at Rome and field mints
(CRRO/Nomisma). Mentioned in 37 inscriptions across the Roman
Empire (EDH). Wikidata Q1048.
```

For less famous figures:

```
C. Antestius (fl. 146 BC). Roman Republican monetalis 146 BC (DPRR).
Nomisma coin authority c_antesti_rrc, RRC moneyer c. 146 BC.
British Museum person 175171.
```

### Cluster Construction

Built at startup from three sources, in order:

**1. Curated linkage graph** (highest confidence)
- Walk DPRR↔Nomisma confirmed links
- Each link defines a cluster seed: {dprr: [Person/X], nomisma: [nm:Y]}

**2. Nomisma→Wikidata bridges** (extend clusters)
- For each Nomisma URI in a cluster, query the Nomisma store for `skos:exactMatch` to Wikidata
- Add the QID to the cluster

**3. EDH→Wikidata bridges** (extend clusters further)
- For each Wikidata QID in a cluster, query EDH for persons with `skos:sameAs` matching that QID
- Add all matching EDH person URIs to the cluster

**4. Pleiades bridges** (for place entities, future)
- EDH places → Pleiades via `skos:closeMatch`
- DPRR provinces → Pleiades via curated linkage

### Description Assembly

For each cluster, pull key properties from each dataset:

| Dataset | Properties to extract |
|---------|----------------------|
| DPRR | hasPersonName, hasNomen, hasCognomen, hasEraFrom/To, hasHighestOffice |
| Nomisma | skos:definition, skos:prefLabel |
| EDH | COUNT of attestations (inscriptions mentioning this person) |
| CRRO | COUNT of coin types where this person is authority |
| Wikidata | QID (for external reference) |

Concatenate into a natural-language description paragraph.

### Storage

Meta-entities are stored in the existing `EmbeddingIndex` (SQLite) with `doc_type = "meta_entity"`:

```
documents table:
  id: 1
  dataset: "_meta"          # Special dataset name for meta-entities
  doc_type: "meta_entity"
  text: "Gaius Julius Caesar (100-44 BC). Roman dictator..."
  embedding: [0.23, -0.41, ...] (384-dim BLOB)
```

A separate `meta_entities` table stores the structured data:

```sql
CREATE TABLE meta_entities (
    id TEXT PRIMARY KEY,           -- "person:julius_caesar"
    canonical_name TEXT,
    entity_type TEXT,
    description TEXT,
    date_range TEXT,
    uris_json TEXT,                -- JSON: {"dprr": [...], "nomisma": [...], ...}
    wikidata_qid TEXT
);
```

### Search Flow

```
Agent: "Who governed Sicily during Caesar's dictatorship?"
                    │
                    ▼
         search_entities("Caesar")
                    │
         ┌──────────┴──────────┐
         ▼                     ▼
  Meta-entity search     SPARQL label search
  (semantic, fast)       (exact match, per-store)
         │                     │
         ▼                     ▼
  MetaEntity{                 [{uri, label, dataset}, ...]
    "person:julius_caesar"
    uris: {
      dprr: [Person/1957],
      nomisma: [nm:julius_caesar],
      edh: [person/HD019396/1, ...],
      crro: [(authority on 38 types)]
    }
  }
         │
         └──── Merged results ────→ Agent picks the right URIs
```

### Integration Points

**`search_entities` enhancement:**
- First: search meta-entity embeddings (semantic similarity)
- Then: fall back to SPARQL label search across stores (exact/substring)
- Merge results, meta-entities first (they have richer context)
- Return format includes all URIs grouped by dataset

**`explore_entity` enhancement:**
- When exploring a URI, check if it belongs to a meta-entity cluster
- If so, show the full cluster: "This entity is also known as..."
- List all dataset URIs in the cluster

**`find_links` — no change needed:**
- Already discovers store xrefs and curated links
- Meta-entities are an indexing/search layer, not a linkage layer

### Build Lifecycle

```
Server startup
  ├── Initialize dataset stores (existing)
  ├── Load linkage graph (existing)
  ├── Build meta-entity clusters (NEW)
  │   ├── Walk curated linkage graph for seed clusters
  │   ├── Extend via Nomisma→Wikidata store xrefs
  │   ├── Extend via EDH→Wikidata store xrefs
  │   └── For each cluster:
  │       ├── Pull description properties from each dataset store
  │       ├── Assemble description text
  │       └── Store in SQLite meta_entities table
  ├── Build embedding index (existing, now includes meta-entities)
  └── Ready
```

Rebuild triggers:
- On `update_dataset` (new data may create new clusters or change descriptions)
- On linkage YAML changes (new curated links create new clusters)

---

## Scope

### v1 (this implementation)

- Person meta-entities only
- Clusters from: DPRR↔Nomisma curated links + Nomisma→Wikidata + EDH→Wikidata
- Description from: DPRR name/dates/office + Nomisma definition + EDH attestation count
- Semantic search via existing fastembed infrastructure
- Enhances `search_entities` return format

### Future

- Place meta-entities (Pleiades hub, EDH findspots, DPRR provinces)
- Period meta-entities (PeriodO definitions linked to DPRR date ranges)
- Auto-clustering from store xrefs without curated seeds
- Description enrichment from Wikidata API (fetch abstracts)

---

## File Structure

```
linked_past/
├── core/
│   ├── meta_entities.py    # MetaEntity dataclass, cluster builder, description assembler
│   ├── embeddings.py       # (modify: add meta_entities table, search returns MetaEntity)
│   ├── server.py           # (modify: build meta-entities at startup, enhance search_entities)
```

## Estimated Size

- `meta_entities.py`: ~200-250 lines
- Modifications to `embeddings.py`: ~30 lines (new table, query method)
- Modifications to `server.py`: ~50 lines (build step, search_entities enhancement)
- Tests: ~100 lines
- **Total: ~400 lines of new/modified code**

## Expected Output

For the 187 DPRR↔Nomisma confirmed links, we'd get ~187 person meta-entities (some may merge if multiple DPRR persons link to the same Nomisma person). Each with:
- Canonical name from DPRR
- Date range from DPRR
- Nomisma definition
- Wikidata QID (where Nomisma has one)
- EDH attestation count (where Wikidata bridges to EDH)
- A 384-dim embedding of the assembled description

Search for "the general who crossed the Rubicon" would return Caesar's meta-entity with all his URIs across all 4+ datasets.
