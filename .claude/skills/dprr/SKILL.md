---
name: dprr
description: Use when answering prosopographical questions about the Roman Republic using the DPRR MCP tools. Use when querying magistracies, priesthoods, family relationships, or status assertions from the DPRR RDF store.
---

# Querying the Digital Prosopography of the Roman Republic

## Overview

DPRR aggregates modern secondary sources (principally Broughton's _MRR_, Rüpke's _Fasti Sacerdotum_, Zmeskal's _Adfinitas_) into a SPARQL-queryable RDF store. **Every result is "according to Broughton (or Zmeskal, or Rüpke), as digitised by the DPRR team" — not "according to the ancient sources."**

You have three MCP tools: `get_schema`, `validate_sparql`, `execute_sparql`.

**Iron rule: ALWAYS validate before execute. No exceptions.**

## Prefixes

Always use these exact namespace URIs — do NOT guess or use other domains:

```sparql
PREFIX vocab: <http://romanrepublic.ac.uk/rdf/ontology#>
PREFIX entity: <http://romanrepublic.ac.uk/rdf/entity/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
```

The `validate_sparql` tool auto-repairs missing prefixes, but using wrong URIs (e.g. `https://dprr.classics.ox.ac.uk/`) will cause errors. When in doubt, call `get_schema` first.

## Workflow

```
get_schema → draft query → validate_sparql → fix errors → validate again → execute_sparql
```

Never call `execute_sparql` without a preceding successful `validate_sparql` on the same query. If you edit a query after validation, re-validate before executing.

### Query Patterns

**Find a person:**

```sparql
SELECT ?person ?name ?dprrId
WHERE {
  ?person a vocab:Person .
  ?person vocab:hasPersonName ?name .
  ?person vocab:hasDprrID ?dprrId .
  ?person vocab:hasNomen "Tullius" .
  FILTER(CONTAINS(?name, "Cicero"))
}
```

**Career with uncertainty flags and sources:**

```sparql
SELECT ?officeLabel ?dateStart ?dateEnd ?isUncertain
       ?isDateStartUncertain ?isDateEndUncertain ?srcLabel
WHERE {
  ?person a vocab:Person .
  ?person vocab:hasDprrID "TULL2072" .
  ?pa a vocab:PostAssertion .
  ?pa vocab:isAboutPerson ?person .
  ?pa vocab:hasOffice ?office . ?office rdfs:label ?officeLabel .
  ?pa vocab:hasSecondarySource ?src . ?src rdfs:label ?srcLabel .
  OPTIONAL { ?pa vocab:hasDateStart ?dateStart }
  OPTIONAL { ?pa vocab:hasDateEnd ?dateEnd }
  OPTIONAL { ?pa vocab:isUncertain ?isUncertain }
  OPTIONAL { ?pa vocab:isDateStartUncertain ?isDateStartUncertain }
  OPTIONAL { ?pa vocab:isDateEndUncertain ?isDateEndUncertain }
}
ORDER BY ?dateStart
```

**ALWAYS query uncertainty flags** (`isUncertain`, `isDateStartUncertain`, `isDateEndUncertain`) and the secondary source (`hasSecondarySource`) on every post assertion. Never omit these.

**Relationships with sources:**

```sparql
SELECT ?relatedName ?relLabel ?srcLabel
WHERE {
  ?person vocab:hasDprrID "TULL2072" .
  ?ra a vocab:RelationshipAssertion .
  ?ra vocab:isAboutPerson ?person .
  ?ra vocab:hasRelatedPerson ?related .
  ?related vocab:hasPersonName ?relatedName .
  ?ra vocab:hasRelationship ?rel . ?rel rdfs:label ?relLabel .
  ?ra vocab:hasSecondarySource ?src . ?src rdfs:label ?srcLabel .
}
```

**Scholarly notes on assertions:**

```sparql
SELECT ?noteText ?noteSrcLabel
WHERE {
  ?pa a vocab:PostAssertion .
  ?pa vocab:isAboutPerson ?person .
  ?person vocab:hasDprrID "CORN1746" .
  ?pa vocab:hasPostAssertionNote ?note .
  ?note vocab:hasNoteText ?noteText .
  OPTIONAL { ?note vocab:hasSecondarySourceForNote ?ns .
             ?ns rdfs:label ?noteSrcLabel }
}
```

## Writing the Prose

The output MUST be well-cited academic prose. Follow these requirements without exception.

### 1. Open with a Methodological Frame

Every answer must begin by establishing what DPRR is and what it can and cannot tell us. State that DPRR aggregates secondary scholarship — principally Broughton's _MRR_ — and that results reflect modern editorial judgments, not unmediated ancient evidence.

### 2. Cite the Secondary Source for Every Claim

When reporting an office, date, or relationship from DPRR, attribute it to the underlying secondary source:

- "Broughton (_MRR_ II) records Cicero as quaestor in 75 BC"
- "Zmeskal (2009) identifies her as the daughter of..."
- "Rüpke (_Fasti Sacerdotum_) attests his augurate from 53 BC"

**Never write**: "He held the consulship in 63 BC" as if this were unmediated fact. **Always write**: "He is recorded as consul in 63 BC (Broughton, _MRR_ II)" or similar.

Map the `hasSecondarySource` labels to citations:
| DPRR Source Label | Citation |
|---|---|
| Broughton MRR I / II / III | Broughton, _MRR_ I / II / III |
| Rüpke 2005 | Rüpke, _Fasti Sacerdotum_ |
| Zmeskal 2009 | Zmeskal, _Adfinitas_ |
| Ryan 1998, Brennan 2000, etc. | Use as-is |

### 3. Surface Every Uncertainty Flag

If `isUncertain`, `isDateStartUncertain`, or `isDateEndUncertain` is `true`, you MUST flag this in prose. Do not silently present uncertain attestations as fact.

- "His praetorship is tentatively dated to 97 BC, though the date is uncertain (Broughton, _MRR_ II)"
- "The augurate is attested but flagged as uncertain in DPRR"

When scholarly notes accompany uncertain assertions, summarise the debate.

### 4. Never Argue from Silence

A query returning zero results means DPRR's sources do not record it. It does NOT mean the event never happened.

- **Never write**: "He never held the quaestorship" or "confirms a gap in office-holding"
- **Always write**: "No quaestorship is recorded in DPRR's sources" or "DPRR records no office-holding for this period, though this may reflect gaps in the evidence rather than genuine absence"

### 5. Treat Relationship Assertions as Hypotheses

Family connections in DPRR are scholarly reconstructions based on onomastic inference (Zmeskal 2009, Salomies 1992), not documented pedigrees. Present them accordingly:

- "Zmeskal identifies her as the probable daughter of..."
- "The relationship assertion in DPRR, following Zmeskal (2009), records him as the son of..."

### 6. Flag Status Labels as Modern Convention

`isNobilis` and `isNovus` encode modern scholarly convention. Brunt (1982) demonstrated that no ancient definition of _nobilis_ or _novus homo_ exists.

- "DPRR classifies him as _novus homo_, following modern scholarly convention (on which see Brunt 1982)"

### 7. Control for Temporal Unevenness

When comparing across periods, explicitly note differential documentation:

- Late Republic (c. 133–31 BC): dense documentation (Cicero, Caesar, epigraphy)
- Middle Republic (c. 264–133 BC): depends on Livy, fragmentary _fasti_
- Early Republic (509–264 BC): traditions of questionable historicity

**Never calculate rates or percentages across periods without discussing sample bias and source survival.**

### 8. Acknowledge Elite Bias

DPRR documents only the political upper strata — senators, magistrates, priests, equestrians. Women appear almost exclusively through relationship assertions. State this limitation when relevant, particularly when discussing women, non-elite actors, or drawing conclusions about "Roman society."

### 9. Close with a Bibliography

End every response with a bibliography of works cited, including:

- The underlying DPRR secondary sources cited in your prose
- The caveat scholarship (Brunt 1982, Salomies 1992, etc.) where invoked
- Bradley (2020) on DPRR's methodology when discussing the database itself

### 10. Include What Prosopography Cannot Capture

Where relevant, note that DPRR's relational data cannot represent ideological, economic, or cultural dimensions of political life (Hölkeskamp 2010). Clientage networks were constantly shifting rather than the fixed structures database relationships imply.

## Red Flags — STOP and Revise

If you catch yourself writing any of these, stop and rewrite:

- "He held the consulship in X BC" (without source attribution)
- "confirms a gap" or "never held" (argument from silence)
- "was the son/daughter of" (relationship assertion as fact, without citing Zmeskal or the relevant source)
- "X% of consuls were novi homines" (without sample bias discussion)
- Comparing early and late Republic data without temporal caveats
- Executing a SPARQL query without validating it first
- Omitting `isUncertain` / `isDateStartUncertain` / `isDateEndUncertain` from post assertion queries

## Standard Caveat Bibliography

```
Bradley, John. "A Prosopography as Linked Open Data." DHQ 14.2 (2020).
Broughton, T. R. S. The Magistrates of the Roman Republic. 3 vols. (1951–1986).
Brunt, P. A. "Nobilitas and Novitas." JRS 72 (1982): 1–17.
Brunt, P. A. The Fall of the Roman Republic. Oxford (1988).
Develin, R. Patterns in Office-Holding, 366–49 B.C. Brussels (1979).
Flower, H. I. Roman Republics. Princeton (2010).
Hölkeskamp, K.-J. Reconstructing the Roman Republic. Princeton (2010).
Mouritsen, H. Plebs and Politics in the Late Roman Republic. Cambridge (2001).
Rüpke, J. Fasti Sacerdotum. Stuttgart (2005).
Salomies, O. Adoptive and Polyonymous Nomenclature. Helsinki (1992).
Zmeskal, K. Adfinitas. 2 vols. Passau (2009).
```
