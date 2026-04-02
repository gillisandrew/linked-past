# Codebase Simplification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate ~1000 lines of duplicated code across dataset plugins, tests, and server wiring; consolidate scattered utilities; restructure validate.py heuristics into composable checkers.

**Architecture:** Move all identical plugin logic (init, get_schema, validate, get_relevant_context) into the DatasetPlugin base class. Replace 7 near-identical plugin test files with a single parametrized test. Auto-discover plugins instead of hardcoding imports. Consolidate duplicate `_uri_to_dataset()`. Split monolithic `_run_heuristics()` into focused checker functions.

**Tech Stack:** Python 3.13+, pytest, pyoxigraph, rdflib, PyYAML

---

### Task 1: Consolidate Plugin Base Class

Move the identical `__init__()`, `get_prefixes()`, `build_schema_dict()`, `get_schema()`, `validate()`, and `get_relevant_context()` implementations from the 7 plugins into `DatasetPlugin`. Each concrete plugin becomes metadata-only (~20 lines).

**Files:**
- Modify: `packages/linked-past/linked_past/datasets/base.py`
- Modify: `packages/linked-past/linked_past/datasets/dprr/plugin.py`
- Modify: `packages/linked-past/linked_past/datasets/pleiades/plugin.py`
- Modify: `packages/linked-past/linked_past/datasets/periodo/plugin.py`
- Modify: `packages/linked-past/linked_past/datasets/nomisma/plugin.py`
- Modify: `packages/linked-past/linked_past/datasets/crro/plugin.py`
- Modify: `packages/linked-past/linked_past/datasets/ocre/plugin.py`
- Modify: `packages/linked-past/linked_past/datasets/edh/plugin.py`
- Test: `packages/linked-past/tests/test_base.py`

- [ ] **Step 1: Write tests for base class concrete methods**

Add tests to `test_base.py` that verify `DatasetPlugin` now works as a concrete (non-abstract) base when subclassed with just metadata and a `context/` directory. Use the DPRR plugin's context dir as a real fixture.

```python
# Append to tests/test_base.py
from pathlib import Path

from linked_past.datasets.base import DatasetPlugin, ValidationResult, VersionInfo


class MinimalPlugin(DatasetPlugin):
    """Plugin with only class-level metadata — all logic comes from base."""
    name = "dprr"
    display_name = "Test Plugin"
    description = "A test plugin"
    citation = "Test"
    license = "CC0"
    url = "https://example.com"
    time_coverage = "all"
    spatial_coverage = "everywhere"
    oci_dataset = "datasets/test"

    @classmethod
    def _context_dir(cls) -> Path:
        return Path(__file__).resolve().parent.parent / "linked_past" / "datasets" / "dprr" / "context"


def test_base_class_loads_context():
    plugin = MinimalPlugin()
    assert len(plugin.get_prefixes()) > 0
    assert "vocab" in plugin.get_prefixes()


def test_base_class_builds_schema_dict():
    plugin = MinimalPlugin()
    sd = plugin.build_schema_dict()
    assert isinstance(sd, dict)
    assert len(sd) > 0


def test_base_class_renders_schema():
    plugin = MinimalPlugin()
    schema = plugin.get_schema()
    assert "## Prefixes" in schema
    assert "## Classes" in schema
    assert "## General Tips" in schema


def test_base_class_validates():
    plugin = MinimalPlugin()
    result = plugin.validate(
        "PREFIX vocab: <http://romanrepublic.ac.uk/rdf/ontology#>\n"
        "SELECT ?p WHERE { ?p a vocab:Person }"
    )
    assert result.valid is True
    assert isinstance(result, ValidationResult)


def test_base_class_relevant_context():
    plugin = MinimalPlugin()
    ctx = plugin.get_relevant_context(
        "PREFIX vocab: <http://romanrepublic.ac.uk/rdf/ontology#>\n"
        "SELECT ?p WHERE { ?p a vocab:Person ; vocab:hasPersonName ?n }"
    )
    assert isinstance(ctx, str)
    assert len(ctx) > 0


def test_base_class_version_info():
    plugin = MinimalPlugin()
    info = plugin.get_version_info(Path("/tmp"))
    assert info is not None
    assert info.rdf_format == "turtle"
    assert info.source_url == "https://example.com"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/linked-past/tests/test_base.py -v -k "MinimalPlugin or base_class"`
Expected: FAIL — `DatasetPlugin` has abstract methods and `_context_dir()` doesn't exist yet.

- [ ] **Step 3: Rewrite base.py with concrete implementations**

Replace `base.py` with concrete default implementations. The key design decision: each subclass provides a `_context_dir()` classmethod returning the `Path` to its `context/` directory. The base `__init__()` loads all YAML from there.

```python
"""Base class and dataclasses for dataset plugins."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from pyoxigraph import RdfFormat, Store

logger = logging.getLogger(__name__)


@dataclass
class VersionInfo:
    version: str
    source_url: str
    fetched_at: str
    triple_count: int
    rdf_format: str


@dataclass
class UpdateInfo:
    current: str
    available: str
    changelog_url: str | None = None


@dataclass
class ValidationResult:
    valid: bool
    sparql: str
    errors: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)


class DatasetPlugin:
    """Base class for dataset plugins.

    Subclasses must set class attributes (name, display_name, etc.) and
    implement ``_context_dir()`` pointing at their ``context/`` directory.
    All SPARQL-facing methods (get_schema, validate, get_relevant_context)
    are provided by the base class.
    """

    name: str
    display_name: str
    description: str
    citation: str
    license: str
    url: str
    time_coverage: str
    spatial_coverage: str
    rdf_format: RdfFormat = RdfFormat.TURTLE
    oci_dataset: str = ""
    oci_version: str = "latest"

    @classmethod
    def _context_dir(cls) -> Path:
        """Return path to this plugin's context/ directory.

        Default: ``<plugin_module_dir>/context/``.
        """
        import inspect

        return Path(inspect.getfile(cls)).parent / "context"

    def __init__(self):
        from linked_past.core.context import (
            load_examples,
            load_prefixes,
            load_schemas,
            load_tips,
        )
        from linked_past.core.validate import build_schema_dict, extract_query_classes

        context_dir = self._context_dir()
        self._prefixes = load_prefixes(context_dir)
        self._schemas = load_schemas(context_dir)
        self._hand_written_class_names = set(self._schemas.keys())
        self._examples = load_examples(context_dir)
        self._tips = load_tips(context_dir)
        self._schema_dict = build_schema_dict(self._schemas, self._prefixes)
        for ex in self._examples:
            ex["classes"] = extract_query_classes(ex["sparql"], self._schema_dict)

    def fetch(self, data_dir: Path, force: bool = False) -> Path:
        """Download data via ORAS from OCI registry. Override for custom fetch logic."""
        from linked_past.core.fetch import pull_artifact

        if not self.oci_dataset:
            raise NotImplementedError(f"{self.__class__.__name__} must set oci_dataset or override fetch()")
        return pull_artifact(self.oci_dataset, data_dir, self.oci_version, force=force)

    def load(self, store: Store, rdf_path: Path) -> int:
        """Bulk-load all data files into Oxigraph store, return triple count."""
        data_dir = rdf_path.parent
        ttl_files = [f for f in sorted(data_dir.glob("*.ttl")) if not f.name.startswith("_")]
        for ttl in ttl_files:
            store.bulk_load(path=str(ttl), format=self.rdf_format)
        return len(store)

    def get_prefixes(self) -> dict[str, str]:
        """Return namespace prefix map."""
        return self._prefixes

    def build_schema_dict(self) -> dict:
        """Return dict[class_full_uri][predicate_full_uri] = {ranges, ...}."""
        return self._schema_dict

    def get_schema(self) -> str:
        """Return rendered ontology overview as markdown."""
        from linked_past.core.context import (
            get_cross_cutting_tips,
            render_auto_detected_summary,
            render_class_summary,
            render_tips,
        )

        prefix_lines = "\n".join(f"PREFIX {k}: <{v}>" for k, v in self._prefixes.items())
        class_summary = render_class_summary(self._schemas)
        cross_tips = get_cross_cutting_tips(self._tips)
        tips_md = render_tips(cross_tips)
        result = (
            f"## Prefixes\n\n```sparql\n{prefix_lines}\n```\n\n"
            f"## Classes\n\n{class_summary}\n\n"
            f"## General Tips\n\n{tips_md}"
        )
        auto_section = render_auto_detected_summary(self._schemas, self._hand_written_class_names)
        if auto_section:
            result += f"\n\n{auto_section}"
        return result

    def validate(self, sparql: str) -> ValidationResult:
        """Dataset-specific semantic validation."""
        from linked_past.core.validate import validate_semantics

        class_counts = getattr(self, "_class_counts", None)
        hints = validate_semantics(sparql, self._schema_dict, class_counts=class_counts)
        return ValidationResult(valid=True, sparql=sparql, suggestions=hints)

    def get_relevant_context(self, sparql: str) -> str:
        """Return contextual tips/examples for a SPARQL query."""
        from linked_past.core.context import (
            get_relevant_examples,
            get_relevant_tips,
            render_examples,
            render_tips,
        )
        from linked_past.core.validate import extract_query_classes

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
        """Return current snapshot metadata.

        Default uses self.url as source_url. Override in subclasses that need
        a different source URL (e.g., a specific RDF dump endpoint).
        Note: fetched_at is left empty — the registry populates the actual
        timestamp when it saves registry.json after a successful fetch.
        """
        return VersionInfo(
            version=self.oci_version,
            source_url=self.url,
            fetched_at="",
            triple_count=0,
            rdf_format="turtle",
        )

    def set_void_class_counts(self, class_counts: dict[str, int]) -> None:
        """Store VoID class counts for validation hints."""
        self._class_counts = class_counts

    def set_auto_schema(self, auto_schema: dict | None) -> None:
        """Merge auto-generated schema classes into this plugin's schemas."""
        if not auto_schema:
            return
        from linked_past.core.context import merge_schemas
        from linked_past.core.validate import build_schema_dict

        original_count = len(self._schemas)
        self._schemas = merge_schemas(self._schemas, auto_schema)
        new_count = len(self._schemas) - original_count
        if new_count > 0:
            self._schema_dict = build_schema_dict(self._schemas, self._prefixes)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/linked-past/tests/test_base.py -v`
Expected: All new tests PASS. Existing `test_dataset_plugin_is_abstract` will FAIL — update it since `DatasetPlugin` is no longer abstract.

- [ ] **Step 5: Update test_dataset_plugin_is_abstract**

The base class is no longer abstract. Replace that test with one that verifies a bare `DatasetPlugin()` raises because it has no `context/` dir at the module level (the default `_context_dir` would point to `datasets/base/context/` which doesn't exist).

```python
def test_dataset_plugin_requires_context_dir():
    """A bare DatasetPlugin() fails because base.py has no context/ directory."""
    import pytest
    with pytest.raises(Exception):
        DatasetPlugin()
```

- [ ] **Step 6: Run full test_base.py**

Run: `uv run pytest packages/linked-past/tests/test_base.py -v`
Expected: All PASS.

- [ ] **Step 7: Slim down all 7 plugin files**

Replace each plugin with metadata-only. Plugins that need a custom `get_version_info` (DPRR for its env var, CRRO/OCRE for their specific RDF dump URLs) override just that method.

DPRR (`packages/linked-past/linked_past/datasets/dprr/plugin.py`) — retains `DPRR_DATA_URL` env var override:

```python
"""DPRR dataset plugin."""

import os
from pathlib import Path

from linked_past.datasets.base import DatasetPlugin, VersionInfo

_DEFAULT_DATA_URL = "https://github.com/gillisandrew/dprr-mcp/releases/latest/download/dprr-data.tar.gz"


class DPRRPlugin(DatasetPlugin):
    name = "dprr"
    display_name = "Digital Prosopography of the Roman Republic"
    description = (
        "A structured prosopography of the political elite of the Roman Republic "
        "(c. 509-31 BC), documenting persons, office-holdings, family relationships, "
        "and social status with full source citations."
    )
    citation = (
        "Sherwin et al., Digital Prosopography of the Roman Republic, "
        "romanrepublic.ac.uk"
    )
    license = "CC BY-NC 4.0"
    url = "https://romanrepublic.ac.uk"
    time_coverage = "509-31 BC"
    spatial_coverage = "Roman Republic"
    oci_dataset = "datasets/dprr"

    def get_version_info(self, data_dir: Path) -> VersionInfo:
        return VersionInfo(
            version=self.oci_version,
            source_url=os.environ.get("DPRR_DATA_URL", _DEFAULT_DATA_URL),
            fetched_at="",
            triple_count=0,
            rdf_format="turtle",
        )
```

Pleiades (`packages/linked-past/linked_past/datasets/pleiades/plugin.py`):

```python
"""Pleiades dataset plugin."""

from linked_past.datasets.base import DatasetPlugin


class PleiadesPlugin(DatasetPlugin):
    name = "pleiades"
    display_name = "Pleiades Gazetteer of Ancient Places"
    description = (
        "A community-built gazetteer and graph of ancient places, "
        "covering the Greek and Roman world with ~41,000 places, "
        "locations, and historical names."
    )
    citation = (
        "Pleiades: A Gazetteer of Past Places, "
        "https://pleiades.stoa.org"
    )
    license = "CC BY 3.0"
    url = "https://pleiades.stoa.org"
    time_coverage = "Archaic period through Late Antiquity"
    spatial_coverage = "Greek and Roman world"
    oci_dataset = "datasets/pleiades"
```

PeriodO (`packages/linked-past/linked_past/datasets/periodo/plugin.py`):

```python
"""PeriodO dataset plugin."""

from linked_past.datasets.base import DatasetPlugin


class PeriodOPlugin(DatasetPlugin):
    name = "periodo"
    display_name = "PeriodO"
    description = (
        "A gazetteer of scholarly definitions of historical, art-historical, "
        "and archaeological periods. Each period has temporal bounds, spatial "
        "coverage, and provenance from a specific authority."
    )
    citation = (
        "PeriodO, A gazetteer of period definitions for linking "
        "and visualizing data, https://perio.do"
    )
    license = "CC0"
    url = "https://perio.do"
    time_coverage = "All periods (prehistoric through modern)"
    spatial_coverage = "Global"
    oci_dataset = "datasets/periodo"
```

Nomisma (`packages/linked-past/linked_past/datasets/nomisma/plugin.py`):

```python
"""Nomisma dataset plugin."""

from linked_past.datasets.base import DatasetPlugin


class NomismaPlugin(DatasetPlugin):
    name = "nomisma"
    display_name = "Nomisma.org Numismatic Vocabulary"
    description = (
        "A collaborative project providing stable digital representations "
        "of numismatic concepts — people, mints, denominations, materials, "
        "and regions — as Linked Open Data."
    )
    citation = "Nomisma.org, http://nomisma.org"
    license = "CC BY"
    url = "http://nomisma.org"
    time_coverage = "Ancient through modern numismatics"
    spatial_coverage = "Global"
    oci_dataset = "datasets/nomisma"
```

CRRO (`packages/linked-past/linked_past/datasets/crro/plugin.py`) — retains specific RDF dump URL:

```python
"""CRRO dataset plugin."""

from pathlib import Path

from linked_past.datasets.base import DatasetPlugin, VersionInfo


class CRROPlugin(DatasetPlugin):
    name = "crro"
    display_name = "Coinage of the Roman Republic Online (CRRO)"
    description = (
        "A digital type corpus of 2,602 Roman Republican coin types based on "
        "Crawford's Roman Republican Coinage (RRC). Each type documents denomination, "
        "issuing authority, mint, material, and obverse/reverse iconography with "
        "links to Nomisma concepts."
    )
    citation = (
        "American Numismatic Society, Coinage of the Roman Republic Online, "
        "https://numismatics.org/crro/. Based on Crawford, M.H. (1974) "
        "Roman Republican Coinage."
    )
    license = "ODbL 1.0"
    url = "https://numismatics.org/crro"
    time_coverage = "c. 280-27 BC"
    spatial_coverage = "Roman Republic"
    oci_dataset = "datasets/crro"

    def get_version_info(self, data_dir: Path) -> VersionInfo:
        return VersionInfo(
            version=self.oci_version,
            source_url="https://numismatics.org/crro/nomisma.rdf",
            fetched_at="",
            triple_count=0,
            rdf_format="turtle",
        )
```

OCRE (`packages/linked-past/linked_past/datasets/ocre/plugin.py`) — retains specific RDF dump URL:

```python
"""OCRE dataset plugin."""

from pathlib import Path

from linked_past.datasets.base import DatasetPlugin, VersionInfo


class OCREPlugin(DatasetPlugin):
    name = "ocre"
    display_name = "Online Coins of the Roman Empire (OCRE)"
    description = (
        "A digital type corpus of ~50,000 Roman Imperial coin types from "
        "RIC (Roman Imperial Coinage). Each type documents denomination, "
        "issuing emperor, mint, material, and obverse/reverse iconography "
        "with links to Nomisma concepts."
    )
    citation = (
        "American Numismatic Society, Online Coins of the Roman Empire, "
        "https://numismatics.org/ocre/. Based on Mattingly, H. et al., "
        "Roman Imperial Coinage (RIC)."
    )
    license = "ODbL 1.0"
    url = "https://numismatics.org/ocre"
    time_coverage = "c. 31 BC - 491 AD"
    spatial_coverage = "Roman Empire"
    oci_dataset = "datasets/ocre"

    def get_version_info(self, data_dir: Path) -> VersionInfo:
        return VersionInfo(
            version=self.oci_version,
            source_url="https://numismatics.org/ocre/nomisma.rdf",
            fetched_at="",
            triple_count=0,
            rdf_format="turtle",
        )
```

EDH (`packages/linked-past/linked_past/datasets/edh/plugin.py`):

```python
"""EDH (Epigraphic Database Heidelberg) dataset plugin."""

from linked_past.datasets.base import DatasetPlugin


class EDHPlugin(DatasetPlugin):
    name = "edh"
    display_name = "Epigraphic Database Heidelberg (EDH)"
    description = (
        "81,000+ Latin inscriptions from across the Roman Empire with transcriptions, "
        "findspots, dates, and prosopographic data. Includes diplomatic and scholarly "
        "edition texts."
    )
    citation = (
        "Epigraphic Database Heidelberg, https://edh.ub.uni-heidelberg.de/. "
        "CC BY-SA 4.0."
    )
    license = "CC BY-SA 4.0"
    url = "https://edh.ub.uni-heidelberg.de"
    time_coverage = "Antiquity through Late Antiquity"
    spatial_coverage = "Roman Empire"
    oci_dataset = "datasets/edh"
```

- [ ] **Step 8: Run all existing plugin tests**

Run: `uv run pytest packages/linked-past/tests/test_dprr_plugin.py packages/linked-past/tests/test_pleiades_plugin.py packages/linked-past/tests/test_periodo_plugin.py packages/linked-past/tests/test_nomisma_plugin.py packages/linked-past/tests/test_crro_plugin.py packages/linked-past/tests/test_ocre_plugin.py packages/linked-past/tests/test_edh_plugin.py -v`
Expected: All PASS — behavior unchanged.

- [ ] **Step 9: Run full test suite**

Run: `uv run pytest -x -v`
Expected: All PASS.

- [ ] **Step 10: Commit**

```bash
git add packages/linked-past/linked_past/datasets/base.py packages/linked-past/linked_past/datasets/*/plugin.py packages/linked-past/tests/test_base.py
git commit -m "refactor: consolidate plugin boilerplate into DatasetPlugin base class"
```

---

### Task 2: Replace Individual Plugin Tests with Parametrized Suite

The 6 plugin test files (`test_dprr_plugin.py`, `test_pleiades_plugin.py`, `test_periodo_plugin.py`, `test_nomisma_plugin.py`, `test_edh_plugin.py`, `test_ocre_plugin.py`) test the same methods with 95% identical structure. Replace with a single parametrized test file covering all 7 plugins (CRRO had no dedicated test file).

**Files:**
- Create: `packages/linked-past/tests/test_plugins.py`
- Delete: `packages/linked-past/tests/test_dprr_plugin.py`
- Delete: `packages/linked-past/tests/test_pleiades_plugin.py`
- Delete: `packages/linked-past/tests/test_periodo_plugin.py`
- Delete: `packages/linked-past/tests/test_nomisma_plugin.py`
- Delete: `packages/linked-past/tests/test_edh_plugin.py`
- Delete: `packages/linked-past/tests/test_ocre_plugin.py`

- [ ] **Step 1: Write the parametrized test file**

```python
# tests/test_plugins.py
"""Parametrized tests for all dataset plugins.

Each plugin must provide prefixes, a schema with classes, working validation,
relevant context extraction, and data loading.
"""

import pytest
from linked_past.core.store import create_store
from linked_past.datasets.crro.plugin import CRROPlugin
from linked_past.datasets.dprr.plugin import DPRRPlugin
from linked_past.datasets.edh.plugin import EDHPlugin
from linked_past.datasets.nomisma.plugin import NomismaPlugin
from linked_past.datasets.ocre.plugin import OCREPlugin
from linked_past.datasets.periodo.plugin import PeriodOPlugin
from linked_past.datasets.pleiades.plugin import PleiadesPlugin

ALL_PLUGINS = [DPRRPlugin, PleiadesPlugin, PeriodOPlugin, NomismaPlugin, CRROPlugin, OCREPlugin, EDHPlugin]

# Per-plugin expectations: (PluginClass, expected_name, expected_license, required_prefix, schema_class_keywords, sample_turtle)
PLUGIN_SPECS = [
    (DPRRPlugin, "dprr", "CC BY-NC 4.0", "vocab", ["Person", "PostAssertion"],
     '@prefix vocab: <http://romanrepublic.ac.uk/rdf/ontology#> .\n'
     '<http://romanrepublic.ac.uk/rdf/entity/Person/1> a vocab:Person .\n'),
    (PleiadesPlugin, "pleiades", "CC BY 3.0", "pleiades", ["Place", "Location"],
     '@prefix pleiades: <https://pleiades.stoa.org/places/vocab#> .\n'
     '@prefix dcterms: <http://purl.org/dc/terms/> .\n'
     '<https://pleiades.stoa.org/places/423025> a pleiades:Place ; dcterms:title "Roma" .\n'),
    (PeriodOPlugin, "periodo", "CC0", "skos", ["Period", "Authority"],
     '@prefix skos: <http://www.w3.org/2004/02/skos/core#> .\n'
     '<http://n2t.net/ark:/99152/p05krdxmkzt> a skos:Concept ; skos:prefLabel "Roman Republic" .\n'),
    (NomismaPlugin, "nomisma", "CC BY", "nmo", ["Person", "Mint", "Denomination"],
     '@prefix nmo: <http://nomisma.org/ontology#> .\n'
     '@prefix nm: <http://nomisma.org/id/> .\n'
     '@prefix skos: <http://www.w3.org/2004/02/skos/core#> .\n'
     'nm:rome a nmo:Mint, skos:Concept ; skos:prefLabel "Rome"@en .\n'),
    (CRROPlugin, "crro", "ODbL 1.0", "nmo", ["CoinType", "TypeSeriesItem"],
     '@prefix nmo: <http://nomisma.org/ontology#> .\n'
     '@prefix skos: <http://www.w3.org/2004/02/skos/core#> .\n'
     '<http://numismatics.org/crro/id/rrc-1.1> a nmo:TypeSeriesItem, skos:Concept ;\n'
     '    skos:prefLabel "RRC 1/1" .\n'),
    (OCREPlugin, "ocre", "ODbL 1.0", "nmo", ["CoinType", "TypeSeriesItem"],
     '@prefix nmo: <http://nomisma.org/ontology#> .\n'
     '@prefix skos: <http://www.w3.org/2004/02/skos/core#> .\n'
     '<http://numismatics.org/ocre/id/ric.1(2).aug.1A> a nmo:TypeSeriesItem, skos:Concept ;\n'
     '    skos:prefLabel "RIC I Augustus 1A" .\n'),
    (EDHPlugin, "edh", "CC BY-SA 4.0", "epi", ["Inscription"],
     '@prefix epi: <http://edh-www.adw.uni-heidelberg.de/lod/ontology#> .\n'
     '<http://edh-www.adw.uni-heidelberg.de/edh/inschrift/HD000001> a epi:Inscription .\n'),
]


@pytest.fixture(params=PLUGIN_SPECS, ids=lambda s: s[1])
def plugin_spec(request):
    return request.param


def test_plugin_attributes(plugin_spec):
    PluginClass, expected_name, expected_license, _, _, _ = plugin_spec
    plugin = PluginClass()
    assert plugin.name == expected_name
    assert plugin.license == expected_license
    assert plugin.display_name
    assert plugin.url
    assert plugin.oci_dataset == f"datasets/{expected_name}"


def test_plugin_prefixes(plugin_spec):
    PluginClass, _, _, required_prefix, _, _ = plugin_spec
    plugin = PluginClass()
    prefixes = plugin.get_prefixes()
    assert len(prefixes) > 0
    assert required_prefix in prefixes


def test_plugin_schema(plugin_spec):
    PluginClass, _, _, _, schema_keywords, _ = plugin_spec
    plugin = PluginClass()
    schema = plugin.get_schema()
    assert "## Prefixes" in schema
    assert "## Classes" in schema
    for keyword in schema_keywords:
        assert keyword in schema


def test_plugin_validate_valid(plugin_spec):
    PluginClass, _, _, _, _, _ = plugin_spec
    plugin = PluginClass()
    result = plugin.validate("SELECT ?s WHERE { ?s ?p ?o } LIMIT 1")
    assert result.valid is True


def test_plugin_validate_unknown_class(plugin_spec):
    PluginClass, _, _, _, _, _ = plugin_spec
    plugin = PluginClass()
    result = plugin.validate("SELECT ?s WHERE { ?s a <http://example.org/FakeClass> }")
    assert result.valid is True  # Unknown classes are non-blocking warnings


def test_plugin_load(plugin_spec, tmp_path):
    PluginClass, expected_name, _, _, _, sample_turtle = plugin_spec
    plugin = PluginClass()
    ttl = tmp_path / f"{expected_name}.ttl"
    ttl.write_text(sample_turtle)
    store = create_store(tmp_path / "store")
    count = plugin.load(store, ttl)
    assert count > 0


def test_plugin_version_info(plugin_spec, tmp_path):
    PluginClass, _, _, _, _, _ = plugin_spec
    plugin = PluginClass()
    info = plugin.get_version_info(tmp_path)
    assert info is not None
    assert info.rdf_format == "turtle"
```

- [ ] **Step 2: Run parametrized tests**

Run: `uv run pytest packages/linked-past/tests/test_plugins.py -v`
Expected: All PASS (7 plugins × 7 tests = 49 test cases).

- [ ] **Step 3: Delete the 6 individual plugin test files**

```bash
rm packages/linked-past/tests/test_dprr_plugin.py
rm packages/linked-past/tests/test_pleiades_plugin.py
rm packages/linked-past/tests/test_periodo_plugin.py
rm packages/linked-past/tests/test_nomisma_plugin.py
rm packages/linked-past/tests/test_edh_plugin.py
rm packages/linked-past/tests/test_ocre_plugin.py
```

- [ ] **Step 4: Run full test suite to verify nothing else depended on deleted files**

Run: `uv run pytest -x -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/linked-past/tests/test_plugins.py
git add -u packages/linked-past/tests/
git commit -m "refactor: replace 6 per-plugin test files with single parametrized suite"
```

---

### Task 3: Auto-Discover Plugins in server.py

Remove the 7 hardcoded plugin imports from `server.py`. Add a `discover_plugins()` function to the registry that finds all `DatasetPlugin` subclasses from the `datasets/` package.

**Files:**
- Modify: `packages/linked-past/linked_past/core/registry.py`
- Modify: `packages/linked-past/linked_past/core/server.py`
- Modify: `packages/linked-past/linked_past/datasets/__init__.py`
- Test: `packages/linked-past/tests/test_registry.py`

- [ ] **Step 1: Write failing test for discover_plugins**

Add to `test_registry.py`:

```python
def test_discover_plugins_finds_all():
    from linked_past.core.registry import discover_plugins

    plugins = discover_plugins()
    names = {p.name for p in plugins}
    assert names == {"dprr", "pleiades", "periodo", "nomisma", "crro", "ocre", "edh"}


def test_discover_plugins_returns_instances():
    from linked_past.core.registry import discover_plugins

    plugins = discover_plugins()
    for p in plugins:
        assert hasattr(p, "get_prefixes")
        assert hasattr(p, "get_schema")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/linked-past/tests/test_registry.py::test_discover_plugins_finds_all -v`
Expected: FAIL — `discover_plugins` doesn't exist yet.

- [ ] **Step 3: Add datasets/__init__.py that imports all plugins**

Update `packages/linked-past/linked_past/datasets/__init__.py` to import all plugin classes. This is the single place that enumerates plugins — no scanning needed, just an explicit import list:

```python
"""Dataset plugins package.

Import all plugins here so discover_plugins() can find them via
DatasetPlugin.__subclasses__().
"""

from linked_past.datasets.crro.plugin import CRROPlugin
from linked_past.datasets.dprr.plugin import DPRRPlugin
from linked_past.datasets.edh.plugin import EDHPlugin
from linked_past.datasets.nomisma.plugin import NomismaPlugin
from linked_past.datasets.ocre.plugin import OCREPlugin
from linked_past.datasets.periodo.plugin import PeriodOPlugin
from linked_past.datasets.pleiades.plugin import PleiadesPlugin

__all__ = [
    "CRROPlugin",
    "DPRRPlugin",
    "EDHPlugin",
    "NomismaPlugin",
    "OCREPlugin",
    "PeriodOPlugin",
    "PleiadesPlugin",
]
```

- [ ] **Step 4: Add discover_plugins() to registry.py**

Add at the top level of `registry.py`:

```python
def discover_plugins() -> list[DatasetPlugin]:
    """Discover and instantiate all dataset plugins.

    Imports the datasets package (which registers all subclasses),
    then instantiates each DatasetPlugin subclass. Filters out test
    classes (FakePlugin, MinimalPlugin, etc.) by checking the module path.
    """
    import linked_past.datasets  # noqa: F401 — triggers subclass registration

    return [
        cls()
        for cls in DatasetPlugin.__subclasses__()
        if cls.__module__.startswith("linked_past.datasets.")
    ]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest packages/linked-past/tests/test_registry.py::test_discover_plugins_finds_all packages/linked-past/tests/test_registry.py::test_discover_plugins_returns_instances -v`
Expected: PASS.

- [ ] **Step 6: Update server.py to use discover_plugins**

In `packages/linked-past/linked_past/core/server.py`, replace lines 23-29 (the 7 plugin imports) and lines 248-254 (the 7 `registry.register()` calls) with:

Replace the imports block:
```python
# Remove these 7 lines:
from linked_past.datasets.crro.plugin import CRROPlugin
from linked_past.datasets.dprr.plugin import DPRRPlugin
from linked_past.datasets.edh.plugin import EDHPlugin
from linked_past.datasets.nomisma.plugin import NomismaPlugin
from linked_past.datasets.ocre.plugin import OCREPlugin
from linked_past.datasets.periodo.plugin import PeriodOPlugin
from linked_past.datasets.pleiades.plugin import PleiadesPlugin

# Add this one:
from linked_past.core.registry import DatasetRegistry, discover_plugins
```

Replace the registration block in `build_app_context()`:
```python
# Replace lines 248-254:
    registry.register(DPRRPlugin())
    registry.register(PleiadesPlugin())
    registry.register(PeriodOPlugin())
    registry.register(NomismaPlugin())
    registry.register(CRROPlugin())
    registry.register(OCREPlugin())
    registry.register(EDHPlugin())

# With:
    for plugin in discover_plugins():
        registry.register(plugin)
```

- [ ] **Step 7: Run full test suite**

Run: `uv run pytest -x -v`
Expected: All PASS.

- [ ] **Step 8: Commit**

```bash
git add packages/linked-past/linked_past/core/registry.py packages/linked-past/linked_past/core/server.py packages/linked-past/linked_past/datasets/__init__.py packages/linked-past/tests/test_registry.py
git commit -m "refactor: auto-discover plugins via DatasetPlugin.__subclasses__"
```

---

### Task 4: Shared Integration Test Fixtures

Both `test_server.py` and `test_linked_past_integration.py` duplicate identical monkeypatch blocks to patch all 7 plugin `fetch()` methods. Extract into `conftest.py`.

**Files:**
- Create: `packages/linked-past/tests/conftest.py`
- Modify: `packages/linked-past/tests/test_server.py`
- Modify: `packages/linked-past/tests/test_linked_past_integration.py`

- [ ] **Step 1: Create conftest.py with shared fixture**

After Task 3, monkeypatching is simpler — we patch `DatasetPlugin.fetch` on the base class, or patch each plugin's fetch via the common pattern. Since integration tests need per-dataset TTL files, use a fixture that creates minimal TTL for all datasets:

```python
# tests/conftest.py
"""Shared fixtures for linked-past integration tests."""

import pytest
from linked_past.core.server import build_app_context

SAMPLE_DPRR_TURTLE = """\
@prefix vocab: <http://romanrepublic.ac.uk/rdf/ontology#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

<http://romanrepublic.ac.uk/rdf/entity/Person/1> a vocab:Person ;
    vocab:hasPersonName "IUNI0001 L. Iunius Brutus" ;
    vocab:hasDprrID "IUNI0001" ;
    vocab:hasNomen "Iunius" ;
    vocab:hasCognomen "Brutus" ;
    vocab:isSex <http://romanrepublic.ac.uk/rdf/entity/Sex/Male> ;
    vocab:hasEraFrom "-509"^^xsd:integer .

<http://romanrepublic.ac.uk/rdf/entity/PostAssertion/1> a vocab:PostAssertion ;
    vocab:isAboutPerson <http://romanrepublic.ac.uk/rdf/entity/Person/1> ;
    vocab:hasOffice <http://romanrepublic.ac.uk/rdf/entity/Office/3> ;
    vocab:hasDateStart "-509"^^xsd:integer .

<http://romanrepublic.ac.uk/rdf/entity/Office/3> a vocab:Office ;
    rdfs:label "Office: consul" .

<http://romanrepublic.ac.uk/rdf/entity/Sex/Male> a vocab:Sex ;
    rdfs:label "Sex: Male" .
"""

MINIMAL_TURTLE = "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n"

ALL_DATASETS = ("dprr", "pleiades", "periodo", "nomisma", "crro", "ocre", "edh")


@pytest.fixture
def patched_app_context(tmp_path, monkeypatch):
    """Build an AppContext with all plugins using local TTL fixtures (no downloads).

    DPRR gets rich sample data; all other datasets get minimal stubs.
    """
    monkeypatch.setenv("LINKED_PAST_DATA_DIR", str(tmp_path))

    # Create dataset directories and TTL files
    dprr_dir = tmp_path / "dprr"
    dprr_dir.mkdir()
    (dprr_dir / "dprr.ttl").write_text(SAMPLE_DPRR_TURTLE)

    for dataset in ALL_DATASETS:
        if dataset == "dprr":
            continue
        ds_dir = tmp_path / dataset
        ds_dir.mkdir()
        (ds_dir / f"{dataset}.ttl").write_text(MINIMAL_TURTLE)

    # Patch fetch on all plugins to return local files
    # NOTE: must accept force= kwarg since initialize_dataset passes force=force
    for dataset in ALL_DATASETS:
        module_path = f"linked_past.datasets.{dataset}.plugin"
        class_name = {
            "dprr": "DPRRPlugin", "pleiades": "PleiadesPlugin",
            "periodo": "PeriodOPlugin", "nomisma": "NomismaPlugin",
            "crro": "CRROPlugin", "ocre": "OCREPlugin", "edh": "EDHPlugin",
        }[dataset]
        monkeypatch.setattr(
            f"{module_path}.{class_name}.fetch",
            lambda self, data_dir, force=False, _ds=dataset: data_dir / f"{_ds}.ttl",
        )

    return build_app_context(eager=True, skip_search=True)
```

- [ ] **Step 2: Update test_server.py to use shared fixture**

```python
# tests/test_server.py
from linked_past.core.server import create_mcp_server


def test_build_app_context(patched_app_context):
    assert "dprr" in patched_app_context.registry.list_datasets()
    store = patched_app_context.registry.get_store("dprr")
    assert store is not None


def test_create_mcp_server():
    mcp = create_mcp_server()
    tool_names = [t.name for t in mcp._tool_manager.list_tools()]
    assert "discover_datasets" in tool_names
    assert "get_schema" in tool_names
    assert "validate_sparql" in tool_names
    assert "query" in tool_names
    assert "disambiguate" in tool_names
```

- [ ] **Step 3: Update test_linked_past_integration.py to use shared fixture**

Replace the `integration_ctx` fixture with `patched_app_context`:

```python
# tests/test_linked_past_integration.py
"""End-to-end integration test for the linked-past server with DPRR plugin."""

import json

from linked_past.core.validate import parse_and_fix_prefixes, validate_and_execute


def test_discover_lists_dprr(patched_app_context):
    datasets = patched_app_context.registry.list_datasets()
    assert "dprr" in datasets


def test_get_schema_has_classes(patched_app_context):
    plugin = patched_app_context.registry.get_plugin("dprr")
    schema = plugin.get_schema()
    assert "Person" in schema
    assert "PostAssertion" in schema
    assert "PREFIX vocab:" in schema


def test_validate_valid_query(patched_app_context):
    plugin = patched_app_context.registry.get_plugin("dprr")
    prefix_map = plugin.get_prefixes()
    sparql = (
        "PREFIX vocab: <http://romanrepublic.ac.uk/rdf/ontology#>\n"
        "SELECT ?p ?name WHERE { ?p a vocab:Person ; vocab:hasPersonName ?name }"
    )
    fixed, errors = parse_and_fix_prefixes(sparql, prefix_map)
    assert errors == []
    result = plugin.validate(fixed)
    assert result.valid is True


def test_validate_unknown_class_is_warning(patched_app_context):
    plugin = patched_app_context.registry.get_plugin("dprr")
    sparql = (
        "PREFIX vocab: <http://romanrepublic.ac.uk/rdf/ontology#>\n"
        "SELECT ?p WHERE { ?p a vocab:FakeClass }"
    )
    result = plugin.validate(sparql)
    assert result.valid is True


def test_execute_query_returns_results(patched_app_context):
    store = patched_app_context.registry.get_store("dprr")
    plugin = patched_app_context.registry.get_plugin("dprr")
    sparql = (
        "PREFIX vocab: <http://romanrepublic.ac.uk/rdf/ontology#>\n"
        "SELECT ?name WHERE { ?p a vocab:Person ; vocab:hasPersonName ?name }"
    )
    result = validate_and_execute(sparql, store, plugin.build_schema_dict(), plugin.get_prefixes())
    assert result.success is True
    assert len(result.rows) == 1
    assert "Brutus" in result.rows[0]["name"]


def test_execute_with_prefix_repair(patched_app_context):
    store = patched_app_context.registry.get_store("dprr")
    plugin = patched_app_context.registry.get_plugin("dprr")
    sparql = "SELECT ?name WHERE { ?p a vocab:Person ; vocab:hasPersonName ?name }"
    result = validate_and_execute(sparql, store, plugin.build_schema_dict(), plugin.get_prefixes())
    assert result.success is True
    assert len(result.rows) == 1


def test_registry_json_written(patched_app_context, tmp_path, monkeypatch):
    monkeypatch.setenv("LINKED_PAST_DATA_DIR", str(tmp_path))
    registry_path = tmp_path / "registry.json"
    assert registry_path.exists()
    data = json.loads(registry_path.read_text())
    assert "dprr" in data
    assert "version" in data["dprr"]
    assert data["dprr"]["triple_count"] > 0


def test_discover_datasets_topic_filter(patched_app_context):
    plugin = patched_app_context.registry.get_plugin("dprr")
    searchable = [plugin.description, plugin.display_name,
                  plugin.spatial_coverage, plugin.time_coverage]
    assert any("roman" in f.lower() for f in searchable)
    assert not any("medieval" in f.lower() for f in searchable)


def test_query_result_includes_citation(patched_app_context):
    store = patched_app_context.registry.get_store("dprr")
    plugin = patched_app_context.registry.get_plugin("dprr")
    result = validate_and_execute(
        "PREFIX vocab: <http://romanrepublic.ac.uk/rdf/ontology#>\n"
        "SELECT ?name WHERE { ?p a vocab:Person ; vocab:hasPersonName ?name }",
        store, plugin.build_schema_dict(), plugin.get_prefixes(),
    )
    assert result.success is True
    meta = patched_app_context.registry.get_metadata("dprr")
    assert "version" in meta
    assert plugin.citation != ""
```

- [ ] **Step 4: Run full test suite**

Run: `uv run pytest -x -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/linked-past/tests/conftest.py packages/linked-past/tests/test_server.py packages/linked-past/tests/test_linked_past_integration.py
git commit -m "refactor: extract shared integration test fixtures into conftest.py"
```

---

### Task 5: Consolidate Duplicate `_uri_to_dataset()`

`_uri_to_dataset()` is defined in both `DatasetRegistry` (as `dataset_for_uri`) and `MetaEntityIndex` (as `_uri_to_dataset`). They have the same namespace map with minor differences (MetaEntityIndex adds wikidata entries). Consolidate into `DatasetRegistry.dataset_for_uri()` and have MetaEntityIndex call it.

**Files:**
- Modify: `packages/linked-past/linked_past/core/registry.py:21-30`
- Modify: `packages/linked-past/linked_past/core/meta_entities.py:371-389`
- Modify: `packages/linked-past/tests/test_advanced_tools.py:58-61`
- Test: `packages/linked-past/tests/test_registry.py`

- [ ] **Step 1: Write test for expanded dataset_for_uri**

Add to `test_registry.py`. Note: after this change `dataset_for_uri` is a pure namespace lookup — it no longer checks plugin registration. This matches `MetaEntityIndex._uri_to_dataset` behavior:

```python
def test_dataset_for_uri_standard(tmp_path):
    reg = DatasetRegistry(data_dir=tmp_path)
    # No plugins registered — still returns dataset name from namespace map
    assert reg.dataset_for_uri("http://romanrepublic.ac.uk/rdf/entity/Person/1") == "dprr"
    assert reg.dataset_for_uri("https://pleiades.stoa.org/places/423025") == "pleiades"
    assert reg.dataset_for_uri("http://edh-www.adw.uni-heidelberg.de/edh/inschrift/HD000001") == "edh"
    assert reg.dataset_for_uri("https://edh-www.adw.uni-heidelberg.de/edh/inschrift/HD000001") == "edh"
    assert reg.dataset_for_uri("http://www.wikidata.org/entity/Q1234") == "wikidata"
    assert reg.dataset_for_uri("http://example.org/unknown") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/linked-past/tests/test_registry.py::test_dataset_for_uri_standard -v`
Expected: FAIL — wikidata entries not in `_URI_NAMESPACES` yet, and current code requires plugin registration.

- [ ] **Step 3: Add wikidata namespaces to DatasetRegistry._URI_NAMESPACES**

In `packages/linked-past/linked_past/core/registry.py`, add to `_URI_NAMESPACES`:

```python
    _URI_NAMESPACES: dict[str, str] = {
        "http://romanrepublic.ac.uk/rdf/": "dprr",
        "https://pleiades.stoa.org/places/": "pleiades",
        "http://n2t.net/ark:/99152/": "periodo",
        "http://nomisma.org/id/": "nomisma",
        "http://numismatics.org/crro/id/": "crro",
        "http://numismatics.org/ocre/id/": "ocre",
        "http://edh-www.adw.uni-heidelberg.de/edh/": "edh",
        "https://edh-www.adw.uni-heidelberg.de/edh/": "edh",
        "http://www.wikidata.org/entity/": "wikidata",
        "https://www.wikidata.org/wiki/": "wikidata",
    }
```

Also remove the `if name in self._plugins` check from `dataset_for_uri` — it should return the dataset name even if the plugin isn't registered (MetaEntityIndex needs this for wikidata which has no plugin):

```python
    def dataset_for_uri(self, uri: str) -> str | None:
        """Determine which dataset a URI belongs to based on namespace."""
        for ns, name in self._URI_NAMESPACES.items():
            if uri.startswith(ns):
                return name
        return None
```

- [ ] **Step 3b: Update test_advanced_tools.py to match new behavior**

The existing `test_dataset_for_uri_unregistered` at `packages/linked-past/tests/test_advanced_tools.py:58-61` asserts that an unregistered namespace returns `None`. After this change, `dataset_for_uri` is a pure namespace lookup — it returns the name regardless of registration. Update the test:

```python
def test_dataset_for_uri_unregistered():
    """URI matches namespace even when plugin is not registered (pure namespace lookup)."""
    reg = DatasetRegistry(data_dir=Path("/tmp"))
    assert reg.dataset_for_uri("http://romanrepublic.ac.uk/rdf/entity/Person/1") == "dprr"
```

- [ ] **Step 4: Update MetaEntityIndex to use DatasetRegistry.dataset_for_uri**

In `packages/linked-past/linked_past/core/meta_entities.py`, replace the static `_uri_to_dataset` method:

```python
    @staticmethod
    def _uri_to_dataset(uri: str) -> str | None:
        """Determine dataset from URI namespace."""
        from linked_past.core.registry import DatasetRegistry
        # Use the canonical namespace map from the registry
        for ns, name in DatasetRegistry._URI_NAMESPACES.items():
            if uri.startswith(ns):
                return name
        return None
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest packages/linked-past/tests/test_registry.py packages/linked-past/tests/test_advanced_tools.py -v`
Expected: All PASS.

- [ ] **Step 6: Run full test suite**

Run: `uv run pytest -x -v`
Expected: All PASS.

- [ ] **Step 7: Commit**

```bash
git add packages/linked-past/linked_past/core/registry.py packages/linked-past/linked_past/core/meta_entities.py packages/linked-past/tests/test_registry.py packages/linked-past/tests/test_advanced_tools.py
git commit -m "refactor: consolidate _uri_to_dataset into DatasetRegistry._URI_NAMESPACES"
```

---

### Task 6: Split _run_heuristics() into Composable Checkers

The 170-line `_run_heuristics()` function in `validate.py:108-276` has 5 distinct checks crammed into one function. Split into individual checker functions that each take the same arguments and return `list[str]`.

**Files:**
- Modify: `packages/linked-past/linked_past/core/validate.py:108-276`
- Test: `packages/linked-past/tests/test_core_validate.py`

- [ ] **Step 1: Write targeted tests for each heuristic**

Add to `test_core_validate.py`:

```python
from linked_past.core.validate import (
    _check_boolean_escalation,
    _check_contradictory_types,
    _check_bc_date_sign,
    _parse_triples_and_types,
)


def test_check_contradictory_types():
    schema_dict = {
        "http://example.org/Person": {"_meta": {}},
        "http://example.org/Office": {"_meta": {}},
    }
    sparql = (
        "PREFIX ex: <http://example.org/>\n"
        "SELECT ?x WHERE { ?x a ex:Person . ?x a ex:Office }"
    )
    _, var_types, _ = _parse_triples_and_types(sparql)
    hints = _check_contradictory_types(var_types, schema_dict)
    assert any("typed as both" in h for h in hints)


def test_check_bc_date_sign():
    schema_dict = {
        "http://example.org/Person": {
            "http://example.org/hasEra": {
                "comment": "Negative integers for BC dates",
                "ranges": [],
            },
        },
    }
    sparql = (
        "PREFIX ex: <http://example.org/>\n"
        "SELECT ?p WHERE { ?p a ex:Person ; ex:hasEra ?e . FILTER(?e > 100) }"
    )
    _, _, var_preds = _parse_triples_and_types(sparql)
    hints = _check_bc_date_sign(sparql, var_preds, schema_dict)
    assert any("negative" in h.lower() or "BC" in h for h in hints)


def test_check_boolean_escalation():
    hints = _check_boolean_escalation(["open-world boolean warning: ..."])
    assert any("open-world boolean" in h.lower() for h in hints)

    hints = _check_boolean_escalation([])
    assert hints == []

    hints = _check_boolean_escalation(None)
    assert hints == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/linked-past/tests/test_core_validate.py -v -k "check_contradictory or check_bc or check_boolean"`
Expected: FAIL — functions don't exist yet.

- [ ] **Step 3: Extract checker functions**

In `packages/linked-past/linked_past/core/validate.py`, replace the body of `_run_heuristics` with calls to individual functions. Add these functions right before `_run_heuristics`:

```python
def _parse_triples_and_types(sparql: str) -> tuple[list[tuple], dict[str, list[str]], dict[str, list[str]]]:
    """Parse SPARQL to extract triples, variable types, and variable predicates."""
    triples: list[tuple] = []
    var_types: dict[str, list[str]] = {}
    var_preds: dict[str, list[str]] = {}
    try:
        triples = _collect_triples(sparql)
        for s, p, o in triples:
            if p == RDF_TYPE and isinstance(s, Variable) and isinstance(o, URIRef):
                var_types.setdefault(str(s), []).append(str(o))
    except Exception:
        pass
    for s, p, o in triples:
        if isinstance(p, URIRef) and isinstance(o, Variable):
            var_preds.setdefault(str(o), []).append(str(p))
    return triples, var_types, var_preds


All checker functions accept pre-parsed data (triples, var_types, var_preds) to avoid re-parsing the SPARQL for each check. `_run_heuristics` parses once and passes the results through.

```python
def _check_boolean_escalation(semantic_hints: list[str] | None) -> list[str]:
    """Escalate open-world boolean warnings from pre-execution."""
    if not semantic_hints:
        return []
    for hint in semantic_hints:
        if "open-world boolean" in hint.lower():
            return [
                "Diagnostic: This query returned 0 rows. The open-world boolean "
                "warning above is likely the cause — the property only stores "
                "true values, so filtering for false always yields nothing."
            ]
    return []


def _check_contradictory_types(
    var_types: dict[str, list[str]],
    schema_dict: dict,
) -> list[str]:
    """Detect variables typed as two different known classes simultaneously."""
    hints = []
    for var_name, types in var_types.items():
        if len(types) > 1:
            known = [t for t in types if t in schema_dict]
            if len(known) > 1:
                names = [_local_name(t) for t in known]
                hints.append(
                    f"Diagnostic: ?{var_name} is typed as both {' and '.join(names)}. "
                    f"No entity is likely to satisfy both types simultaneously. "
                    f"Use separate variables for each type."
                )
    return hints


def _check_bc_date_sign(
    sparql: str,
    var_preds: dict[str, list[str]],
    schema_dict: dict,
) -> list[str]:
    """Detect positive integers used with BC date fields that expect negatives."""
    bc_preds: set[str] = set()
    for class_uri, preds in schema_dict.items():
        for pred_uri, pred_info in preds.items():
            if pred_uri == "_meta" or not isinstance(pred_info, dict):
                continue
            comment = pred_info.get("comment", "").lower()
            if "negative" in comment and "bc" in comment:
                bc_preds.add(pred_uri)

    if not bc_preds:
        return []

    hints = []
    filter_pattern = re.compile(
        r"FILTER\s*\(.*?\?\s*(\w+)\s*(?:>|>=|=)\s*(\d+)",
        re.IGNORECASE,
    )
    for match in filter_pattern.finditer(sparql):
        var_name = match.group(1)
        value = int(match.group(2))
        if value > 0:
            for pred_uri in var_preds.get(var_name, []):
                if pred_uri in bc_preds:
                    pred_local = _local_name(pred_uri)
                    hints.append(
                        f"Diagnostic: '{pred_local}' uses negative integers for BC dates. "
                        f"Your filter compares ?{var_name} against {value} (a positive "
                        f"number, meaning AD). For BC dates, use negative values "
                        f"(e.g., -100 for 100 BC)."
                    )
                    break
    return hints


def _check_date_padding(
    sparql: str,
    var_preds: dict[str, list[str]],
    schema_dict: dict,
) -> list[str]:
    """Detect unpadded year literals and string comparisons on date fields."""
    date_preds: dict[str, str] = {}
    for class_uri, preds in schema_dict.items():
        for pred_uri, pred_info in preds.items():
            if pred_uri == "_meta" or not isinstance(pred_info, dict):
                continue
            dt = pred_info.get("datatype", "")
            if dt:
                for suffix in _DATE_SUFFIXES:
                    if dt.endswith(suffix):
                        date_preds[pred_uri] = suffix
                        break

    if not date_preds:
        return []

    hints = []

    # Unpadded year
    date_filter = re.compile(
        r"""FILTER\s*\(.*?\?(\w+)\s*(?:[<>=!]+)\s*"(-?\d{1,3})(?:["-])""",
        re.IGNORECASE,
    )
    for match in date_filter.finditer(sparql):
        var_name = match.group(1)
        year_val = match.group(2)
        for pred_uri in var_preds.get(var_name, []):
            if pred_uri in date_preds:
                pred_local = _local_name(pred_uri)
                dtype = date_preds[pred_uri]
                padded = year_val.zfill(4) if not year_val.startswith("-") else "-" + year_val[1:].zfill(4)
                if dtype == "gYear":
                    example = f'"{padded}"^^xsd:gYear'
                else:
                    example = f'"{padded}-01-01"^^xsd:{dtype}'
                hints.append(
                    f"Diagnostic: '{pred_local}' uses xsd:{dtype} with zero-padded 4-digit years. "
                    f'Your value "{year_val}" needs padding: use {example} '
                    f'(e.g., "-0044-03-15"^^xsd:date for 44 BC).'
                )
                break

    # String comparison without type cast
    untyped_date = re.compile(
        r"""FILTER\s*\(.*?\?(\w+)\s*[<>=!]+\s*"(-?\d{4})"(?!\s*\^\^)""",
        re.IGNORECASE,
    )
    for match in untyped_date.finditer(sparql):
        var_name = match.group(1)
        year_val = match.group(2)
        for pred_uri in var_preds.get(var_name, []):
            if pred_uri in date_preds:
                pred_local = _local_name(pred_uri)
                hints.append(
                    f'Diagnostic: Comparing \'{pred_local}\' as a plain string "{year_val}" '
                    f"will give wrong results for date ranges (string ordering ≠ chronological). "
                    f"Use xsd:integer cast: FILTER(xsd:integer(?{var_name}) >= {int(year_val)}) "
                    f'or typed literal: FILTER(?{var_name} >= "{year_val}"^^xsd:gYear).'
                )
                break

    return hints


def _check_string_uri_mismatch(
    sparql: str,
    triples: list[tuple],
    var_types: dict[str, list[str]],
    schema_dict: dict,
) -> list[str]:
    """Detect string literal comparison on a property whose range is a URI/entity."""
    var_range_types: dict[str, list[str]] = {}
    for s, p, o in triples:
        if isinstance(p, URIRef) and isinstance(o, Variable) and isinstance(s, Variable):
            pred_uri = str(p)
            s_name = str(s)
            for class_uri in var_types.get(s_name, []):
                if class_uri not in schema_dict:
                    continue
                pred_info = schema_dict[class_uri].get(pred_uri)
                if isinstance(pred_info, dict):
                    for range_uri in pred_info.get("ranges", []):
                        var_range_types.setdefault(str(o), []).append(range_uri)

    hints = []
    string_filter = re.compile(
        r"""FILTER\s*\(.*?\?(\w+)\s*=\s*"([^"]*)"(?:\^\^[^ )]*)?""",
        re.IGNORECASE,
    )
    for match in string_filter.finditer(sparql):
        var_name = match.group(1)
        ranges = var_range_types.get(var_name, [])
        for range_uri in ranges:
            if not range_uri.startswith(_XSD_NS):
                range_local = _local_name(range_uri)
                hints.append(
                    f"Diagnostic: ?{var_name} has range {range_local} (a URI/entity), "
                    f"but you're comparing it to a string literal. Use the entity URI "
                    f"or match via rdfs:label on the linked entity."
                )
                break

    return hints
```

Then replace the body of `_run_heuristics`. It parses the SPARQL once and passes the pre-parsed data to all checkers:

```python
def _run_heuristics(
    sparql: str,
    schema_dict: dict,
    prefix_map: dict[str, str],
    dataset: str | None,
    semantic_hints: list[str] | None,
) -> list[str]:
    """Zero-cost heuristic checks on the SPARQL AST."""
    # Parse once, pass to all checkers
    triples, var_types, var_preds = _parse_triples_and_types(sparql)

    hints: list[str] = []
    hints.extend(_check_boolean_escalation(semantic_hints))
    hints.extend(_check_contradictory_types(var_types, schema_dict))
    hints.extend(_check_bc_date_sign(sparql, var_preds, schema_dict))
    hints.extend(_check_date_padding(sparql, var_preds, schema_dict))
    hints.extend(_check_string_uri_mismatch(sparql, triples, var_types, schema_dict))
    return hints
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest packages/linked-past/tests/test_core_validate.py -v`
Expected: All PASS (both new targeted tests and existing tests).

- [ ] **Step 5: Run full test suite**

Run: `uv run pytest -x -v`
Expected: All PASS.

- [ ] **Step 6: Commit**

```bash
git add packages/linked-past/linked_past/core/validate.py packages/linked-past/tests/test_core_validate.py
git commit -m "refactor: split _run_heuristics into composable checker functions"
```

---

### Task 7: Clean Up `check_for_updates()` Dead Code Path

`check_for_updates()` returns `None` in all 7 plugins (now on the base class after Task 1). It **is** called in `server.py:1287` inside the `update_dataset` tool handler, but the result is always `None`, so the `if update_info:` branch at line 1294 is dead code. Remove the dead branch from server.py and the `UpdateInfo` dataclass from base.py, but keep the `check_for_updates` stub on the base class so the call site doesn't break.

**Files:**
- Modify: `packages/linked-past/linked_past/core/server.py:1287-1301`
- Modify: `packages/linked-past/linked_past/datasets/base.py`

- [ ] **Step 1: Remove UpdateInfo dataclass from base.py**

In `packages/linked-past/linked_past/datasets/base.py`, delete the `UpdateInfo` dataclass. Keep the `check_for_updates` method but simplify its return type:

```python
    def check_for_updates(self) -> None:
        """Compare local vs upstream. Returns None (not yet implemented)."""
        return None
```

- [ ] **Step 2: Remove dead `if update_info:` branch from server.py**

In `packages/linked-past/linked_past/core/server.py`, replace lines 1287-1301:

```python
            update_info = plugin.check_for_updates()

            lines.append(f"## {plugin.display_name}\n")
            lines.append(f"- **Current version:** {version}")
            lines.append(f"- **Triples:** {triple_count}")
            lines.append(f"- **OCI artifact:** {plugin.oci_dataset}:{plugin.oci_version}")

            if update_info:
                lines.append(f"- **Available:** {update_info.available}")
                if update_info.changelog_url:
                    lines.append(f"- **Changelog:** {update_info.changelog_url}")
                lines.append("\nTo update, re-initialize with a fresh data directory.")
            else:
                lines.append("- **Status:** Up to date (or no update check available)")
            lines.append("")
```

With:

```python
            lines.append(f"## {plugin.display_name}\n")
            lines.append(f"- **Current version:** {version}")
            lines.append(f"- **Triples:** {triple_count}")
            lines.append(f"- **OCI artifact:** {plugin.oci_dataset}:{plugin.oci_version}")
            lines.append("- **Status:** Up to date (or no update check available)")
            lines.append("")
```

- [ ] **Step 3: Remove any remaining UpdateInfo imports**

```bash
grep -r "UpdateInfo" packages/linked-past/ --include="*.py" | grep -v "__pycache__"
```

Remove any imports found (plugins should have none after Task 1; server.py may still import it).

- [ ] **Step 4: Run full test suite**

Run: `uv run pytest -x -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/linked-past/linked_past/datasets/base.py packages/linked-past/linked_past/core/server.py
git commit -m "cleanup: remove UpdateInfo and dead check_for_updates branch"
```

---

### Task 8: Clean Up test_multi_dataset_integration.py

After Tasks 2-3, `test_multi_dataset_integration.py` is partially redundant with the parametrized test suite. Update it to use `discover_plugins()` instead of importing all 7 classes, and remove the duplicated `test_all_plugins_*` tests that are now in `test_plugins.py`.

**Files:**
- Modify: `packages/linked-past/tests/test_multi_dataset_integration.py`

- [ ] **Step 1: Rewrite the file**

```python
# tests/test_multi_dataset_integration.py
"""Cross-cutting integration tests: all plugins load and server registers them."""

from linked_past.core.registry import discover_plugins
from linked_past.core.server import create_mcp_server

EXPECTED_DATASETS = {"dprr", "pleiades", "periodo", "nomisma", "crro", "ocre", "edh"}


def test_discover_finds_all_datasets():
    plugins = discover_plugins()
    names = {p.name for p in plugins}
    assert names == EXPECTED_DATASETS


def test_server_registers_all_plugins():
    mcp = create_mcp_server()
    tool_names = [t.name for t in mcp._tool_manager.list_tools()]
    assert "discover_datasets" in tool_names
    assert "query" in tool_names
```

- [ ] **Step 2: Run tests**

Run: `uv run pytest packages/linked-past/tests/test_multi_dataset_integration.py -v`
Expected: All PASS.

- [ ] **Step 3: Commit**

```bash
git add packages/linked-past/tests/test_multi_dataset_integration.py
git commit -m "cleanup: simplify multi-dataset integration test to use discover_plugins"
```

---

## Summary

| Task | What | Lines removed (approx) | Lines added (approx) |
|------|------|----------------------|---------------------|
| 1 | Plugin base class consolidation | ~600 (7 plugins) | ~150 (base.py) |
| 2 | Parametrized plugin tests | ~500 (6 test files) | ~100 (1 test file) |
| 3 | Auto-discover plugins | ~20 (server.py imports) | ~15 (registry + datasets/__init__) |
| 4 | Shared test fixtures | ~60 (duplicated patches) | ~50 (conftest.py) |
| 5 | Consolidate _uri_to_dataset | ~20 (meta_entities.py) | ~5 (registry.py) |
| 6 | Split _run_heuristics | ~170 (monolith) | ~180 (5 focused functions) |
| 7 | Clean up check_for_updates dead code | ~20 | 0 |
| 8 | Clean up multi-dataset test | ~30 | ~15 |
| **Total** | | **~1415** | **~515** |

**Net reduction: ~900 lines of code.**
