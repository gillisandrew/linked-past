# Linked Past: Dataset Plugins (Pleiades, PeriodO, Nomisma) + ORAS Distribution — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add three new dataset plugins (Pleiades, PeriodO, Nomisma) and migrate all dataset fetching to ORAS-based OCI artifact distribution for uniform versioning and caching.

**Architecture:** Each dataset is pre-processed into Oxigraph-ready Turtle at build time (via scripts), pushed to ghcr.io as a public OCI artifact, and pulled at runtime via `oras-py`. Each plugin follows the established `DatasetPlugin` pattern from Plan 1: YAML context files (schemas, examples, tips, prefixes) + a `plugin.py`. DPRR's existing fetch logic is migrated to the same ORAS pattern.

**Tech Stack:** Python 3.13+, oras-py, pyoxigraph, rdflib (for PeriodO JSON-LD conversion)

**Scope:** DPRR + Pleiades + PeriodO + Nomisma (4 datasets). POMS deferred (CKAN download unreliable).

**Deferred (Plan 3):** Linkage graph, embeddings, advanced tools (explore_entity, get_provenance, find_links, search_entities, update_dataset)

---

## File Structure

```
linked_past/
├── core/
│   ├── fetch.py              # ORAS-based fetch: pull OCI artifact to data_dir
│   └── ...                   # (existing from Plan 1)
├── datasets/
│   ├── base.py               # (modify: add default fetch using core.fetch)
│   ├── dprr/
│   │   ├── plugin.py         # (modify: replace custom fetch with ORAS)
│   │   └── context/ ...      # (existing)
│   ├── pleiades/
│   │   ├── __init__.py
│   │   ├── plugin.py
│   │   └── context/
│   │       ├── schemas.yaml
│   │       ├── examples.yaml
│   │       ├── tips.yaml
│   │       └── prefixes.yaml
│   ├── periodo/
│   │   ├── __init__.py
│   │   ├── plugin.py
│   │   └── context/
│   │       ├── schemas.yaml
│   │       ├── examples.yaml
│   │       ├── tips.yaml
│   │       └── prefixes.yaml
│   └── nomisma/
│       ├── __init__.py
│       ├── plugin.py
│       └── context/
│           ├── schemas.yaml
│           ├── examples.yaml
│           ├── tips.yaml
│           └── prefixes.yaml
scripts/
├── package_dprr.py           # Download + package DPRR data as OCI artifact
├── package_pleiades.py       # Download + package Pleiades data
├── package_periodo.py        # Download + convert + package PeriodO data
├── package_nomisma.py        # Download + package Nomisma data
tests/
├── test_core_fetch.py
├── test_pleiades_plugin.py
├── test_periodo_plugin.py
├── test_nomisma_plugin.py
```

---

### Task 1: Add ORAS-based fetch infrastructure

**Files:**
- Create: `linked_past/core/fetch.py`
- Modify: `linked_past/datasets/base.py` — add default `fetch()` using ORAS
- Modify: `pyproject.toml` — add `oras` dependency
- Test: `tests/test_core_fetch.py`

- [ ] **Step 1: Add oras dependency to pyproject.toml**

In `pyproject.toml`, add `"oras"` to the dependencies list:

```toml
dependencies = [
    "pyoxigraph",
    "rdflib",
    "pyyaml",
    "mcp",
    "toons>=0.5.3",
    "oras",
]
```

Run: `uv sync` to install.

- [ ] **Step 2: Write the failing test**

```python
# tests/test_core_fetch.py
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from linked_past.core.fetch import pull_artifact, default_registry, artifact_ref


def test_artifact_ref():
    ref = artifact_ref("dprr", "1.3.0")
    assert "dprr" in ref
    assert "1.3.0" in ref


def test_artifact_ref_latest():
    ref = artifact_ref("pleiades")
    assert "latest" in ref


def test_default_registry():
    reg = default_registry()
    assert "ghcr.io" in reg


def test_pull_artifact_calls_oras(tmp_path):
    with patch("linked_past.core.fetch.oras.client.OrasClient") as MockClient:
        mock_instance = MagicMock()
        MockClient.return_value = mock_instance
        mock_instance.pull.return_value = [str(tmp_path / "data.ttl")]

        result = pull_artifact("dprr", tmp_path, version="1.0.0")

        mock_instance.pull.assert_called_once()
        call_args = mock_instance.pull.call_args
        assert "dprr" in call_args.kwargs.get("target", call_args.args[0] if call_args.args else "")


def test_pull_artifact_returns_path(tmp_path):
    with patch("linked_past.core.fetch.oras.client.OrasClient") as MockClient:
        mock_instance = MagicMock()
        MockClient.return_value = mock_instance
        ttl_file = tmp_path / "data.ttl"
        ttl_file.write_text("# empty turtle")
        mock_instance.pull.return_value = [str(ttl_file)]

        result = pull_artifact("dprr", tmp_path, version="1.0.0")
        assert result == ttl_file
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_core_fetch.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'linked_past.core.fetch'`

- [ ] **Step 4: Write the implementation**

```python
# linked_past/core/fetch.py
"""ORAS-based dataset fetching from OCI registry."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import oras.client

logger = logging.getLogger(__name__)

_DEFAULT_REGISTRY = "ghcr.io/gillisandrew/linked-past"


def default_registry() -> str:
    """Return the OCI registry base path, overridable via LINKED_PAST_REGISTRY."""
    return os.environ.get("LINKED_PAST_REGISTRY", _DEFAULT_REGISTRY)


def artifact_ref(dataset: str, version: str = "latest") -> str:
    """Build an OCI artifact reference for a dataset."""
    registry = default_registry()
    return f"{registry}/{dataset}:{version}"


def pull_artifact(dataset: str, data_dir: Path, version: str = "latest") -> Path:
    """Pull a dataset artifact from the OCI registry.

    Downloads all layers to data_dir. Returns path to the primary .ttl file.
    Falls back to LINKED_PAST_{DATASET}_URL env var for legacy HTTP download.
    """
    # Check for legacy URL override (e.g., LINKED_PAST_DPRR_URL)
    legacy_url = os.environ.get(f"LINKED_PAST_{dataset.upper()}_URL")
    if legacy_url:
        return _fetch_legacy(legacy_url, data_dir, dataset)

    ref = artifact_ref(dataset, version)
    logger.info("Pulling %s to %s", ref, data_dir)

    client = oras.client.OrasClient()
    files = client.pull(target=ref, outdir=str(data_dir))

    # Find the .ttl file among pulled files
    ttl_files = [Path(f) for f in files if f.endswith(".ttl")]
    if not ttl_files:
        raise RuntimeError(f"No .ttl file found in artifact {ref}. Got: {files}")

    logger.info("Pulled %s (%d files)", ref, len(files))
    return ttl_files[0]


def _fetch_legacy(url: str, data_dir: Path, dataset: str) -> Path:
    """Legacy HTTP fetch for backwards compatibility."""
    import tarfile
    import urllib.request

    logger.info("Legacy fetch from %s", url)
    data_dir.mkdir(parents=True, exist_ok=True)

    tmp_path, _ = urllib.request.urlretrieve(url)
    try:
        # Try as tarball first
        if tarfile.is_tarfile(tmp_path):
            with tarfile.open(tmp_path, "r:gz") as tar:
                tar.extractall(path=str(data_dir), filter="data")
        else:
            # Plain file — copy to data_dir
            import shutil
            dest = data_dir / f"{dataset}.ttl"
            shutil.copy2(tmp_path, dest)
            return dest
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    # Find the .ttl file
    ttl_files = list(data_dir.glob("*.ttl"))
    if not ttl_files:
        raise RuntimeError(f"No .ttl file found after fetching {url}")
    return ttl_files[0]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_core_fetch.py -v`
Expected: PASS (5 tests)

- [ ] **Step 6: Update DatasetPlugin base to use ORAS fetch by default**

In `linked_past/datasets/base.py`, change `fetch` from abstract to a default implementation. Add `oci_dataset` and `oci_version` attributes:

Add these class attributes after `rdf_format`:
```python
    oci_dataset: str = ""   # OCI artifact name (e.g., "dprr", "pleiades")
    oci_version: str = "latest"
```

Change `fetch` from abstract to default:
```python
    def fetch(self, data_dir: Path) -> Path:
        """Download data via ORAS from OCI registry. Override for custom fetch logic."""
        from linked_past.core.fetch import pull_artifact
        if not self.oci_dataset:
            raise NotImplementedError(f"{self.__class__.__name__} must set oci_dataset or override fetch()")
        return pull_artifact(self.oci_dataset, data_dir, self.oci_version)
```

Remove the `@abstractmethod` decorator from `fetch`.

- [ ] **Step 7: Update DPRR plugin to use ORAS fetch**

In `linked_past/datasets/dprr/plugin.py`:

Add class attributes:
```python
    oci_dataset = "dprr"
    oci_version = "1.3.0"
```

Remove the entire `fetch()` method override (the base class default now handles it).

Remove unused imports: `os`, `sys`, `tarfile`, `urllib.request`.

Keep `DPRR_DATA_URL` support by ensuring the env var `LINKED_PAST_DPRR_URL` is checked (the base `pull_artifact` does this).

- [ ] **Step 8: Run all tests**

Run: `uv run pytest -v && uv run ruff check .`
Expected: All tests pass, lint clean. The DPRR plugin tests should still pass since they mock `fetch()` or use pre-populated data.

- [ ] **Step 9: Commit**

```bash
git add linked_past/core/fetch.py linked_past/datasets/base.py linked_past/datasets/dprr/plugin.py pyproject.toml tests/test_core_fetch.py
git commit -m "feat: add ORAS-based fetch infrastructure, migrate DPRR to OCI pull"
```

---

### Task 2: Pleiades dataset plugin

**Files:**
- Create: `linked_past/datasets/pleiades/__init__.py`
- Create: `linked_past/datasets/pleiades/plugin.py`
- Create: `linked_past/datasets/pleiades/context/schemas.yaml`
- Create: `linked_past/datasets/pleiades/context/examples.yaml`
- Create: `linked_past/datasets/pleiades/context/tips.yaml`
- Create: `linked_past/datasets/pleiades/context/prefixes.yaml`
- Modify: `linked_past/core/server.py` — register Pleiades plugin
- Test: `tests/test_pleiades_plugin.py`

- [ ] **Step 1: Create context YAML files**

```yaml
# linked_past/datasets/pleiades/context/prefixes.yaml
prefixes:
  pleiades: "https://pleiades.stoa.org/places/vocab#"
  geo: "http://www.w3.org/2003/01/geo/wgs84_pos#"
  osgeo: "http://data.ordnancesurvey.co.uk/ontology/geometry/"
  dcterms: "http://purl.org/dc/terms/"
  skos: "http://www.w3.org/2004/02/skos/core#"
  foaf: "http://xmlns.com/foaf/0.1/"
  cito: "http://purl.org/spar/cito/"
  prov: "http://www.w3.org/ns/prov#"
  rdfs: "http://www.w3.org/2000/01/rdf-schema#"
  rdf: "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
  xsd: "http://www.w3.org/2001/XMLSchema#"
```

```yaml
# linked_past/datasets/pleiades/context/schemas.yaml
classes:
  Place:
    label: "Place"
    comment: "An ancient geographic place (also typed skos:Concept). ~41,000 places covering the Greek and Roman world."
    uri: "pleiades:Place"
    properties:
      - pred: "dcterms:title"
        range: "xsd:string"
        comment: "Display title of the place"
      - pred: "dcterms:description"
        range: "xsd:string"
        comment: "Textual description"
      - pred: "pleiades:hasLocation"
        range: "pleiades:Location"
        comment: "Links to one or more Location entities with coordinates"
      - pred: "pleiades:hasName"
        range: "pleiades:Name"
        comment: "Links to one or more Name entities with attested/romanized forms"
      - pred: "pleiades:hasFeatureType"
        range: "skos:Concept"
        comment: "Feature type from controlled vocabulary (settlement, temple, fort, etc.)"
      - pred: "foaf:primaryTopicOf"
        range: "xsd:anyURI"
        comment: "Link to the Pleiades web page for this place"
      - pred: "prov:wasDerivedFrom"
        range: "xsd:anyURI"
        comment: "Provenance source"
      - pred: "cito:citesForEvidence"
        range: "xsd:anyURI"
        comment: "Bibliographic citation for evidence"
      - pred: "cito:citesForInformation"
        range: "xsd:anyURI"
        comment: "Bibliographic citation for information"

  Location:
    label: "Location"
    comment: "Physical location of a place with coordinates and geometry. A Place may have multiple Locations for different time periods."
    uri: "pleiades:Location"
    properties:
      - pred: "dcterms:title"
        range: "xsd:string"
        comment: "Location label"
      - pred: "geo:lat"
        range: "xsd:float"
        comment: "WGS84 latitude"
      - pred: "geo:long"
        range: "xsd:float"
        comment: "WGS84 longitude"
      - pred: "osgeo:asGeoJSON"
        range: "xsd:string"
        comment: "GeoJSON geometry string"
      - pred: "pleiades:during"
        range: "skos:Concept"
        comment: "Time period when this location was relevant (SKOS concept, not a date literal)"
      - pred: "pleiades:start_date"
        range: "xsd:string"
        comment: "Earliest CE year of related time periods"
      - pred: "pleiades:end_date"
        range: "xsd:string"
        comment: "Latest CE year of related time periods"

  Name:
    label: "Name"
    comment: "An appellation of a place in historical context, with attested and romanized forms."
    uri: "pleiades:Name"
    properties:
      - pred: "pleiades:nameAttested"
        range: "xsd:string"
        comment: "Attested form in original writing system"
      - pred: "pleiades:nameRomanized"
        range: "xsd:string"
        comment: "Romanized/transliterated form"
      - pred: "pleiades:during"
        range: "skos:Concept"
        comment: "Time period when this name was in use"
      - pred: "pleiades:start_date"
        range: "xsd:string"
        comment: "Earliest CE year"
      - pred: "pleiades:end_date"
        range: "xsd:string"
        comment: "Latest CE year"
```

```yaml
# linked_past/datasets/pleiades/context/examples.yaml
examples:
  - question: "Find all places with their coordinates"
    sparql: |
      PREFIX pleiades: <https://pleiades.stoa.org/places/vocab#>
      PREFIX geo: <http://www.w3.org/2003/01/geo/wgs84_pos#>
      PREFIX dcterms: <http://purl.org/dc/terms/>
      SELECT ?place ?title ?lat ?long
      WHERE {
        ?place a pleiades:Place ;
               dcterms:title ?title ;
               pleiades:hasLocation ?loc .
        ?loc geo:lat ?lat ;
             geo:long ?long .
      }
      LIMIT 100

  - question: "Find places with their ancient names and time periods"
    sparql: |
      PREFIX pleiades: <https://pleiades.stoa.org/places/vocab#>
      PREFIX dcterms: <http://purl.org/dc/terms/>
      PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
      SELECT ?place ?title ?attested ?romanized ?periodLabel
      WHERE {
        ?place a pleiades:Place ;
               dcterms:title ?title ;
               pleiades:hasName ?name .
        OPTIONAL { ?name pleiades:nameAttested ?attested }
        OPTIONAL { ?name pleiades:nameRomanized ?romanized }
        OPTIONAL { ?name pleiades:during ?period .
                   ?period skos:prefLabel ?periodLabel }
      }
      LIMIT 100

  - question: "Find all settlements"
    sparql: |
      PREFIX pleiades: <https://pleiades.stoa.org/places/vocab#>
      PREFIX dcterms: <http://purl.org/dc/terms/>
      PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
      SELECT ?place ?title ?featureType
      WHERE {
        ?place a pleiades:Place ;
               dcterms:title ?title ;
               pleiades:hasFeatureType ?ft .
        ?ft skos:prefLabel ?featureType .
        FILTER(CONTAINS(LCASE(?featureType), "settlement"))
      }

  - question: "Find places active during the Roman period"
    sparql: |
      PREFIX pleiades: <https://pleiades.stoa.org/places/vocab#>
      PREFIX dcterms: <http://purl.org/dc/terms/>
      PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
      PREFIX geo: <http://www.w3.org/2003/01/geo/wgs84_pos#>
      SELECT ?place ?title ?lat ?long
      WHERE {
        ?place a pleiades:Place ;
               dcterms:title ?title ;
               pleiades:hasLocation ?loc .
        ?loc pleiades:during ?period ;
             geo:lat ?lat ;
             geo:long ?long .
        ?period skos:prefLabel ?periodLabel .
        FILTER(CONTAINS(LCASE(?periodLabel), "roman"))
      }

  - question: "Find places with GeoJSON geometry"
    sparql: |
      PREFIX pleiades: <https://pleiades.stoa.org/places/vocab#>
      PREFIX osgeo: <http://data.ordnancesurvey.co.uk/ontology/geometry/>
      PREFIX dcterms: <http://purl.org/dc/terms/>
      SELECT ?place ?title ?geojson
      WHERE {
        ?place a pleiades:Place ;
               dcterms:title ?title ;
               pleiades:hasLocation ?loc .
        ?loc osgeo:asGeoJSON ?geojson .
      }
      LIMIT 100
```

```yaml
# linked_past/datasets/pleiades/context/tips.yaml
tips:
  - title: "coordinates_on_location"
    body: "Coordinates (geo:lat, geo:long) are on Location entities, not Place. Always join through pleiades:hasLocation to reach coordinates."
    classes: ["Place", "Location"]

  - title: "time_periods_are_concepts"
    body: "pleiades:during links to a skos:Concept with a skos:prefLabel like 'Roman' or 'Hellenistic'. These are not date literals. Use start_date/end_date for numeric year filtering."
    classes: ["Location", "Name"]

  - title: "feature_types_need_vocab"
    body: "pleiades:hasFeatureType links to URIs from a controlled vocabulary. The label is accessible via skos:prefLabel on the feature type concept."
    classes: ["Place"]

  - title: "place_uris_use_https"
    body: "Pleiades place URIs use HTTPS: https://pleiades.stoa.org/places/{ID}. Ensure you use HTTPS in FILTER or URI comparisons."
    classes: []

  - title: "multiple_locations_per_place"
    body: "A Place may have multiple Locations for different time periods or accuracy levels. Use OPTIONAL or accept multiple rows per place."
    classes: ["Place", "Location"]
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_pleiades_plugin.py
from pathlib import Path

from linked_past.datasets.pleiades.plugin import PleiadesPlugin


SAMPLE_PLEIADES_TURTLE = """\
@prefix pleiades: <https://pleiades.stoa.org/places/vocab#> .
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix geo: <http://www.w3.org/2003/01/geo/wgs84_pos#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .

<https://pleiades.stoa.org/places/423025> a pleiades:Place ;
    dcterms:title "Roma" ;
    pleiades:hasLocation <https://pleiades.stoa.org/places/423025/location1> .

<https://pleiades.stoa.org/places/423025/location1> a pleiades:Location ;
    geo:lat "41.891775"^^<http://www.w3.org/2001/XMLSchema#float> ;
    geo:long "12.486137"^^<http://www.w3.org/2001/XMLSchema#float> .
"""


def test_pleiades_plugin_attributes():
    plugin = PleiadesPlugin()
    assert plugin.name == "pleiades"
    assert "Pleiades" in plugin.display_name
    assert plugin.license == "CC BY 3.0"


def test_pleiades_plugin_prefixes():
    plugin = PleiadesPlugin()
    prefixes = plugin.get_prefixes()
    assert "pleiades" in prefixes
    assert prefixes["pleiades"] == "https://pleiades.stoa.org/places/vocab#"


def test_pleiades_plugin_schema():
    plugin = PleiadesPlugin()
    schema = plugin.get_schema()
    assert "Place" in schema
    assert "Location" in schema
    assert "Name" in schema


def test_pleiades_plugin_validate_valid():
    plugin = PleiadesPlugin()
    result = plugin.validate(
        "PREFIX pleiades: <https://pleiades.stoa.org/places/vocab#>\n"
        "PREFIX dcterms: <http://purl.org/dc/terms/>\n"
        "SELECT ?p ?title WHERE { ?p a pleiades:Place ; dcterms:title ?title }",
    )
    assert result.valid is True


def test_pleiades_plugin_validate_invalid():
    plugin = PleiadesPlugin()
    result = plugin.validate(
        "PREFIX pleiades: <https://pleiades.stoa.org/places/vocab#>\n"
        "SELECT ?p WHERE { ?p a pleiades:City }",
    )
    assert result.valid is False
    assert any("Unknown class" in e for e in result.errors)


def test_pleiades_plugin_load(tmp_path):
    from linked_past.core.store import create_store

    plugin = PleiadesPlugin()
    ttl = tmp_path / "pleiades.ttl"
    ttl.write_text(SAMPLE_PLEIADES_TURTLE)
    store = create_store(tmp_path / "store")
    count = plugin.load(store, ttl)
    assert count > 0


def test_pleiades_plugin_oci_attributes():
    plugin = PleiadesPlugin()
    assert plugin.oci_dataset == "pleiades"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_pleiades_plugin.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Write the plugin**

```python
# linked_past/datasets/pleiades/__init__.py
```

```python
# linked_past/datasets/pleiades/plugin.py
"""Pleiades ancient places gazetteer dataset plugin."""

from __future__ import annotations

from pathlib import Path

from linked_past.core.context import (
    get_cross_cutting_tips,
    get_relevant_examples,
    get_relevant_tips,
    load_examples,
    load_prefixes,
    load_schemas,
    load_tips,
    render_class_summary,
    render_examples,
    render_tips,
)
from linked_past.core.validate import build_schema_dict, extract_query_classes, validate_semantics
from linked_past.datasets.base import DatasetPlugin, ValidationResult, VersionInfo

_CONTEXT_DIR = Path(__file__).parent / "context"


class PleiadesPlugin(DatasetPlugin):
    name = "pleiades"
    display_name = "Pleiades: A Gazetteer of Past Places"
    description = (
        "A community-built gazetteer of ancient places covering the Greek, Roman, "
        "Egyptian, and Near Eastern worlds. ~41,000 place resources with coordinates, "
        "ancient names, time periods, and feature type classifications."
    )
    citation = (
        "Bagnall, R. et al. (eds.), Pleiades: A Gazetteer of Past Places, "
        "https://pleiades.stoa.org/. DOI: 10.5281/zenodo.1193921"
    )
    license = "CC BY 3.0"
    url = "https://pleiades.stoa.org"
    time_coverage = "Archaic through Late Antique"
    spatial_coverage = "Mediterranean, Near East, Central Asia"
    oci_dataset = "pleiades"
    oci_version = "latest"

    def __init__(self):
        self._prefixes = load_prefixes(_CONTEXT_DIR)
        self._schemas = load_schemas(_CONTEXT_DIR)
        self._examples = load_examples(_CONTEXT_DIR)
        self._tips = load_tips(_CONTEXT_DIR)
        self._schema_dict = build_schema_dict(self._schemas, self._prefixes)
        for ex in self._examples:
            ex["classes"] = extract_query_classes(ex["sparql"], self._schema_dict)

    def get_prefixes(self) -> dict[str, str]:
        return self._prefixes

    def build_schema_dict(self) -> dict:
        return self._schema_dict

    def get_schema(self) -> str:
        prefix_lines = "\n".join(f"PREFIX {k}: <{v}>" for k, v in self._prefixes.items())
        class_summary = render_class_summary(self._schemas)
        cross_tips = get_cross_cutting_tips(self._tips)
        tips_md = render_tips(cross_tips)
        return (
            f"## Prefixes\n\n```sparql\n{prefix_lines}\n```\n\n"
            f"## Classes\n\n{class_summary}\n\n"
            f"## General Tips\n\n{tips_md}"
        )

    def validate(self, sparql: str) -> ValidationResult:
        errors = validate_semantics(sparql, self._schema_dict)
        if errors:
            return ValidationResult(valid=False, sparql=sparql, errors=errors)
        return ValidationResult(valid=True, sparql=sparql)

    def get_relevant_context(self, sparql: str) -> str:
        classes = extract_query_classes(sparql, self._schema_dict)
        if not classes:
            return ""
        parts: list[str] = []
        tips = get_relevant_tips(self._tips, classes)
        if tips:
            parts.append(f"## Relevant Tips\n\n{render_tips(tips)}")
        examples = get_relevant_examples(self._examples, classes)
        if examples:
            parts.append(f"## Relevant Examples\n\n{render_examples(examples)}")
        if not parts:
            return ""
        return "\n\n---\n\n" + "\n\n".join(parts)

    def get_version_info(self, data_dir: Path) -> VersionInfo:
        return VersionInfo(
            version=self.oci_version,
            source_url=f"https://pleiades.stoa.org/downloads",
            fetched_at="",
            triple_count=0,
            rdf_format="turtle",
        )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_pleiades_plugin.py -v`
Expected: PASS (7 tests)

- [ ] **Step 6: Commit**

```bash
git add linked_past/datasets/pleiades/ tests/test_pleiades_plugin.py
git commit -m "feat: add Pleiades dataset plugin with context files"
```

---

### Task 3: PeriodO dataset plugin

**Files:**
- Create: `linked_past/datasets/periodo/__init__.py`
- Create: `linked_past/datasets/periodo/plugin.py`
- Create: `linked_past/datasets/periodo/context/schemas.yaml`
- Create: `linked_past/datasets/periodo/context/examples.yaml`
- Create: `linked_past/datasets/periodo/context/tips.yaml`
- Create: `linked_past/datasets/periodo/context/prefixes.yaml`
- Test: `tests/test_periodo_plugin.py`

- [ ] **Step 1: Create context YAML files**

```yaml
# linked_past/datasets/periodo/context/prefixes.yaml
prefixes:
  periodo: "http://n2t.net/ark:/99152/p0v#"
  skos: "http://www.w3.org/2004/02/skos/core#"
  time: "http://www.w3.org/2006/time#"
  dcterms: "http://purl.org/dc/terms/"
  owl: "http://www.w3.org/2002/07/owl#"
  xsd: "http://www.w3.org/2001/XMLSchema#"
  rdf: "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
  rdfs: "http://www.w3.org/2000/01/rdf-schema#"
```

```yaml
# linked_past/datasets/periodo/context/schemas.yaml
classes:
  Period:
    label: "Period"
    comment: "A named historical time period as defined by a specific scholarly source. Dual-typed as skos:Concept and time:ProperInterval. Multiple authorities may define the same period name with different temporal bounds."
    uri: "skos:Concept"
    properties:
      - pred: "skos:prefLabel"
        range: "xsd:string"
        comment: "Period name exactly as in source (e.g., 'Bronze Age', 'Roman Republic')"
      - pred: "skos:inScheme"
        range: "skos:ConceptScheme"
        comment: "Links to the authority (scholarly source) that defines this period"
      - pred: "time:intervalStartedBy"
        range: "time:ProperInterval"
        comment: "Start interval — chain through time:hasDateTimeDescription to get time:year"
      - pred: "time:intervalFinishedBy"
        range: "time:ProperInterval"
        comment: "Stop interval — chain through time:hasDateTimeDescription to get time:year"
      - pred: "periodo:spatialCoverageDescription"
        range: "xsd:string"
        comment: "Free-text spatial scope from source"
      - pred: "periodo:spatialCoverage"
        range: "xsd:anyURI"
        comment: "Linked spatial entity (DBpedia, Wikidata, Pleiades URI)"
      - pred: "owl:sameAs"
        range: "xsd:anyURI"
        comment: "Equivalent period in another vocabulary"

  Authority:
    label: "Authority"
    comment: "A scholarly source that defines one or more periods. Each authority groups periods from a single bibliographic reference."
    uri: "skos:ConceptScheme"
    properties:
      - pred: "dcterms:source"
        range: "xsd:anyURI"
        comment: "Bibliographic source node — chain to dcterms:title for the title"
```

```yaml
# linked_past/datasets/periodo/context/examples.yaml
examples:
  - question: "List all periods with their labels"
    sparql: |
      PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
      PREFIX time: <http://www.w3.org/2006/time#>
      SELECT ?period ?label
      WHERE {
        ?period a skos:Concept ;
                a time:ProperInterval ;
                skos:prefLabel ?label .
      }
      LIMIT 100

  - question: "Find periods with their authority and source publication"
    sparql: |
      PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
      PREFIX dcterms: <http://purl.org/dc/terms/>
      SELECT ?period ?periodLabel ?scheme ?sourceTitle
      WHERE {
        ?period a skos:Concept ;
                skos:prefLabel ?periodLabel ;
                skos:inScheme ?scheme .
        ?scheme dcterms:source ?source .
        ?source dcterms:title ?sourceTitle .
      }
      LIMIT 100

  - question: "Get the temporal extent (start and stop years) of periods"
    sparql: |
      PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
      PREFIX time: <http://www.w3.org/2006/time#>
      SELECT ?period ?label ?startYear ?stopYear
      WHERE {
        ?period a skos:Concept ;
                skos:prefLabel ?label ;
                time:intervalStartedBy ?startInterval ;
                time:intervalFinishedBy ?stopInterval .
        ?startInterval time:hasDateTimeDescription ?startDesc .
        ?startDesc time:year ?startYear .
        ?stopInterval time:hasDateTimeDescription ?stopDesc .
        ?stopDesc time:year ?stopYear .
      }

  - question: "Find all definitions of 'Bronze Age' across different authorities"
    sparql: |
      PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
      PREFIX dcterms: <http://purl.org/dc/terms/>
      PREFIX time: <http://www.w3.org/2006/time#>
      SELECT ?period ?label ?sourceTitle ?startYear ?stopYear
      WHERE {
        ?period a skos:Concept ;
                skos:prefLabel ?label ;
                skos:inScheme ?scheme .
        ?scheme dcterms:source ?src .
        ?src dcterms:title ?sourceTitle .
        FILTER CONTAINS(LCASE(?label), "bronze age")
        OPTIONAL {
          ?period time:intervalStartedBy/time:hasDateTimeDescription/time:year ?startYear
        }
        OPTIONAL {
          ?period time:intervalFinishedBy/time:hasDateTimeDescription/time:year ?stopYear
        }
      }
      ORDER BY ?startYear

  - question: "Find periods overlapping a date range (500-300 BC)"
    sparql: |
      PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
      PREFIX time: <http://www.w3.org/2006/time#>
      PREFIX periodo: <http://n2t.net/ark:/99152/p0v#>
      PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
      SELECT ?period ?label ?effectiveStart ?effectiveStop
      WHERE {
        ?period a skos:Concept ;
                skos:prefLabel ?label ;
                time:intervalStartedBy ?startInterval ;
                time:intervalFinishedBy ?stopInterval .
        ?startInterval time:hasDateTimeDescription ?startDesc .
        ?stopInterval time:hasDateTimeDescription ?stopDesc .
        OPTIONAL { ?startDesc time:year ?startExact }
        OPTIONAL { ?startDesc periodo:earliestYear ?startEarliest }
        BIND(COALESCE(?startExact, ?startEarliest) AS ?effectiveStart)
        OPTIONAL { ?stopDesc time:year ?stopExact }
        OPTIONAL { ?stopDesc periodo:latestYear ?stopLatest }
        BIND(COALESCE(?stopExact, ?stopLatest) AS ?effectiveStop)
        FILTER (
          ?effectiveStart <= "-0300"^^xsd:gYear &&
          ?effectiveStop >= "-0500"^^xsd:gYear
        )
      }
      ORDER BY ?effectiveStart
```

```yaml
# linked_past/datasets/periodo/context/tips.yaml
tips:
  - title: "year_encoding"
    body: "PeriodO uses ISO 8601 proleptic Gregorian years as xsd:gYear. '400 BC' = '-0399' (year 0 = 1 BC). Watch for off-by-one errors."
    classes: ["Period"]

  - title: "dual_temporal_encoding"
    body: "Some periods use time:year (exact), others use periodo:earliestYear/periodo:latestYear (ranges like 'eighth century BC'). Use COALESCE to handle both in date filters."
    classes: ["Period"]

  - title: "multiple_definitions_by_design"
    body: "The same period name (e.g., 'Bronze Age') appears many times with different date ranges from different authorities. Always include skos:inScheme to disambiguate or group by authority."
    classes: ["Period", "Authority"]

  - title: "gyear_comparison"
    body: "Date filters require explicit xsd:gYear cast: FILTER (?startYear <= \"-0300\"^^xsd:gYear). Without the cast, comparison may not work correctly."
    classes: ["Period"]

  - title: "temporal_chain"
    body: "To get years from a period, chain: time:intervalStartedBy -> time:hasDateTimeDescription -> time:year. This is a 3-step property path, not a direct property on the period."
    classes: ["Period"]
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_periodo_plugin.py
from pathlib import Path

from linked_past.datasets.periodo.plugin import PeriodOPlugin


SAMPLE_PERIODO_TURTLE = """\
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix time: <http://www.w3.org/2006/time#> .
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

<http://n2t.net/ark:/99152/p06v8w4> a skos:ConceptScheme ;
    dcterms:source [ dcterms:title "FastiOnline" ] .

<http://n2t.net/ark:/99152/p05krdxmkzt> a skos:Concept, time:ProperInterval ;
    skos:prefLabel "Roman Republic" ;
    skos:inScheme <http://n2t.net/ark:/99152/p06v8w4> ;
    time:intervalStartedBy [ a time:ProperInterval ;
        time:hasDateTimeDescription [ time:year "-0508"^^xsd:gYear ] ] ;
    time:intervalFinishedBy [ a time:ProperInterval ;
        time:hasDateTimeDescription [ time:year "-0030"^^xsd:gYear ] ] .
"""


def test_periodo_plugin_attributes():
    plugin = PeriodOPlugin()
    assert plugin.name == "periodo"
    assert "PeriodO" in plugin.display_name
    assert plugin.license == "CC0"


def test_periodo_plugin_prefixes():
    plugin = PeriodOPlugin()
    prefixes = plugin.get_prefixes()
    assert "periodo" in prefixes
    assert "skos" in prefixes
    assert "time" in prefixes


def test_periodo_plugin_schema():
    plugin = PeriodOPlugin()
    schema = plugin.get_schema()
    assert "Period" in schema
    assert "Authority" in schema


def test_periodo_plugin_validate_valid():
    plugin = PeriodOPlugin()
    result = plugin.validate(
        "PREFIX skos: <http://www.w3.org/2004/02/skos/core#>\n"
        "PREFIX time: <http://www.w3.org/2006/time#>\n"
        "SELECT ?p ?label WHERE { ?p a skos:Concept ; skos:prefLabel ?label }",
    )
    assert result.valid is True


def test_periodo_plugin_load(tmp_path):
    from linked_past.core.store import create_store

    plugin = PeriodOPlugin()
    ttl = tmp_path / "periodo.ttl"
    ttl.write_text(SAMPLE_PERIODO_TURTLE)
    store = create_store(tmp_path / "store")
    count = plugin.load(store, ttl)
    assert count > 0


def test_periodo_plugin_oci_attributes():
    plugin = PeriodOPlugin()
    assert plugin.oci_dataset == "periodo"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_periodo_plugin.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Write the plugin**

```python
# linked_past/datasets/periodo/__init__.py
```

```python
# linked_past/datasets/periodo/plugin.py
"""PeriodO period gazetteer dataset plugin."""

from __future__ import annotations

from pathlib import Path

from linked_past.core.context import (
    get_cross_cutting_tips,
    get_relevant_examples,
    get_relevant_tips,
    load_examples,
    load_prefixes,
    load_schemas,
    load_tips,
    render_class_summary,
    render_examples,
    render_tips,
)
from linked_past.core.validate import build_schema_dict, extract_query_classes, validate_semantics
from linked_past.datasets.base import DatasetPlugin, ValidationResult, VersionInfo

_CONTEXT_DIR = Path(__file__).parent / "context"


class PeriodOPlugin(DatasetPlugin):
    name = "periodo"
    display_name = "PeriodO: A Gazetteer of Period Definitions"
    description = (
        "A gazetteer of scholarly definitions of historical, art-historical, and "
        "archaeological periods. Each entry records how a specific published source "
        "defines a named period with temporal bounds and spatial coverage. "
        "~9,000 periods from ~270 authorities."
    )
    citation = (
        "Golden, P. & Shaw, R. (2016). PeriodO, https://perio.do/. "
        "PeerJ Computer Science 2:e44"
    )
    license = "CC0"
    url = "https://perio.do"
    time_coverage = "All periods (prehistoric through modern)"
    spatial_coverage = "Global"
    oci_dataset = "periodo"
    oci_version = "latest"

    def __init__(self):
        self._prefixes = load_prefixes(_CONTEXT_DIR)
        self._schemas = load_schemas(_CONTEXT_DIR)
        self._examples = load_examples(_CONTEXT_DIR)
        self._tips = load_tips(_CONTEXT_DIR)
        self._schema_dict = build_schema_dict(self._schemas, self._prefixes)
        for ex in self._examples:
            ex["classes"] = extract_query_classes(ex["sparql"], self._schema_dict)

    def get_prefixes(self) -> dict[str, str]:
        return self._prefixes

    def build_schema_dict(self) -> dict:
        return self._schema_dict

    def get_schema(self) -> str:
        prefix_lines = "\n".join(f"PREFIX {k}: <{v}>" for k, v in self._prefixes.items())
        class_summary = render_class_summary(self._schemas)
        cross_tips = get_cross_cutting_tips(self._tips)
        tips_md = render_tips(cross_tips)
        return (
            f"## Prefixes\n\n```sparql\n{prefix_lines}\n```\n\n"
            f"## Classes\n\n{class_summary}\n\n"
            f"## General Tips\n\n{tips_md}"
        )

    def validate(self, sparql: str) -> ValidationResult:
        errors = validate_semantics(sparql, self._schema_dict)
        if errors:
            return ValidationResult(valid=False, sparql=sparql, errors=errors)
        return ValidationResult(valid=True, sparql=sparql)

    def get_relevant_context(self, sparql: str) -> str:
        classes = extract_query_classes(sparql, self._schema_dict)
        if not classes:
            return ""
        parts: list[str] = []
        tips = get_relevant_tips(self._tips, classes)
        if tips:
            parts.append(f"## Relevant Tips\n\n{render_tips(tips)}")
        examples = get_relevant_examples(self._examples, classes)
        if examples:
            parts.append(f"## Relevant Examples\n\n{render_examples(examples)}")
        if not parts:
            return ""
        return "\n\n---\n\n" + "\n\n".join(parts)

    def get_version_info(self, data_dir: Path) -> VersionInfo:
        return VersionInfo(
            version=self.oci_version,
            source_url="http://n2t.net/ark:/99152/p0d.jsonld",
            fetched_at="",
            triple_count=0,
            rdf_format="turtle",
        )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_periodo_plugin.py -v`
Expected: PASS (6 tests)

- [ ] **Step 6: Commit**

```bash
git add linked_past/datasets/periodo/ tests/test_periodo_plugin.py
git commit -m "feat: add PeriodO dataset plugin with context files"
```

---

### Task 4: Nomisma dataset plugin

**Files:**
- Create: `linked_past/datasets/nomisma/__init__.py`
- Create: `linked_past/datasets/nomisma/plugin.py`
- Create: `linked_past/datasets/nomisma/context/schemas.yaml`
- Create: `linked_past/datasets/nomisma/context/examples.yaml`
- Create: `linked_past/datasets/nomisma/context/tips.yaml`
- Create: `linked_past/datasets/nomisma/context/prefixes.yaml`
- Test: `tests/test_nomisma_plugin.py`

- [ ] **Step 1: Create context YAML files**

```yaml
# linked_past/datasets/nomisma/context/prefixes.yaml
prefixes:
  nmo: "http://nomisma.org/ontology#"
  nm: "http://nomisma.org/id/"
  skos: "http://www.w3.org/2004/02/skos/core#"
  foaf: "http://xmlns.com/foaf/0.1/"
  dcterms: "http://purl.org/dc/terms/"
  geo: "http://www.w3.org/2003/01/geo/wgs84_pos#"
  org: "http://www.w3.org/ns/org#"
  rdfs: "http://www.w3.org/2000/01/rdf-schema#"
  rdf: "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
  xsd: "http://www.w3.org/2001/XMLSchema#"
```

```yaml
# linked_past/datasets/nomisma/context/schemas.yaml
classes:
  Person:
    label: "Person"
    comment: "A historical figure (emperor, magistrate, moneyer) relevant to numismatics. Uses foaf:Person type. Roles modeled via org:hasMembership pattern."
    uri: "foaf:Person"
    properties:
      - pred: "skos:prefLabel"
        range: "xsd:string"
        comment: "Preferred label (language-tagged, filter with langMatches)"
      - pred: "skos:definition"
        range: "xsd:string"
        comment: "Definition text"
      - pred: "org:hasMembership"
        range: "org:Membership"
        comment: "Links to membership with org:role and org:organization"
      - pred: "skos:exactMatch"
        range: "xsd:anyURI"
        comment: "Links to Wikidata, VIAF, GND, etc."
      - pred: "skos:closeMatch"
        range: "xsd:anyURI"
        comment: "Approximate match to external authorities"

  Mint:
    label: "Mint"
    comment: "A coin minting location. Has geographic coordinates and links to Pleiades via skos:closeMatch."
    uri: "nmo:Mint"
    properties:
      - pred: "skos:prefLabel"
        range: "xsd:string"
        comment: "Mint name (language-tagged)"
      - pred: "skos:definition"
        range: "xsd:string"
        comment: "Description"
      - pred: "geo:location"
        range: "geo:SpatialThing"
        comment: "Location node — chain to geo:lat/geo:long for coordinates"
      - pred: "skos:closeMatch"
        range: "xsd:anyURI"
        comment: "Links to Pleiades, Wikidata, etc."
      - pred: "skos:broader"
        range: "nmo:Region"
        comment: "Parent region"
      - pred: "dcterms:isPartOf"
        range: "xsd:anyURI"
        comment: "Discipline hierarchy (nm:roman_numismatics, nm:greek_numismatics)"

  Region:
    label: "Region"
    comment: "A geographic/administrative region containing mints."
    uri: "nmo:Region"
    properties:
      - pred: "skos:prefLabel"
        range: "xsd:string"
        comment: "Region name"
      - pred: "geo:location"
        range: "geo:SpatialThing"
        comment: "Location node with coordinates"

  Denomination:
    label: "Denomination"
    comment: "A coin denomination (denarius, aureus, sestertius, etc.)."
    uri: "nmo:Denomination"
    properties:
      - pred: "skos:prefLabel"
        range: "xsd:string"
        comment: "Denomination name"
      - pred: "skos:definition"
        range: "xsd:string"
        comment: "Description"

  Material:
    label: "Material"
    comment: "Coin material (gold/av, silver/ar, bronze/ae, etc.)."
    uri: "nmo:Material"
    properties:
      - pred: "skos:prefLabel"
        range: "xsd:string"
        comment: "Material name"
```

```yaml
# linked_past/datasets/nomisma/context/examples.yaml
examples:
  - question: "List all Roman Emperors"
    sparql: |
      PREFIX foaf: <http://xmlns.com/foaf/0.1/>
      PREFIX nm: <http://nomisma.org/id/>
      PREFIX org: <http://www.w3.org/ns/org#>
      PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
      SELECT ?person ?label
      WHERE {
        ?person a foaf:Person ;
                skos:prefLabel ?label ;
                org:hasMembership ?membership .
        ?membership org:role nm:roman_emperor .
        FILTER(langMatches(lang(?label), "EN"))
      }

  - question: "Find mints with Pleiades links"
    sparql: |
      PREFIX nmo: <http://nomisma.org/ontology#>
      PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
      SELECT ?mint ?label ?pleiadesURI
      WHERE {
        ?mint a nmo:Mint ;
              skos:prefLabel ?label ;
              skos:closeMatch ?pleiadesURI .
        FILTER(STRSTARTS(STR(?pleiadesURI), "https://pleiades.stoa.org/places/"))
        FILTER(langMatches(lang(?label), "EN"))
      }

  - question: "Find all mints with coordinates"
    sparql: |
      PREFIX nmo: <http://nomisma.org/ontology#>
      PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
      PREFIX geo: <http://www.w3.org/2003/01/geo/wgs84_pos#>
      SELECT ?mint ?label ?lat ?long
      WHERE {
        ?mint a nmo:Mint ;
              skos:prefLabel ?label ;
              geo:location ?loc .
        ?loc geo:lat ?lat ;
             geo:long ?long .
        FILTER(langMatches(lang(?label), "EN"))
      }

  - question: "List persons with their roles in the Roman Empire"
    sparql: |
      PREFIX foaf: <http://xmlns.com/foaf/0.1/>
      PREFIX nm: <http://nomisma.org/id/>
      PREFIX nmo: <http://nomisma.org/ontology#>
      PREFIX org: <http://www.w3.org/ns/org#>
      PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
      SELECT ?person ?label ?roleLabel ?begin ?end
      WHERE {
        ?person a foaf:Person ;
                skos:prefLabel ?label ;
                org:hasMembership ?membership .
        ?membership org:organization nm:roman_empire .
        OPTIONAL { ?membership org:role ?role .
                   ?role skos:prefLabel ?roleLabel
                   FILTER(langMatches(lang(?roleLabel), "EN")) }
        OPTIONAL { ?membership nmo:hasStartDate ?begin }
        OPTIONAL { ?membership nmo:hasEndDate ?end }
        FILTER(langMatches(lang(?label), "EN"))
      }
      ORDER BY ?begin

  - question: "List all coin denominations"
    sparql: |
      PREFIX nmo: <http://nomisma.org/ontology#>
      PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
      SELECT ?denomination ?label ?definition
      WHERE {
        ?denomination a nmo:Denomination ;
                      skos:prefLabel ?label .
        OPTIONAL { ?denomination skos:definition ?definition
                   FILTER(langMatches(lang(?definition), "EN")) }
        FILTER(langMatches(lang(?label), "EN"))
      }
      ORDER BY ?label
```

```yaml
# linked_past/datasets/nomisma/context/tips.yaml
tips:
  - title: "language_tagged_labels"
    body: "Labels are language-tagged. Always filter with FILTER(langMatches(lang(?label), \"EN\")) to get English labels. Without this filter, you'll get duplicate results in multiple languages."
    classes: ["Person", "Mint", "Region", "Denomination", "Material"]

  - title: "person_role_pattern"
    body: "Person roles use the W3C Organization vocabulary pattern, NOT a direct property. Chain: ?person org:hasMembership ?m . ?m org:role nm:roman_emperor . ?m org:organization nm:roman_empire ."
    classes: ["Person"]

  - title: "deprecated_records"
    body: "Filter out deprecated concepts with FILTER NOT EXISTS { ?x dcterms:isReplacedBy ?y }. Some concepts have been superseded."
    classes: []

  - title: "concept_vocab_scope"
    body: "This local store contains the Nomisma concept vocabulary only (persons, mints, denominations, materials, regions). Physical coins (nmo:NumismaticObject) and hoards are in partner datasets available via the live SPARQL endpoint at http://nomisma.org/sparql/."
    classes: []

  - title: "mint_coordinates_via_location"
    body: "Mint coordinates are not direct properties. Chain: ?mint geo:location ?loc . ?loc geo:lat ?lat ; geo:long ?long ."
    classes: ["Mint", "Region"]
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_nomisma_plugin.py
from pathlib import Path

from linked_past.datasets.nomisma.plugin import NomismaPlugin


SAMPLE_NOMISMA_TURTLE = """\
@prefix nmo: <http://nomisma.org/ontology#> .
@prefix nm: <http://nomisma.org/id/> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix foaf: <http://xmlns.com/foaf/0.1/> .
@prefix geo: <http://www.w3.org/2003/01/geo/wgs84_pos#> .
@prefix org: <http://www.w3.org/ns/org#> .

nm:augustus a foaf:Person, skos:Concept ;
    skos:prefLabel "Augustus"@en ;
    org:hasMembership [ org:role nm:roman_emperor ;
                        org:organization nm:roman_empire ] .

nm:rome a nmo:Mint, skos:Concept ;
    skos:prefLabel "Rome"@en ;
    geo:location [ geo:lat "41.8933"^^<http://www.w3.org/2001/XMLSchema#float> ;
                   geo:long "12.4831"^^<http://www.w3.org/2001/XMLSchema#float> ] .

nm:denarius a nmo:Denomination, skos:Concept ;
    skos:prefLabel "Denarius"@en .
"""


def test_nomisma_plugin_attributes():
    plugin = NomismaPlugin()
    assert plugin.name == "nomisma"
    assert "Nomisma" in plugin.display_name
    assert plugin.license == "CC BY"


def test_nomisma_plugin_prefixes():
    plugin = NomismaPlugin()
    prefixes = plugin.get_prefixes()
    assert "nmo" in prefixes
    assert "nm" in prefixes
    assert prefixes["nmo"] == "http://nomisma.org/ontology#"


def test_nomisma_plugin_schema():
    plugin = NomismaPlugin()
    schema = plugin.get_schema()
    assert "Person" in schema
    assert "Mint" in schema
    assert "Denomination" in schema


def test_nomisma_plugin_validate_valid():
    plugin = NomismaPlugin()
    result = plugin.validate(
        "PREFIX nmo: <http://nomisma.org/ontology#>\n"
        "PREFIX skos: <http://www.w3.org/2004/02/skos/core#>\n"
        "SELECT ?m ?label WHERE { ?m a nmo:Mint ; skos:prefLabel ?label }",
    )
    assert result.valid is True


def test_nomisma_plugin_validate_invalid():
    plugin = NomismaPlugin()
    result = plugin.validate(
        "PREFIX nmo: <http://nomisma.org/ontology#>\n"
        "SELECT ?m WHERE { ?m a nmo:Coin }",
    )
    assert result.valid is False


def test_nomisma_plugin_load(tmp_path):
    from linked_past.core.store import create_store

    plugin = NomismaPlugin()
    ttl = tmp_path / "nomisma.ttl"
    ttl.write_text(SAMPLE_NOMISMA_TURTLE)
    store = create_store(tmp_path / "store")
    count = plugin.load(store, ttl)
    assert count > 0


def test_nomisma_plugin_oci_attributes():
    plugin = NomismaPlugin()
    assert plugin.oci_dataset == "nomisma"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_nomisma_plugin.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Write the plugin**

```python
# linked_past/datasets/nomisma/__init__.py
```

```python
# linked_past/datasets/nomisma/plugin.py
"""Nomisma numismatic linked data dataset plugin."""

from __future__ import annotations

from pathlib import Path

from linked_past.core.context import (
    get_cross_cutting_tips,
    get_relevant_examples,
    get_relevant_tips,
    load_examples,
    load_prefixes,
    load_schemas,
    load_tips,
    render_class_summary,
    render_examples,
    render_tips,
)
from linked_past.core.validate import build_schema_dict, extract_query_classes, validate_semantics
from linked_past.datasets.base import DatasetPlugin, ValidationResult, VersionInfo

_CONTEXT_DIR = Path(__file__).parent / "context"


class NomismaPlugin(DatasetPlugin):
    name = "nomisma"
    display_name = "Nomisma: Numismatic Linked Open Data"
    description = (
        "Stable digital representations of numismatic concepts as Linked Open Data. "
        "Provides URIs for mints, denominations, materials, persons (rulers/authorities), "
        "and regions relevant to ancient coinage. Concept vocabulary only — physical coins "
        "are available via the live SPARQL endpoint at nomisma.org/sparql/."
    )
    citation = (
        "Gruber, E. & Meadows, A. (2021). Numismatics and Linked Open Data. "
        "ISAW Papers 20.6. https://nomisma.org/"
    )
    license = "CC BY"
    url = "https://nomisma.org"
    time_coverage = "Ancient through medieval"
    spatial_coverage = "Mediterranean, Europe, Near East"
    oci_dataset = "nomisma"
    oci_version = "latest"

    def __init__(self):
        self._prefixes = load_prefixes(_CONTEXT_DIR)
        self._schemas = load_schemas(_CONTEXT_DIR)
        self._examples = load_examples(_CONTEXT_DIR)
        self._tips = load_tips(_CONTEXT_DIR)
        self._schema_dict = build_schema_dict(self._schemas, self._prefixes)
        for ex in self._examples:
            ex["classes"] = extract_query_classes(ex["sparql"], self._schema_dict)

    def get_prefixes(self) -> dict[str, str]:
        return self._prefixes

    def build_schema_dict(self) -> dict:
        return self._schema_dict

    def get_schema(self) -> str:
        prefix_lines = "\n".join(f"PREFIX {k}: <{v}>" for k, v in self._prefixes.items())
        class_summary = render_class_summary(self._schemas)
        cross_tips = get_cross_cutting_tips(self._tips)
        tips_md = render_tips(cross_tips)
        return (
            f"## Prefixes\n\n```sparql\n{prefix_lines}\n```\n\n"
            f"## Classes\n\n{class_summary}\n\n"
            f"## General Tips\n\n{tips_md}"
        )

    def validate(self, sparql: str) -> ValidationResult:
        errors = validate_semantics(sparql, self._schema_dict)
        if errors:
            return ValidationResult(valid=False, sparql=sparql, errors=errors)
        return ValidationResult(valid=True, sparql=sparql)

    def get_relevant_context(self, sparql: str) -> str:
        classes = extract_query_classes(sparql, self._schema_dict)
        if not classes:
            return ""
        parts: list[str] = []
        tips = get_relevant_tips(self._tips, classes)
        if tips:
            parts.append(f"## Relevant Tips\n\n{render_tips(tips)}")
        examples = get_relevant_examples(self._examples, classes)
        if examples:
            parts.append(f"## Relevant Examples\n\n{render_examples(examples)}")
        if not parts:
            return ""
        return "\n\n---\n\n" + "\n\n".join(parts)

    def get_version_info(self, data_dir: Path) -> VersionInfo:
        return VersionInfo(
            version=self.oci_version,
            source_url="http://nomisma.org/nomisma.org.ttl",
            fetched_at="",
            triple_count=0,
            rdf_format="turtle",
        )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_nomisma_plugin.py -v`
Expected: PASS (7 tests)

- [ ] **Step 6: Commit**

```bash
git add linked_past/datasets/nomisma/ tests/test_nomisma_plugin.py
git commit -m "feat: add Nomisma dataset plugin with context files"
```

---

### Task 5: Register all plugins in the server

**Files:**
- Modify: `linked_past/core/server.py`
- Test: `tests/test_multi_dataset_integration.py`

- [ ] **Step 1: Write the integration test**

```python
# tests/test_multi_dataset_integration.py
"""Integration test verifying all 4 dataset plugins register and provide schemas."""

from linked_past.core.server import create_mcp_server
from linked_past.datasets.dprr.plugin import DPRRPlugin
from linked_past.datasets.pleiades.plugin import PleiadesPlugin
from linked_past.datasets.periodo.plugin import PeriodOPlugin
from linked_past.datasets.nomisma.plugin import NomismaPlugin


def test_all_plugins_instantiate():
    plugins = [DPRRPlugin(), PleiadesPlugin(), PeriodOPlugin(), NomismaPlugin()]
    names = {p.name for p in plugins}
    assert names == {"dprr", "pleiades", "periodo", "nomisma"}


def test_all_plugins_have_schemas():
    for Plugin in [DPRRPlugin, PleiadesPlugin, PeriodOPlugin, NomismaPlugin]:
        plugin = Plugin()
        schema = plugin.get_schema()
        assert "## Prefixes" in schema
        assert "## Classes" in schema


def test_all_plugins_have_prefixes():
    for Plugin in [DPRRPlugin, PleiadesPlugin, PeriodOPlugin, NomismaPlugin]:
        plugin = Plugin()
        prefixes = plugin.get_prefixes()
        assert len(prefixes) > 0


def test_all_plugins_validate():
    for Plugin in [DPRRPlugin, PleiadesPlugin, PeriodOPlugin, NomismaPlugin]:
        plugin = Plugin()
        # A generic valid query should pass (no class/predicate assertions)
        result = plugin.validate("SELECT ?s WHERE { ?s ?p ?o } LIMIT 1")
        assert result.valid is True


def test_server_registers_all_plugins():
    mcp = create_mcp_server()
    tool_names = [t.name for t in mcp._tool_manager.list_tools()]
    assert "discover_datasets" in tool_names
    assert "query" in tool_names
```

- [ ] **Step 2: Update server.py to register all plugins**

In `linked_past/core/server.py`, add imports for the new plugins and register them in `build_app_context`:

Add after the DPRRPlugin import:
```python
from linked_past.datasets.pleiades.plugin import PleiadesPlugin
from linked_past.datasets.periodo.plugin import PeriodOPlugin
from linked_past.datasets.nomisma.plugin import NomismaPlugin
```

In `build_app_context`, add after `registry.register(DPRRPlugin())`:
```python
    registry.register(PleiadesPlugin())
    registry.register(PeriodOPlugin())
    registry.register(NomismaPlugin())
```

- [ ] **Step 3: Run tests**

Run: `uv run pytest tests/test_multi_dataset_integration.py -v`
Expected: PASS (5 tests)

Run: `uv run pytest -v && uv run ruff check .`
Expected: All tests pass, lint clean

- [ ] **Step 4: Commit**

```bash
git add linked_past/core/server.py tests/test_multi_dataset_integration.py
git commit -m "feat: register Pleiades, PeriodO, and Nomisma plugins in server"
```

---

### Task 6: Dataset packaging scripts

**Files:**
- Create: `scripts/package_dprr.py`
- Create: `scripts/package_pleiades.py`
- Create: `scripts/package_periodo.py`
- Create: `scripts/package_nomisma.py`

These scripts download source data and push to the OCI registry. They run at build time, not at runtime.

- [ ] **Step 1: Create the packaging scripts**

```python
# scripts/package_dprr.py
"""Download DPRR data and push to OCI registry as a Turtle artifact."""

import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

SOURCE_URL = "https://github.com/gillisandrew/dprr-mcp/releases/latest/download/dprr-data.tar.gz"
ARTIFACT_REF = "ghcr.io/gillisandrew/linked-past/dprr"


def main(version: str = "latest"):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Download and extract
        print(f"Downloading {SOURCE_URL}...")
        tmp_path, _ = urllib.request.urlretrieve(SOURCE_URL)
        with tarfile.open(tmp_path, "r:gz") as tar:
            tar.extract("dprr.ttl", path=str(tmpdir), filter="data")
        Path(tmp_path).unlink()

        ttl = tmpdir / "dprr.ttl"
        print(f"Extracted {ttl} ({ttl.stat().st_size:,} bytes)")

        # Push to OCI registry
        ref = f"{ARTIFACT_REF}:{version}"
        print(f"Pushing to {ref}...")
        subprocess.run(
            ["oras", "push", ref, f"dprr.ttl:application/x-turtle"],
            cwd=str(tmpdir),
            check=True,
        )
        print(f"Done: {ref}")


if __name__ == "__main__":
    version = sys.argv[1] if len(sys.argv) > 1 else "latest"
    main(version)
```

```python
# scripts/package_pleiades.py
"""Download Pleiades RDF dump and push to OCI registry."""

import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

SOURCE_URL = "https://atlantides.org/downloads/pleiades/rdf/pleiades-latest.tar.gz"
ARTIFACT_REF = "ghcr.io/gillisandrew/linked-past/pleiades"


def main(version: str = "latest"):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        print(f"Downloading {SOURCE_URL}...")
        tmp_path, _ = urllib.request.urlretrieve(SOURCE_URL)

        # Extract all .ttl files and concatenate into one
        print("Extracting and concatenating Turtle files...")
        output = tmpdir / "pleiades.ttl"
        with tarfile.open(tmp_path, "r:gz") as tar, open(output, "w") as out:
            for member in sorted(tar.getnames()):
                if member.endswith(".ttl"):
                    f = tar.extractfile(member)
                    if f:
                        out.write(f"# Source: {member}\n")
                        out.write(f.read().decode("utf-8"))
                        out.write("\n\n")
        Path(tmp_path).unlink()

        print(f"Created {output} ({output.stat().st_size:,} bytes)")

        ref = f"{ARTIFACT_REF}:{version}"
        print(f"Pushing to {ref}...")
        subprocess.run(
            ["oras", "push", ref, f"pleiades.ttl:application/x-turtle"],
            cwd=str(tmpdir),
            check=True,
        )
        print(f"Done: {ref}")


if __name__ == "__main__":
    version = sys.argv[1] if len(sys.argv) > 1 else "latest"
    main(version)
```

```python
# scripts/package_periodo.py
"""Download PeriodO JSON-LD, convert to Turtle, and push to OCI registry."""

import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

SOURCE_URL = "http://n2t.net/ark:/99152/p0d.jsonld"
ARTIFACT_REF = "ghcr.io/gillisandrew/linked-past/periodo"


def main(version: str = "latest"):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        print(f"Downloading {SOURCE_URL}...")
        jsonld_path = tmpdir / "periodo.jsonld"
        urllib.request.urlretrieve(SOURCE_URL, str(jsonld_path))
        print(f"Downloaded {jsonld_path} ({jsonld_path.stat().st_size:,} bytes)")

        # Convert JSON-LD to Turtle using rdflib
        print("Converting JSON-LD to Turtle...")
        from rdflib import Graph
        g = Graph()
        g.parse(str(jsonld_path), format="json-ld")
        ttl_path = tmpdir / "periodo.ttl"
        g.serialize(str(ttl_path), format="turtle")
        print(f"Created {ttl_path} ({ttl_path.stat().st_size:,} bytes), {len(g)} triples")

        ref = f"{ARTIFACT_REF}:{version}"
        print(f"Pushing to {ref}...")
        subprocess.run(
            ["oras", "push", ref, f"periodo.ttl:application/x-turtle"],
            cwd=str(tmpdir),
            check=True,
        )
        print(f"Done: {ref}")


if __name__ == "__main__":
    version = sys.argv[1] if len(sys.argv) > 1 else "latest"
    main(version)
```

```python
# scripts/package_nomisma.py
"""Download Nomisma concept vocabulary and push to OCI registry."""

import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

SOURCE_URL = "http://nomisma.org/nomisma.org.ttl"
ARTIFACT_REF = "ghcr.io/gillisandrew/linked-past/nomisma"


def main(version: str = "latest"):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        print(f"Downloading {SOURCE_URL}...")
        ttl_path = tmpdir / "nomisma.ttl"
        urllib.request.urlretrieve(SOURCE_URL, str(ttl_path))
        print(f"Downloaded {ttl_path} ({ttl_path.stat().st_size:,} bytes)")

        ref = f"{ARTIFACT_REF}:{version}"
        print(f"Pushing to {ref}...")
        subprocess.run(
            ["oras", "push", ref, f"nomisma.ttl:application/x-turtle"],
            cwd=str(tmpdir),
            check=True,
        )
        print(f"Done: {ref}")


if __name__ == "__main__":
    version = sys.argv[1] if len(sys.argv) > 1 else "latest"
    main(version)
```

- [ ] **Step 2: Commit**

```bash
git add scripts/package_dprr.py scripts/package_pleiades.py scripts/package_periodo.py scripts/package_nomisma.py
git commit -m "feat: add dataset packaging scripts for OCI registry distribution"
```

---

### Task 7: Final verification

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest -v`
Expected: All tests pass

- [ ] **Step 2: Run lint**

Run: `uv run ruff check .`
Expected: Clean (or only pre-existing issues in `dprr_mcp/`)

- [ ] **Step 3: Verify server starts with all plugins**

Run: `LINKED_PAST_DATA_DIR=/tmp/lp-test uv run linked-past-server --help`
Expected: Shows help without errors

- [ ] **Step 4: Commit any fixes**

```bash
git add -A && git commit -m "fix: address issues found in final verification"
```
