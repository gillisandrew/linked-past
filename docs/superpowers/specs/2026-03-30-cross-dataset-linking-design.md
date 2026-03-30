# Cross-Dataset Person Linking and Query-Time "See Also"

**Date:** 2026-03-30
**Status:** Draft

## Problem

The DPRR, Nomisma, and CRRO datasets describe overlapping persons (Roman
Republican officials who also appear on coins) but share no cross-reference
URIs. This was documented in `hispanic-mint-documentary-gaps.md`: officials
like C. Annius, Caesar, and the Pompeii exist in both DPRR (as office-holders)
and Nomisma (as coin authorities), but automated cross-referencing is
impossible. Users who query one dataset get no hint that related records exist
in another.

## Goals

1. Declare known person-level equivalences between DPRR and Nomisma in the
   existing linkage YAML format, with scholarly provenance.
2. Surface those links automatically in `query` tool responses as a "See also"
   section, so users discover cross-dataset connections without calling
   `find_links` manually.
3. Keep latency impact negligible — the linkage graph is small and already
   in-memory.

## Non-Goals

- Automated Wikidata reconciliation pipeline (future work, `scripts/`).
- Linking every Nomisma person to DPRR — only the confirmed matches we've
  already identified.
- Changing the `find_links` or `explore_entity` tools (they already surface
  linkage data correctly).

---

## Design

### Part 1: Linkage YAML File

Create `linked_past/linkages/dprr_nomisma.yaml` following the established
format. Each link maps a DPRR person URI to a Nomisma person URI.

**Relationship type:** `skos:closeMatch` — not `owl:sameAs` because the
entities are conceptually different (a prosopographic person record vs. a
numismatic authority record). They refer to the same historical individual
but model different facets.

**Confidence levels:**
- `confirmed` — the DPRR explicitly records a "moneyer" post citing RRC, and
  the Nomisma URI is the RRC authority for the same person.
- `probable` — strong circumstantial match (same name, overlapping dates,
  Hispanic context) but no shared RRC citation in the DPRR.

**Initial link set** (10 links from the gap analysis):

| DPRR URI | Nomisma URI | Confidence | Note |
|----------|-------------|------------|------|
| `entity/Person/1740` (C. Annius) | `nomisma:c_annivs_rrc` | confirmed | RRC 366/3-4; DPRR moneyer 82-81 BC |
| `entity/Person/2082` (Cn. Lentulus Marcellinus) | `nomisma:cn_len_rrc` | confirmed | RRC 393/1; DPRR curator 76-75 BC |
| `entity/Person/1889` (Q. Metellus Pius) | `nomisma:q_c_m_p_i_rrc` | confirmed | DPRR moneyer 81 BC citing RRC |
| `entity/Person/1976` (Cn. Pompeius Magnus) | `nomisma:pompey` | confirmed | DPRR moneyer 71, 49 BC citing RRC |
| `entity/Person/2253` (Cn. Pompeius Jr.) | `nomisma:cn_magnvs_imp_rrc` | probable | RRC 470-471; DPRR promagistrate in Hispania |
| `entity/Person/2254` (Sex. Pompeius Pius) | `nomisma:sex_magnvs_rrc` | probable | RRC 477-479; DPRR legatus Hispania Ulterior |
| `entity/Person/1957` (C. Iulius Caesar) | `nomisma:julius_caesar` | confirmed | RRC 468; DPRR moneyer 49-44 BC |
| `entity/Person/2481` (Q. Cassius Longinus) | `nomisma:q_cassivs_rrc` | confirmed | RRC 428; DPRR quaestor Hispania |
| `entity/Person/2613` (M. Minatius Sabinus) | `nomisma:m_minat_sabin_rrc` | probable | RRC 470/1; DPRR proquaestor Hispania |
| `entity/Person/2623` (M. Publicius) | `nomisma:m_poblici_rrc` | probable | RRC 469/1; DPRR legatus pro praetore Hispania |

**Basis citation:** "Cross-referencing DPRR v1.3.0 post assertions (source:
Broughton MRR, Crawford RRC) against CRRO coin type attributions
(numismatics.org/crro) and Nomisma person authorities (nomisma.org)."

**Note:** The Nomisma URIs above (e.g., `cn_len_rrc`, `m_poblici_rrc`) need
verification against the actual Nomisma ID namespace before committing. Some
may not exist yet — Nomisma's coverage of minor Republican moneyers is
incomplete. Links to non-existent URIs should be omitted; the YAML file should
only contain links where both endpoints resolve.

**File structure:**

```yaml
metadata:
  source_dataset: dprr
  target_dataset: nomisma
  relationship: "skos:closeMatch"
  confidence: confirmed          # default; overridden per-link
  method: manual_alignment
  basis: >-
    Cross-referencing DPRR v1.3.0 post assertions (Broughton MRR; Crawford RRC)
    against CRRO coin type attributions and Nomisma person authorities.
    See hispanic-mint-documentary-gaps.md for full methodology.
  author: linked-past project
  date: "2026-03-30"
links:
  - source: "http://romanrepublic.ac.uk/rdf/entity/Person/1740"
    target: "http://nomisma.org/id/c_annivs_rrc"
    note: "RRC 366/3-4; DPRR moneyer 82-81 BC"
  # ... remaining links
```

For links with a different confidence than the metadata default, the linkage
system currently applies the metadata-level confidence uniformly. To support
per-link confidence, split into two YAML files: `dprr_nomisma_confirmed.yaml`
and `dprr_nomisma_probable.yaml`. This avoids changes to the LinkageGraph
loader.

### Part 2: "See Also" in Query Responses

After a successful `query` execution, scan the result URIs for known
cross-dataset links and append a "See also" section between the results table
and the Sources footer.

**Location in code:** `linked_past/core/server.py`, in the `query` tool
function, after line 227 (`table = toons.dumps(result.rows)`).

**Algorithm:**

```
1. Collect all URI values from result.rows
   - For each row, for each value, check if it looks like a URI
     (starts with "http://" or "https://")
   - Deduplicate into a set

2. For each URI, query linkage.find_links(uri)
   - This is fast: the linkage store is in-memory, and we expect
     O(tens) of links total across all datasets
   - Collect results into a dict: {source_uri: [link_records]}

3. If any links found, format a "See also" section:
   ─── See also ───
   - Person/1740 (C. Annius) → nomisma:c_annivs_rrc (confirmed)
   - Person/1957 (Caesar) → nomisma:julius_caesar (confirmed)
   Use `find_links(uri)` for full provenance.

4. Append between table and Sources footer
```

**What to show:** Keep it terse — one line per linked entity, with the target
URI, confidence level, and a pointer to `find_links` for details. The goal is
awareness, not full provenance in every query response.

**Performance:** The linkage graph is a small in-memory Oxigraph store
(currently ~50 quads for dprr_pleiades, will grow to ~150 with person links).
Each `find_links` call is a SPARQL query against this store. For a typical
query returning 20 rows with ~3 URI columns each, that's at most 60 lookups
against a tiny store — sub-millisecond total.

**Edge cases:**
- No links found → no "See also" section (common case, zero overhead beyond
  the URI scan).
- Large result sets (200+ rows) → cap URI scanning at the first 50 unique
  URIs to bound the work.
- URIs from the linkage graph itself → skip (avoid self-referential loops).

**Helper function** (new, in `server.py` or a small utility):

```python
def _collect_see_also(
    rows: list[dict[str, str]],
    linkage: LinkageGraph | None,
    max_uris: int = 50,
) -> str:
    """Scan query result URIs for cross-dataset links. Returns formatted section or empty string."""
    if not linkage:
        return ""

    uris: set[str] = set()
    for row in rows:
        for value in row.values():
            if value and value.startswith("http"):
                uris.add(value)
            if len(uris) >= max_uris:
                break

    see_also_lines: list[str] = []
    seen_targets: set[str] = set()
    for uri in uris:
        for link in linkage.find_links(uri):
            target = link["target"]
            if target not in seen_targets:
                seen_targets.add(target)
                confidence = link.get("confidence", "")
                see_also_lines.append(
                    f"  {uri} → {target} ({confidence})"
                )

    if not see_also_lines:
        return ""

    header = "\n─── See also ───\n"
    footer = "\nUse `find_links(uri)` for full provenance.\n"
    return header + "\n".join(see_also_lines) + footer
```

**Integration in `query` tool:**

```python
# After: table = toons.dumps(result.rows)
see_also = _collect_see_also(result.rows, app.linkage)

# Change footer assembly to:
return table + see_also + footer
```

### Part 3: URI Verification Step

Before committing the YAML file, each Nomisma target URI must be verified:

1. For each candidate Nomisma URI, run `search_entities` or
   `explore_entity` to confirm it exists in the loaded Nomisma store.
2. Drop any link where the target URI doesn't resolve to a real entity.
3. Document which candidates were dropped and why (URI not in Nomisma,
   ambiguous match, etc.) in the YAML file comments or in the gap analysis
   document.

This is a manual step during authoring, not a runtime check.

---

## Testing

### Linkage YAML loading
- Test that `dprr_nomisma_confirmed.yaml` loads without error via
  `LinkageGraph.load_yaml()`.
- Test that `find_links` returns the expected links for a DPRR person URI
  that has a Nomisma match.
- Test round-trip: load YAML → find_links → get_provenance → verify basis
  text.

### "See also" in query responses
- Test `_collect_see_also` with mock rows containing URIs that have links →
  returns formatted section.
- Test with rows containing no linked URIs → returns empty string.
- Test with rows containing no URIs at all → returns empty string.
- Test the 50-URI cap with a large result set.
- Integration test: execute a DPRR query that returns a linked person URI
  and verify the response contains "See also".

### Existing tests
- Verify existing `find_links` and `explore_entity` tests still pass (the
  new YAML file adds data to the linkage graph but shouldn't change behavior
  for existing links).

---

## Files Changed

| File | Change |
|------|--------|
| `linked_past/linkages/dprr_nomisma_confirmed.yaml` | **New.** Confirmed person links. |
| `linked_past/linkages/dprr_nomisma_probable.yaml` | **New.** Probable person links. |
| `linked_past/core/server.py` | Add `_collect_see_also` helper; call it in `query` tool. |
| `tests/test_linked_past_integration.py` | Add tests for see-also rendering. |

---

## Future Work

### Wikidata Reconciliation Pipeline

A `scripts/reconcile_wikidata.py` script that:

1. Extracts Wikidata QIDs from Nomisma persons (already in the data via
   `skos:closeMatch`).
2. For each DPRR person with a "moneyer" or "monetalis" post, queries the
   Wikidata API for matching Roman Republican figures by name + date range.
3. Joins on shared QIDs to generate candidate `skos:closeMatch` links.
4. Outputs a candidate YAML file for human review before promotion to the
   linkages directory.

This is explicitly out of scope for the current design but is the natural
next step once the manual links are validated and the "see also" UX is
confirmed.

### Per-Link Confidence in YAML

The current `LinkageGraph._load_data` applies metadata-level confidence to
all links. A future enhancement could support per-link `confidence` overrides
in the YAML format, avoiding the need to split confirmed/probable into
separate files. This is a small change to `linkage.py` but is not needed for
the initial implementation.
