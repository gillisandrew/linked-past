# Fix Schema/Examples Data Mismatches

**Date:** 2026-02-25
**Addresses:** Issues 1-2 from `docs/feedback/mcp-tool-usability-report.md`, plus additional mismatches discovered during investigation and swarm testing.

## Problem

The schema documentation and curated SPARQL examples contain property names, label values, type annotations, and data model assumptions that don't match the actual RDF data. Queries built from these examples silently return zero rows.

## Findings

### Round 1: Initial investigation

| Issue | Schema/Examples say | Data actually has |
|-------|-------------------|-------------------|
| Person display name | `rdfs:label` (string) | `vocab:hasPersonName` (string like `"IUNI0001 L. Iunius (46a) M. f. Brutus"`) |
| Reference entity labels | Bare labels: `"consul"`, `"Cornelia"` | Prefixed: `"Office: consul"`, `"Tribe: Cornelia"`, `"Province: Latium"`, `"Date Type: death"`, `"Relationship: father of"`, `"Secondary Source: Broughton MRR I"`, `"Status: senator"` |
| `hasDprrID` type | `xsd:integer` | `xsd:string` (format: `"IUNI0001"`) |
| `hasID` type | `xsd:integer` | `xsd:string` (numeric string: `"1"`) |
| Date integer casting (Issue 3) | Report said bare `-120` fails | Not reproducible — `FILTER(?start = -120)` works fine |

### Round 2: Swarm testing (6 agents with different questions)

| Issue | Severity | Details |
|-------|----------|---------|
| Province data model wrong | Critical | `hasProvince` is not on `PostAssertion`. There's an undocumented `PostAssertionProvince` intermediary class. The province example was doubly broken (wrong model + English "Sicily" vs Latin "Sicilia"). |
| Missing Person predicates | High | 7 predicates exist in data but not in schema: `hasAssociatedWebpage`, `hasNobilisNotes`, `hasNovusNotes`, `hasReNumberOld`, `isFiliationUncertain`, `isOtherNamesUncertain`, `isPatricianUncertain` |
| Boolean matching | NOT A BUG | Bare `true` works fine. Agent was confused by stale validator rejecting `hasPersonName`. |
| Undocumented classes in data | Noted | 8 classes exist but aren't in schema: `PostAssertionNote`, `PersonNote`, `PrimarySourceReference`, `RelationshipAssertionReference`, `StatusAssertionNote`, `RelationshipInverse`, `NoteType` (not fixed — auxiliary classes unlikely to be queried directly) |

## Changes Made

### 1. `dprr_tool/context/schemas.yaml`

**Person class:**
- Replace `rdfs:label` with `vocab:hasPersonName` (range `xsd:string`)
- Fix `hasDprrID`/`hasID` ranges from `xsd:integer` to `xsd:string`
- Add 7 missing predicates: `hasAssociatedWebpage`, `hasNobilisNotes`, `hasNovusNotes`, `hasReNumberOld`, `isFiliationUncertain`, `isOtherNamesUncertain`, `isPatricianUncertain`

**Reference entity classes** (Office, Province, Sex, Praenomen, Tribe, SecondarySource, PrimarySource, Status, Relationship, DateType):
- Update `rdfs:label` comment to document the prefix convention for each class

**New class: `PostAssertionProvince`:**
- Added with predicates: `hasPostAssertion`, `hasProvince`, `hasID`, `rdfs:label`, `isProvinceUncertain`
- Documents the intermediary join pattern for province queries

### 2. `dprr_tool/context/examples.yaml`

All 22 examples updated:
- **Person name:** `?person rdfs:label ?name` → `?person vocab:hasPersonName ?name`
- **Prefixed labels:** `"consul"` → `"Office: consul"`, `"Cornelia"` → `"Tribe: Cornelia"`, etc.
- **Province example:** Rewritten to use `PostAssertionProvince` intermediary join and Latin label `"Province: Sicilia"`
- **DPRR ID lookup:** Use `vocab:hasID "1"` instead of `vocab:hasDprrID 1`
- **Death type:** `"Death"` → `"Date Type: death"`
- **Secondary source:** `"Broughton MRR"` → `"Secondary Source: Broughton MRR I"`

### 3. Tests

- `test_store.py`: Updated `SAMPLE_TURTLE` to use `hasPersonName`, `hasID`, and prefixed labels
- `test_context.py`: Updated Person property assertions, added `PostAssertionProvince` to expected classes
- `test_validate.py`: Updated all query strings to use `hasPersonName`
- `test_integration.py`: Updated query strings
- `test_pipeline.py`: Updated mock pipeline SPARQL

## Not in scope

- Issue 4 from original report (semantic validation warnings) — separate enhancement
- Issue 5 from original report (multi-valued hasDateStart) — separate enhancement
- Auxiliary undocumented classes (PostAssertionNote, PersonNote, etc.) — unlikely to be queried directly
- DateType value enumeration — enhancement for discoverability
- Office descriptions (all null in data) — data quality issue
