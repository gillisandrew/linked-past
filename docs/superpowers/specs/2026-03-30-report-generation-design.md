# Report Generation: Query Provenance and Research Reports

**Date:** 2026-03-30
**Status:** Draft

## Problem

When a scholar uses the MCP tools to research a question, the conversation produces valuable artifacts — SPARQL queries, result tables, cross-references, provenance chains — but these are trapped in the chat transcript. There's no structured way to:

1. Reproduce the research (which queries produced which results?)
2. Share findings with colleagues who don't have the MCP server
3. Cite the exact data and queries used
4. Build on prior sessions without re-running everything

## Goals

Three levels of report generation, each building on the previous:

### Level 1: Query Provenance Log

Machine-readable audit trail of every tool call in a research session. Captures queries, results, datasets, versions, and timestamps. Exportable as JSON or Markdown.

### Level 2: Research Report

Synthesized narrative document with embedded citations, entity references, and cross-dataset links. Produced by an AI agent from the provenance log + user direction. Exportable as Markdown, with scholarly citation format.

### Level 3: Interactive Publication (future)

MDX/React components that render entity cards, linkage graphs, and queryable tables inline. A reader clicks "Caesar" and sees his full cross-dataset profile. Out of scope for this spec — separate project.

## Non-Goals

- Real-time collaborative editing
- Full publication pipeline (LaTeX, PDF, journal formatting)
- Replacing the conversation — reports augment, not replace

---

## Level 1: Query Provenance Log

### What Gets Captured

Every MCP tool call produces a log entry:

```json
{
  "id": "entry_001",
  "timestamp": "2026-03-30T21:15:00Z",
  "tool": "query",
  "inputs": {
    "sparql": "PREFIX vocab: ...\nSELECT ?person ?name WHERE { ... }",
    "dataset": "dprr",
    "timeout": null
  },
  "outputs": {
    "row_count": 25,
    "rows": [...],
    "see_also": [
      {"uri": "http://romanrepublic.ac.uk/rdf/entity/Person/1957", "target": "http://nomisma.org/id/julius_caesar", "confidence": "confirmed"}
    ]
  },
  "dataset_version": {
    "dataset": "dprr",
    "version": "1.3.0",
    "triple_count": 654125,
    "digest": "sha256:2aeecdfd3d99..."
  },
  "duration_ms": 142
}
```

### Log Entries by Tool

| Tool | What's logged |
|---|---|
| `query` | SPARQL, dataset, results, see-also links, dataset version+digest |
| `validate_sparql` | SPARQL, dataset, valid/invalid, errors, prefix repairs |
| `search_entities` | Query text, dataset filter, matching URIs |
| `explore_entity` | URI, properties returned, cross-links found |
| `find_links` | URI, links (curated + in-data), confidence levels |
| `get_provenance` | URI, predicate, provenance chain, secondary sources |
| `get_schema` | Dataset, schema returned |
| `discover_datasets` | Topic, matched datasets |

### Storage

The log accumulates in memory during the server's lifespan. It's an append-only list in `AppContext`:

```python
@dataclass
class AppContext:
    registry: DatasetRegistry
    linkage: LinkageGraph | None = None
    embeddings: EmbeddingIndex | None = None
    session_log: list[dict] = field(default_factory=list)
```

Each tool call appends to `session_log` before returning.

### Export

A new MCP tool: `export_report`

```
export_report(format: "json" | "markdown" | "provenance", path?: str) → str
```

**format="json":** Full structured log as JSON array.

**format="provenance":** Minimal provenance — just queries, datasets, versions, digests. Suitable for "Methods" section of a paper:

```markdown
## Data Sources and Queries

All queries executed against locally cached RDF datasets distributed
via OCI (ghcr.io/gillisandrew/linked-past/).

| # | Dataset | Version | Digest | Query | Results |
|---|---------|---------|--------|-------|---------|
| 1 | DPRR | 1.3.0 | sha256:2aee... | `SELECT ?person ...` | 25 rows |
| 2 | Nomisma | latest | sha256:5655... | `SELECT ?mint ...` | 12 rows |

Cross-references discovered via curated linkage graph (193 confirmed
DPRR↔Nomisma links) and in-data SKOS/OWL predicates.
```

**format="markdown":** Full report with sections, tables, citations:

```markdown
# Research Session: Moneyers of the Late Republic

**Generated:** 2026-03-30T21:30:00Z
**Datasets:** DPRR v1.3.0, Nomisma (latest), CRRO (latest)

## Queries Executed

### Query 1: DPRR Moneyers 150-100 BC

```sparql
PREFIX vocab: <http://romanrepublic.ac.uk/rdf/ontology#>
...
```

**Dataset:** DPRR v1.3.0 (sha256:2aee...)
**Results:** 25 persons

| Person | Name | Office | Date |
|--------|------|--------|------|
| Person/3502 | C. Iunius C.f. | monetalis | 149 BC |
| ... | ... | ... | ... |

### Cross-References Discovered

| DPRR Person | Nomisma Match | Confidence |
|-------------|---------------|------------|
| Person/3502 → nm:c_ivni_or_c_ivni_c_f_rrc | confirmed |
| ... | ... | ... |

## Sources

- DPRR: Mouritsen et al., romanrepublic.ac.uk. CC BY-NC 4.0.
  OCI: ghcr.io/gillisandrew/linked-past/dprr@sha256:2aee...
- Nomisma: Gruber & Meadows, nomisma.org. CC BY 4.0.
  OCI: ghcr.io/gillisandrew/linked-past/nomisma@sha256:5655...
```

### Implementation

**Logging middleware:** A wrapper around each tool function that captures inputs/outputs:

```python
def _log_tool_call(app: AppContext, tool_name: str, inputs: dict, outputs: dict, duration_ms: int):
    """Append a tool call to the session log."""
    entry = {
        "id": f"entry_{len(app.session_log) + 1:03d}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tool": tool_name,
        "inputs": inputs,
        "outputs": outputs,
        "duration_ms": duration_ms,
    }
    # Add dataset version info if a dataset was queried
    dataset = inputs.get("dataset")
    if dataset:
        meta = app.registry.get_metadata(dataset)
        if meta:
            entry["dataset_version"] = meta
    app.session_log.append(entry)
```

This wraps each tool — minimal intrusion into existing code.

**Export tool:**

```python
@mcp.tool()
def export_report(ctx: Context, format: str = "markdown", path: str | None = None) -> str:
    """Export the current session's queries and results as a report."""
    app: AppContext = ctx.request_context.lifespan_context

    if format == "json":
        content = json.dumps(app.session_log, indent=2)
    elif format == "provenance":
        content = _render_provenance(app.session_log, app.registry)
    elif format == "markdown":
        content = _render_markdown_report(app.session_log, app.registry)

    if path:
        Path(path).write_text(content)
        return f"Report written to {path}"
    return content
```

---

## Level 2: Research Report

### What It Adds

Level 1 is a raw log. Level 2 is a **synthesized narrative** — the AI agent reads the log and produces a scholarly document. This doesn't require new infrastructure; it's a prompt pattern:

1. Agent conducts research using MCP tools (Level 1 logs everything)
2. Agent calls `export_report(format="json")` to get the raw log
3. Agent synthesizes a narrative from the log + its conversation context
4. Agent formats with proper citations, entity references, and cross-references

### Entity References

In the markdown output, entity URIs become structured references:

```markdown
[C. Julius Caesar](dprr:Person/1957) held the office of
[moneyer](dprr:Office/monetalis) in 49-44 BC, as attested by
[Broughton, MRR II](dprr:SecondarySource/broughton_mrr_ii).
His coinage is catalogued as [RRC 443-480](crro:rrc-443.1) in the
CRRO type corpus, linking him to the Nomisma authority record
[nm:julius_caesar](nomisma:julius_caesar).
```

These references are resolvable — the MCP tools can expand any of them via `explore_entity`.

### Citation Format

Each dataset citation includes the OCI digest for reproducibility:

```
DPRR v1.3.0 (ghcr.io/gillisandrew/linked-past/dprr@sha256:2aee...).
Accessed 2026-03-30. CC BY-NC 4.0.
```

### Session Metadata

The report header includes:

```yaml
title: "Moneyers of the Late Republic: A Cross-Dataset Analysis"
author: "Generated by linked-past MCP server"
date: "2026-03-30"
datasets:
  - name: dprr
    version: "1.3.0"
    digest: "sha256:2aee..."
    license: "CC BY-NC 4.0"
  - name: nomisma
    version: "latest"
    digest: "sha256:5655..."
    license: "CC BY 4.0"
tool_calls: 15
entities_discovered: 42
cross_references: 7
```

---

## Level 3: Interactive Publication (Future — Separate Spec)

### Vision

MDX components that render linked-past entities as interactive cards:

```mdx
import { Entity, LinkGraph, QueryResult } from '@linked-past/components'

# Caesar's Provincial Commands

<Entity uri="dprr:Person/1957" />

This entity appears across multiple datasets:

<LinkGraph uri="dprr:Person/1957" depth={2} />

## Moneyer Coinage

<QueryResult
  dataset="crro"
  sparql={`SELECT ?type ?label WHERE {
    ?type nmo:hasAuthority nm:julius_caesar ;
          skos:prefLabel ?label .
  }`}
/>
```

**Components:**

| Component | Renders |
|---|---|
| `<Entity uri={...} />` | Entity card with name, dates, key properties, cross-links |
| `<LinkGraph uri={...} depth={n} />` | Force-directed graph of cross-dataset connections |
| `<QueryResult dataset={...} sparql={...} />` | Live query result table (re-executable) |
| `<Citation dataset={...} />` | Formatted scholarly citation with OCI digest |
| `<Provenance uri={...} predicate={...} />` | Source → factoid → dataset chain |

This is a separate frontend project. The MCP server provides the data API; the components consume it.

---

## Implementation Plan

### Phase 1 (Level 1 — do now)

1. Add `session_log: list[dict]` to `AppContext`
2. Add `_log_tool_call` wrapper — instrument each tool
3. Add `export_report` tool (json, provenance, markdown formats)
4. ~150 lines of new code

### Phase 2 (Level 2 — next session)

1. Add entity reference formatting in markdown output
2. Add session metadata header
3. Create a Claude Code skill for "generate research report from session"
4. ~100 lines + skill definition

### Phase 3 (Level 3 — separate project)

1. `@linked-past/components` npm package
2. MDX integration
3. Live MCP connection from browser
4. Separate repo or `packages/linked-past-components/`

---

## Design Principles

1. **Log everything, render later.** The raw log is the source of truth. Reports are views over it.

2. **Reproducibility first.** Every report includes dataset versions and OCI digests. A reader can pull the exact same data and re-run the exact same queries.

3. **Progressive enhancement.** JSON log → Markdown report → Interactive publication. Each level adds richness without breaking the previous.

4. **Don't block the workflow.** Logging is append-only and adds negligible overhead. The scholar doesn't think about reports until they want one.

5. **Citations are structural, not decorative.** Entity references resolve to real URIs. Dataset citations include cryptographic digests. This is scholarship infrastructure, not formatting sugar.
