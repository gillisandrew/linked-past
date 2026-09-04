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
fragment; `classes` lists class names, either `schemas.yaml` keys or the URI
local names (`geography_place` for `edh:geography_place`), empty for
cross-cutting. Tip matching uses URI local names, so the plugin maps keys to
local names when it loads; `test_plugin_tip_classes_resolve_to_schema_classes`
fails on any tag that is neither.

```yaml
tips:
  - title: "date_as_string"
    body: |
      nmo:hasStartDate is an xsd:string like '0071', not an integer.
      Compare numerically by casting: FILTER(xsd:integer(?startDate) <= -1).
      Plain string comparison is wrong here: it reverses order within BC
      years (e.g. "-0044" > "-0001") and sorts every AD year after every BC
      year.
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
