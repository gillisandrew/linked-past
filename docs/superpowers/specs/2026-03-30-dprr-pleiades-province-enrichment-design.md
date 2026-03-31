# DPRR Province → Pleiades Enrichment

## Goal

Extend the existing `dprr_pleiades.yaml` linkage file to cover all DPRR geographic provinces with clear 1:1 Pleiades Place matches. Currently 5 of ~50 geographic provinces are linked; this work adds the remaining ~45.

## Approach

Manual curation using MCP tools (`search_entities`, `query` against Pleiades). For each unlinked geographic DPRR province, find the corresponding Pleiades Place URI and add a `skos:closeMatch` link.

## Output

Append new links to `packages/linked-past/linked_past/linkages/dprr_pleiades.yaml`. Same format and metadata conventions as existing entries.

## Matching Criteria

- Province name matches a Pleiades place name (ancient or modern) for the same geographic region
- Pleiades URIs use the `#this` fragment (refers to the Place concept)
- Reference basis: Barrington Atlas of the Greek and Roman World (Talbert 2000)

## Exclusions

Skip all non-geographic DPRR "provinces":

- **Legal/jurisdictional:** repetundae, ambitus, urbanus, inter peregrinos, inter sicarios, maiestas, peculatus, de vi, de veneficiis, quaestio extraordinaria, quo senatus censuisset, provincia declined
- **Non-geographic assignments:** fleet, cum imperio consulari, cum imperio consulari infinito
- **Vague geography:** "In the east", "Mediterranean", "Allied cities of Italy"
- **Blank:** Province/92

## Confidence

All links: `confidence: confirmed`, `method: manual_alignment`.

## Existing Links (preserved as-is)

| DPRR Province | Pleiades | Note |
|---|---|---|
| Province/Sicilia → Province/5 | places/462492 | Map 47 |
| Province/Africa → Province/23 | places/775 | Map 33 |
| Province/Hispania → Province/18 | places/1027 | Map 25-27 |
| Province/Asia → Province/25 | places/837 | Map 56-62 |
| Province/Gallia → Province/6 | places/993 | Map 14-17 |

## Implementation

1. Query all 92 DPRR provinces, filter to geographic candidates (~50)
2. Remove the 5 already linked
3. For each remaining province, search Pleiades for the matching place
4. Verify match, record Pleiades URI + Barrington Atlas map reference
5. Append all new links to `dprr_pleiades.yaml`
6. Run tests to ensure linkage file loads correctly
