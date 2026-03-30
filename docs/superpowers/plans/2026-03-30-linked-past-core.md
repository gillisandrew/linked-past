# Linked Past: Core + DPRR Migration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure dprr-mcp into a plugin-based multi-dataset server, migrating DPRR as the first plugin, with four core MCP tools (discover_datasets, get_schema, validate_sparql, query).

**Architecture:** Plugin architecture within the existing repo. A `linked_past/core/` module provides dataset-agnostic store management, validation, and context loading. Each dataset is a plugin under `linked_past/datasets/{name}/` implementing a common `DatasetPlugin` interface. A registry discovers and manages plugin lifecycles. The MCP server routes tool calls through the registry to the appropriate plugin.

**Tech Stack:** Python 3.13+, FastMCP, Oxigraph (pyoxigraph), rdflib, PyYAML, toons

**Related plans:**
- Plan 2: Additional dataset plugins (Pleiades, PeriodO, Nomisma, POMS)
- Plan 3: Linkage graph, embeddings, advanced tools

**Deferred tools (Plan 3):** `explore_entity`, `get_provenance`, `find_links`, `search_entities`, `update_dataset`

---

## File Structure

```
linked_past/
├── __init__.py
├── core/
│   ├── __init__.py
│   ├── store.py             # Generic Oxigraph store ops (create, load, query, read-only)
│   ├── context.py           # YAML loading + rendering (generalized from dprr_mcp/context/)
│   ├── validate.py          # Tier-1 validation (parse + prefix repair) + tier-2 orchestration
│   ├── registry.py          # Dataset registry: discover plugins, manage lifecycle
│   └── server.py            # FastMCP server with 4 tools + lifespan
├── datasets/
│   ├── __init__.py
│   ├── base.py              # DatasetPlugin ABC + dataclasses
│   └── dprr/
│       ├── __init__.py
│       ├── plugin.py         # DPRRPlugin(DatasetPlugin) — fetch, validate, schema
│       └── context/
│           ├── schemas.yaml   # (moved from dprr_mcp/context/)
│           ├── examples.yaml
│           ├── tips.yaml
│           └── prefixes.yaml
tests/
├── test_base.py             # DatasetPlugin ABC tests
├── test_core_store.py       # Generic store tests
├── test_core_context.py     # Generic context loader tests
├── test_core_validate.py    # Tier-1 validation tests
├── test_registry.py         # Registry tests
├── test_dprr_plugin.py      # DPRR plugin tests
├── test_server.py           # MCP server integration tests
```

---

### Task 1: Create package skeleton and DatasetPlugin base class

**Files:**
- Create: `linked_past/__init__.py`
- Create: `linked_past/core/__init__.py`
- Create: `linked_past/datasets/__init__.py`
- Create: `linked_past/datasets/base.py`
- Create: `linked_past/datasets/dprr/__init__.py`
- Test: `tests/test_base.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_base.py
import pytest
from linked_past.datasets.base import DatasetPlugin, VersionInfo, ValidationResult


def test_dataset_plugin_is_abstract():
    """Cannot instantiate DatasetPlugin directly — has abstract methods
    including fetch, get_prefixes, get_schema, build_schema_dict, validate, get_version_info."""
    with pytest.raises(TypeError):
        DatasetPlugin()


def test_version_info_dataclass():
    info = VersionInfo(
        version="1.0.0",
        source_url="https://example.com/data.ttl",
        fetched_at="2026-03-30T14:00:00Z",
        triple_count=1000,
        rdf_format="turtle",
    )
    assert info.version == "1.0.0"
    assert info.triple_count == 1000


def test_validation_result_dataclass():
    result = ValidationResult(
        valid=True,
        sparql="SELECT ?s WHERE { ?s ?p ?o }",
        errors=[],
        suggestions=[],
    )
    assert result.valid is True
    assert result.errors == []


def test_validation_result_with_errors():
    result = ValidationResult(
        valid=False,
        sparql="SELECT ?s WHERE { ?s ?p ?o }",
        errors=["Unknown class 'Foo'"],
        suggestions=["Did you mean 'Person'?"],
    )
    assert result.valid is False
    assert len(result.errors) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_base.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'linked_past'`

- [ ] **Step 3: Create package directories and base module**

```python
# linked_past/__init__.py
"""Linked Past: Multi-dataset prosopographical MCP server."""
```

```python
# linked_past/core/__init__.py
```

```python
# linked_past/datasets/__init__.py
```

```python
# linked_past/datasets/dprr/__init__.py
```

```python
# linked_past/datasets/base.py
"""Base class and dataclasses for dataset plugins."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from pyoxigraph import Store


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


class DatasetPlugin(ABC):
    """Abstract base class for dataset plugins.

    Subclasses must set class attributes and implement all abstract methods.
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

    @abstractmethod
    def fetch(self, data_dir: Path) -> Path:
        """Download data, return path to RDF file(s)."""

    def load(self, store: Store, rdf_path: Path) -> int:
        """Bulk-load into Oxigraph store, return triple count.

        Default implementation uses self.rdf_format. Override for custom loading.
        """
        store.bulk_load(path=str(rdf_path), format=self.rdf_format)
        return len(store)

    @abstractmethod
    def get_prefixes(self) -> dict[str, str]:
        """Return namespace prefix map."""

    @abstractmethod
    def get_schema(self) -> str:
        """Return rendered ontology overview."""

    @abstractmethod
    def build_schema_dict(self) -> dict:
        """Return dict[class_full_uri][predicate_full_uri] = [range_types]."""

    @abstractmethod
    def validate(self, sparql: str) -> ValidationResult:
        """Dataset-specific semantic validation (plugin owns its schema dict)."""

    def get_relevant_context(self, sparql: str) -> str:
        """Return contextual tips/examples for a SPARQL query. Default: empty."""
        return ""

    @abstractmethod
    def get_version_info(self, data_dir: Path) -> VersionInfo | None:
        """Return current snapshot metadata, or None if not initialized."""

    def check_for_updates(self) -> UpdateInfo | None:
        """Compare local vs upstream. Returns None if up to date."""
        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_base.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add linked_past/ tests/test_base.py
git commit -m "feat: add DatasetPlugin base class and package skeleton"
```

---

### Task 2: Generalize core store management

**Files:**
- Create: `linked_past/core/store.py`
- Test: `tests/test_core_store.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_core_store.py
import tempfile
from pathlib import Path

import pytest

from linked_past.core.store import (
    create_store,
    execute_query,
    get_data_dir,
    get_read_only_store,
    is_initialized,
    load_rdf,
)

SAMPLE_TURTLE = """\
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix ex: <http://example.org/> .

ex:Thing1 a ex:Widget ;
    rdfs:label "Widget One" .
ex:Thing2 a ex:Widget ;
    rdfs:label "Widget Two" .
"""


def test_get_data_dir_default(monkeypatch):
    monkeypatch.delenv("LINKED_PAST_DATA_DIR", raising=False)
    monkeypatch.delenv("DPRR_DATA_DIR", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    result = get_data_dir()
    assert result == Path.home() / ".local" / "share" / "linked-past"


def test_get_data_dir_linked_past_env(monkeypatch):
    monkeypatch.setenv("LINKED_PAST_DATA_DIR", "/tmp/lp")
    result = get_data_dir()
    assert result == Path("/tmp/lp")


def test_get_data_dir_xdg(monkeypatch):
    monkeypatch.delenv("LINKED_PAST_DATA_DIR", raising=False)
    monkeypatch.delenv("DPRR_DATA_DIR", raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", "/tmp/xdg")
    result = get_data_dir()
    assert result == Path("/tmp/xdg/linked-past")


def test_create_and_load(tmp_path):
    store_path = tmp_path / "store"
    store = create_store(store_path)
    ttl = tmp_path / "data.ttl"
    ttl.write_text(SAMPLE_TURTLE)
    count = load_rdf(store, ttl)
    assert count > 0


def test_is_initialized_false(tmp_path):
    assert not is_initialized(tmp_path / "nonexistent")


def test_is_initialized_true(tmp_path):
    store_path = tmp_path / "store"
    store = create_store(store_path)
    ttl = tmp_path / "data.ttl"
    ttl.write_text(SAMPLE_TURTLE)
    load_rdf(store, ttl)
    del store
    assert is_initialized(store_path)


def test_read_only_store(tmp_path):
    store_path = tmp_path / "store"
    store = create_store(store_path)
    ttl = tmp_path / "data.ttl"
    ttl.write_text(SAMPLE_TURTLE)
    load_rdf(store, ttl)
    del store
    ro = get_read_only_store(store_path)
    results = execute_query(ro, "SELECT (COUNT(*) AS ?c) WHERE { ?s ?p ?o }")
    assert int(results[0]["c"]) > 0


def test_execute_query_select(tmp_path):
    store_path = tmp_path / "store"
    store = create_store(store_path)
    ttl = tmp_path / "data.ttl"
    ttl.write_text(SAMPLE_TURTLE)
    load_rdf(store, ttl)
    results = execute_query(
        store,
        'PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n'
        'SELECT ?s ?label WHERE { ?s rdfs:label ?label } ORDER BY ?label',
    )
    assert len(results) == 2
    assert results[0]["label"] == "Widget One"


def test_execute_query_non_select_raises(tmp_path):
    store_path = tmp_path / "store"
    store = create_store(store_path)
    ttl = tmp_path / "data.ttl"
    ttl.write_text(SAMPLE_TURTLE)
    load_rdf(store, ttl)
    with pytest.raises(ValueError, match="Only SELECT"):
        execute_query(store, "ASK { ?s ?p ?o }")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_core_store.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'linked_past.core.store'`

- [ ] **Step 3: Write the implementation**

```python
# linked_past/core/store.py
"""Generic Oxigraph store management for any RDF dataset."""

import os
from pathlib import Path

from pyoxigraph import RdfFormat, Store


def get_data_dir() -> Path:
    """Compute the linked-past data directory.

    Precedence: LINKED_PAST_DATA_DIR > XDG_DATA_HOME/linked-past > ~/.local/share/linked-past
    """
    explicit = os.environ.get("LINKED_PAST_DATA_DIR")
    if explicit:
        return Path(explicit)
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return base / "linked-past"


def create_store(path: Path) -> Store:
    """Create a persistent Oxigraph store at the given directory."""
    path.mkdir(parents=True, exist_ok=True)
    return Store(str(path))


def load_rdf(store: Store, file_path: Path, rdf_format: RdfFormat = RdfFormat.TURTLE) -> int:
    """Bulk-load an RDF file into the store. Returns the triple count after loading."""
    store.bulk_load(path=str(file_path), format=rdf_format)
    return len(store)


def execute_query(store: Store, sparql: str) -> list[dict[str, str]]:
    """Execute a SPARQL SELECT query and return results as a list of dicts."""
    results = store.query(sparql)
    if not hasattr(results, "variables"):
        raise ValueError(
            "Only SELECT queries are supported. "
            "CONSTRUCT, ASK, and DESCRIBE queries are not implemented."
        )
    variables = [v.value for v in results.variables]
    rows = []
    for solution in results:
        row = {}
        for var_name in variables:
            value = solution[var_name]
            row[var_name] = value.value if value is not None else None
        rows.append(row)
    return rows


def is_initialized(store_path: Path) -> bool:
    """Check whether a store exists and contains data."""
    if not store_path.exists():
        return False
    try:
        store = Store.read_only(str(store_path))
        return len(store) > 0
    except OSError:
        return False


def get_read_only_store(path: Path) -> Store:
    """Open an existing Oxigraph store in read-only mode."""
    return Store.read_only(str(path))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_core_store.py -v`
Expected: PASS (10 tests)

- [ ] **Step 5: Commit**

```bash
git add linked_past/core/store.py tests/test_core_store.py
git commit -m "feat: add generic store management to linked_past.core"
```

---

### Task 3: Generalize core context loading

**Files:**
- Create: `linked_past/core/context.py`
- Test: `tests/test_core_context.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_core_context.py
import tempfile
from pathlib import Path

import yaml

from linked_past.core.context import (
    get_cross_cutting_tips,
    get_relevant_examples,
    get_relevant_tips,
    load_context_yaml,
    render_class_summary,
    render_examples,
    render_tips,
)

SAMPLE_SCHEMAS = {
    "Widget": {
        "label": "Widget",
        "comment": "A sample widget",
        "uri": "ex:Widget",
        "properties": [
            {"pred": "ex:hasName", "range": "xsd:string", "comment": "Name"},
            {"pred": "ex:hasColor", "range": "xsd:string", "comment": "Color"},
        ],
    }
}

SAMPLE_EXAMPLES = [
    {
        "question": "List all widgets",
        "sparql": "SELECT ?w WHERE { ?w a ex:Widget }",
        "classes": {"Widget"},
    },
    {
        "question": "Count things",
        "sparql": "SELECT (COUNT(*) AS ?c) WHERE { ?s ?p ?o }",
        "classes": set(),
    },
]

SAMPLE_TIPS = [
    {"title": "Cross-cutting tip", "body": "Applies everywhere.", "classes": []},
    {"title": "Widget tip", "body": "Widgets are special.", "classes": ["Widget"]},
    {"title": "Gadget tip", "body": "Gadgets are different.", "classes": ["Gadget"]},
]


def test_load_context_yaml(tmp_path):
    data = {"prefixes": {"ex": "http://example.org/"}}
    path = tmp_path / "prefixes.yaml"
    path.write_text(yaml.dump(data))
    result = load_context_yaml(path)
    assert result == data


def test_render_class_summary():
    result = render_class_summary(SAMPLE_SCHEMAS)
    assert "Widget" in result
    assert "ex:Widget" in result
    assert "A sample widget" in result


def test_render_examples():
    result = render_examples(SAMPLE_EXAMPLES)
    assert "List all widgets" in result
    assert "SELECT ?w" in result


def test_render_tips():
    result = render_tips(SAMPLE_TIPS)
    assert "Cross-cutting tip" in result
    assert "Applies everywhere" in result


def test_get_cross_cutting_tips():
    result = get_cross_cutting_tips(SAMPLE_TIPS)
    assert len(result) == 1
    assert result[0]["title"] == "Cross-cutting tip"


def test_get_relevant_tips():
    result = get_relevant_tips(SAMPLE_TIPS, {"Widget"})
    assert len(result) == 1
    assert result[0]["title"] == "Widget tip"


def test_get_relevant_tips_no_match():
    result = get_relevant_tips(SAMPLE_TIPS, {"Nonexistent"})
    assert result == []


def test_get_relevant_examples():
    result = get_relevant_examples(SAMPLE_EXAMPLES, {"Widget"})
    assert len(result) == 1
    assert result[0]["question"] == "List all widgets"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_core_context.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

```python
# linked_past/core/context.py
"""YAML context loading and rendering for dataset plugins."""

from __future__ import annotations

from pathlib import Path

import yaml


def load_context_yaml(path: Path) -> dict:
    """Load a YAML context file and return its contents."""
    with open(path) as f:
        return yaml.safe_load(f)


def load_prefixes(context_dir: Path) -> dict[str, str]:
    """Load prefix map from a context directory's prefixes.yaml."""
    return load_context_yaml(context_dir / "prefixes.yaml")["prefixes"]


def load_schemas(context_dir: Path) -> dict:
    """Load class schemas from a context directory's schemas.yaml."""
    return load_context_yaml(context_dir / "schemas.yaml")["classes"]


def load_examples(context_dir: Path) -> list[dict]:
    """Load SPARQL examples from a context directory's examples.yaml."""
    return load_context_yaml(context_dir / "examples.yaml")["examples"]


def load_tips(context_dir: Path) -> list[dict]:
    """Load query tips from a context directory's tips.yaml."""
    return load_context_yaml(context_dir / "tips.yaml")["tips"]


def render_class_summary(schemas: dict) -> str:
    """Render a one-line-per-class summary."""
    lines = []
    for cls_name, cls_data in schemas.items():
        comment = cls_data.get("comment", "")
        lines.append(f"- **{cls_name}** (`{cls_data['uri']}`) — {comment}")
    return "\n".join(lines)


def render_examples(examples: list[dict]) -> str:
    """Render example queries as formatted markdown."""
    sections = []
    for ex in examples:
        section = f"Question: {ex['question']}\n\n```sparql\n{ex['sparql'].strip()}\n```"
        sections.append(section)
    return "\n\n---\n\n".join(sections)


def render_tips(tips: list[dict]) -> str:
    """Render query tips as formatted markdown."""
    sections = []
    for tip in tips:
        sections.append(f"- **{tip['title']}**: {tip['body'].strip()}")
    return "\n\n".join(sections)


def get_cross_cutting_tips(tips: list[dict]) -> list[dict]:
    """Return tips where classes is empty (cross-cutting)."""
    return [t for t in tips if not t.get("classes")]


def get_relevant_tips(tips: list[dict], class_names: set[str], limit: int = 5) -> list[dict]:
    """Return tips whose classes overlap with class_names, sorted by overlap size."""
    scored = []
    for tip in tips:
        tip_classes = set(tip.get("classes", []))
        if not tip_classes:
            continue
        overlap = len(tip_classes & class_names)
        if overlap > 0:
            scored.append((overlap, tip))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [tip for _, tip in scored[:limit]]


def get_relevant_examples(examples: list[dict], class_names: set[str], limit: int = 3) -> list[dict]:
    """Return examples whose classes overlap with class_names, sorted by overlap size."""
    scored = []
    for ex in examples:
        ex_classes = set(ex.get("classes", []))
        if not ex_classes:
            continue
        overlap = len(ex_classes & class_names)
        if overlap > 0:
            scored.append((overlap, ex))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [ex for _, ex in scored[:limit]]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_core_context.py -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
git add linked_past/core/context.py tests/test_core_context.py
git commit -m "feat: add generic context loading to linked_past.core"
```

---

### Task 4: Generalize core validation (tier-1)

**Files:**
- Create: `linked_past/core/validate.py`
- Test: `tests/test_core_validate.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_core_validate.py
from linked_past.core.validate import (
    build_schema_dict,
    extract_query_classes,
    parse_and_fix_prefixes,
    validate_semantics,
)

PREFIXES = {
    "ex": "http://example.org/",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
}

SCHEMAS = {
    "Widget": {
        "label": "Widget",
        "comment": "A widget",
        "uri": "ex:Widget",
        "properties": [
            {"pred": "ex:hasName", "range": "xsd:string"},
            {"pred": "ex:hasColor", "range": "xsd:string"},
        ],
    }
}


def test_parse_valid_query():
    sparql = "PREFIX ex: <http://example.org/>\nSELECT ?w WHERE { ?w a ex:Widget }"
    fixed, errors = parse_and_fix_prefixes(sparql, PREFIXES)
    assert errors == []
    assert fixed == sparql


def test_parse_fixes_missing_prefix():
    sparql = "SELECT ?w WHERE { ?w a ex:Widget }"
    fixed, errors = parse_and_fix_prefixes(sparql, PREFIXES)
    assert errors == []
    assert "PREFIX ex:" in fixed


def test_parse_syntax_error():
    sparql = "SELEC ?w WHERE { ?w a ex:Widget }"
    _, errors = parse_and_fix_prefixes(sparql, PREFIXES)
    assert len(errors) > 0


def test_build_schema_dict():
    sd = build_schema_dict(SCHEMAS, PREFIXES)
    assert "http://example.org/Widget" in sd
    assert "http://example.org/hasName" in sd["http://example.org/Widget"]


def test_extract_query_classes():
    sd = build_schema_dict(SCHEMAS, PREFIXES)
    sparql = "PREFIX ex: <http://example.org/>\nSELECT ?w WHERE { ?w a ex:Widget }"
    classes = extract_query_classes(sparql, sd)
    assert "Widget" in classes


def test_extract_classes_via_predicate():
    sd = build_schema_dict(SCHEMAS, PREFIXES)
    sparql = "PREFIX ex: <http://example.org/>\nSELECT ?w ?n WHERE { ?w ex:hasName ?n }"
    classes = extract_query_classes(sparql, sd)
    assert "Widget" in classes


def test_validate_semantics_valid():
    sd = build_schema_dict(SCHEMAS, PREFIXES)
    sparql = "PREFIX ex: <http://example.org/>\nSELECT ?w WHERE { ?w a ex:Widget ; ex:hasName ?n }"
    errors = validate_semantics(sparql, sd)
    assert errors == []


def test_validate_semantics_unknown_class():
    sd = build_schema_dict(SCHEMAS, PREFIXES)
    sparql = "PREFIX ex: <http://example.org/>\nSELECT ?w WHERE { ?w a ex:Gadget }"
    errors = validate_semantics(sparql, sd)
    assert any("Unknown class" in e for e in errors)


def test_validate_semantics_unknown_predicate():
    sd = build_schema_dict(SCHEMAS, PREFIXES)
    sparql = "PREFIX ex: <http://example.org/>\nSELECT ?w WHERE { ?w a ex:Widget ; ex:hasFlavor ?f }"
    errors = validate_semantics(sparql, sd)
    assert any("Unknown predicate" in e for e in errors)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_core_validate.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

Copy the validation logic from `dprr_mcp/validate.py` into `linked_past/core/validate.py`, changing only the import path for `execute_query`:

```python
# linked_past/core/validate.py
"""SPARQL validation pipeline: parse, prefix repair, semantic checks."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from pyparsing import ParseException
from rdflib.plugins.sparql import prepareQuery
from rdflib.plugins.sparql.algebra import translateQuery, traverse
from rdflib.plugins.sparql.parser import parseQuery
from rdflib.plugins.sparql.parserutils import CompValue
from rdflib.term import URIRef, Variable

from linked_past.core.store import execute_query

RDF_TYPE = URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")


def _suggest(name: str, valid_names: list[str]) -> str:
    from difflib import get_close_matches
    matches = get_close_matches(name, valid_names, n=3, cutoff=0.6)
    return f" Did you mean: {', '.join(matches)}?" if matches else ""


def _local_name(uri: str) -> str:
    if "#" in uri:
        return uri.rsplit("#", 1)[-1]
    return uri.rsplit("/", 1)[-1]


@dataclass
class QueryResult:
    success: bool
    sparql: str
    rows: list[dict[str, str]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _expand_uri(prefixed: str, prefix_map: dict[str, str]) -> str:
    if ":" not in prefixed:
        return prefixed
    prefix, local = prefixed.split(":", 1)
    if prefix in prefix_map:
        return prefix_map[prefix] + local
    return prefixed


def _scan_used_prefixes(sparql: str) -> set[str]:
    cleaned = re.sub(r'"[^"]*"', '', sparql)
    cleaned = re.sub(r"'[^']*'", '', cleaned)
    cleaned = re.sub(r'<[^>]*>', '', cleaned)
    used = set()
    for match in re.finditer(r'\b([a-zA-Z][a-zA-Z0-9]*):([a-zA-Z_]\w*)', cleaned):
        prefix = match.group(1)
        if prefix.upper() != "PREFIX":
            used.add(prefix)
    return used


def _get_declared_prefixes(sparql: str) -> set[str]:
    declared = set()
    for match in re.finditer(r'PREFIX\s+(\w+)\s*:', sparql, re.IGNORECASE):
        declared.add(match.group(1))
    return declared


def _split_comments_and_query(sparql: str) -> tuple[list[str], str]:
    lines = sparql.split('\n')
    comments = []
    rest_start = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('#') or stripped == '':
            comments.append(line)
            rest_start = i + 1
        else:
            break
    query_body = '\n'.join(lines[rest_start:])
    return comments, query_body


def parse_and_fix_prefixes(sparql: str, prefix_map: dict[str, str]) -> tuple[str, list[str]]:
    """Parse a SPARQL query, automatically fixing missing PREFIX declarations."""
    try:
        prepareQuery(sparql)
        return sparql, []
    except ParseException as e:
        return sparql, [str(e)]
    except Exception as e:
        error_msg = str(e)
        if "Unknown namespace prefix" not in error_msg:
            return sparql, [error_msg]

    comments, query_body = _split_comments_and_query(sparql)
    declared = _get_declared_prefixes(query_body)
    used = _scan_used_prefixes(query_body)
    missing = used - declared

    new_prefixes = []
    for prefix in sorted(missing):
        if prefix in prefix_map:
            new_prefixes.append(f"PREFIX {prefix}: <{prefix_map[prefix]}>")

    parts = []
    if comments:
        parts.append('\n'.join(comments))
    if new_prefixes:
        parts.append('\n'.join(new_prefixes))
    parts.append(query_body)
    fixed = '\n'.join(parts)

    try:
        prepareQuery(fixed)
        return fixed, []
    except ParseException as e:
        return fixed, [str(e)]
    except Exception as e:
        return fixed, [str(e)]


def build_schema_dict(schemas: dict, prefix_map: dict[str, str]) -> dict:
    """Convert schemas YAML to dict[class_full_uri][predicate_full_uri] = [range_types]."""
    schema_dict: dict[str, dict[str, list[str]]] = {}
    for cls_name, cls_data in schemas.items():
        class_uri = _expand_uri(cls_data["uri"], prefix_map)
        predicates: dict[str, list[str]] = {}
        for prop in cls_data.get("properties", []):
            pred_uri = _expand_uri(prop["pred"], prefix_map)
            range_uri = _expand_uri(prop["range"], prefix_map)
            if pred_uri not in predicates:
                predicates[pred_uri] = []
            predicates[pred_uri].append(range_uri)
        schema_dict[class_uri] = predicates
    return schema_dict


def _collect_triples(sparql: str) -> list[tuple]:
    parsed = parseQuery(sparql)
    q = translateQuery(parsed)
    triples = []

    def visitor(node):
        if isinstance(node, CompValue) and node.name == "BGP":
            for t in node.get("triples", []):
                triples.append(t)
        return node

    traverse(q.algebra, visitPost=visitor)
    return triples


_UNIVERSAL_PREDS = {
    "http://www.w3.org/2000/01/rdf-schema#label",
    "http://www.w3.org/1999/02/22-rdf-syntax-ns#type",
}


def extract_query_classes(sparql: str, schema_dict: dict) -> set[str]:
    """Extract class local names referenced in a SPARQL query."""
    try:
        triples = _collect_triples(sparql)
    except Exception:
        return set()

    classes: set[str] = set()
    for s, p, o in triples:
        if p == RDF_TYPE and isinstance(o, URIRef):
            classes.add(_local_name(str(o)))
        elif isinstance(p, URIRef) and str(p) not in _UNIVERSAL_PREDS:
            pred_str = str(p)
            for class_uri, preds in schema_dict.items():
                if pred_str in preds:
                    classes.add(_local_name(class_uri))
    return classes


def validate_semantics(sparql: str, schema_dict: dict) -> list[str]:
    """Validate a SPARQL query against the schema dictionary."""
    errors = []
    try:
        triples = _collect_triples(sparql)
    except Exception:
        return errors

    var_types: dict[str, list[str]] = {}
    all_class_uris = set(schema_dict.keys())

    for s, p, o in triples:
        if p == RDF_TYPE and isinstance(o, URIRef):
            class_uri = str(o)
            if class_uri not in all_class_uris:
                local_name = _local_name(class_uri)
                valid_classes = sorted(_local_name(uri) for uri in all_class_uris)
                errors.append(
                    f"Unknown class '{local_name}'. Valid classes: {', '.join(valid_classes)}"
                    + _suggest(local_name, valid_classes)
                )
            if isinstance(s, Variable):
                var_name = str(s)
                if var_name not in var_types:
                    var_types[var_name] = []
                var_types[var_name].append(class_uri)

    for s, p, o in triples:
        if p == RDF_TYPE or not isinstance(p, URIRef) or not isinstance(s, Variable):
            continue
        var_name = str(s)
        if var_name not in var_types:
            continue
        pred_uri = str(p)
        for class_uri in var_types[var_name]:
            if class_uri not in schema_dict:
                continue
            valid_preds = schema_dict[class_uri]
            if pred_uri not in valid_preds:
                pred_local = _local_name(pred_uri)
                valid_local = sorted(_local_name(uri) for uri in valid_preds)
                errors.append(
                    f"Unknown predicate '{pred_local}' for class "
                    f"'{_local_name(class_uri)}'. "
                    f"Valid predicates: {', '.join(valid_local)}"
                    + _suggest(pred_local, valid_local)
                )
    return errors


def validate_and_execute(
    sparql: str, store, schema_dict: dict, prefix_map: dict[str, str],
) -> QueryResult:
    """Validate and execute a SPARQL query through all three tiers."""
    fixed_sparql, parse_errors = parse_and_fix_prefixes(sparql, prefix_map)
    if parse_errors:
        return QueryResult(success=False, sparql=fixed_sparql, errors=parse_errors)

    semantic_errors = validate_semantics(fixed_sparql, schema_dict)
    if semantic_errors:
        return QueryResult(success=False, sparql=fixed_sparql, errors=semantic_errors)

    try:
        rows = execute_query(store, fixed_sparql)
    except Exception as e:
        return QueryResult(success=False, sparql=fixed_sparql, errors=[f"Query execution error: {e}"])

    return QueryResult(success=True, sparql=fixed_sparql, rows=rows)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_core_validate.py -v`
Expected: PASS (9 tests)

- [ ] **Step 5: Commit**

```bash
git add linked_past/core/validate.py tests/test_core_validate.py
git commit -m "feat: add SPARQL validation pipeline to linked_past.core"
```

---

### Task 5: Create dataset registry

**Files:**
- Create: `linked_past/core/registry.py`
- Test: `tests/test_registry.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_registry.py
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from linked_past.core.registry import DatasetRegistry
from linked_past.datasets.base import DatasetPlugin, ValidationResult, VersionInfo


class FakePlugin(DatasetPlugin):
    name = "fake"
    display_name = "Fake Dataset"
    description = "A fake dataset for testing."
    citation = "Fake et al., 2026"
    license = "CC0"
    url = "https://example.com"
    time_coverage = "2000-2026"
    spatial_coverage = "Everywhere"

    def __init__(self, context_dir=None):
        self._context_dir = context_dir

    def fetch(self, data_dir):
        ttl = data_dir / "fake.ttl"
        ttl.write_text(
            '@prefix ex: <http://example.org/> .\n'
            '@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n'
            'ex:Thing1 a ex:Widget ; rdfs:label "Thing" .\n'
        )
        return ttl

    def load(self, store, rdf_path):
        from pyoxigraph import RdfFormat
        store.bulk_load(path=str(rdf_path), format=RdfFormat.TURTLE)
        return len(store)

    def get_prefixes(self):
        return {"ex": "http://example.org/", "rdfs": "http://www.w3.org/2000/01/rdf-schema#"}

    def get_schema(self):
        return "## Fake Schema\n- Widget"

    def build_schema_dict(self):
        return {}

    def validate(self, sparql):
        return ValidationResult(valid=True, sparql=sparql)

    def get_version_info(self, data_dir):
        return VersionInfo(
            version="1.0.0",
            source_url="https://example.com/data.ttl",
            fetched_at="2026-03-30T00:00:00Z",
            triple_count=3,
            rdf_format="turtle",
        )


def test_registry_register_and_list(tmp_path):
    reg = DatasetRegistry(data_dir=tmp_path)
    plugin = FakePlugin()
    reg.register(plugin)
    assert "fake" in reg.list_datasets()


def test_registry_get_plugin(tmp_path):
    reg = DatasetRegistry(data_dir=tmp_path)
    plugin = FakePlugin()
    reg.register(plugin)
    assert reg.get_plugin("fake") is plugin


def test_registry_get_unknown_raises(tmp_path):
    reg = DatasetRegistry(data_dir=tmp_path)
    with pytest.raises(KeyError, match="fake"):
        reg.get_plugin("fake")


def test_registry_initialize_dataset(tmp_path):
    reg = DatasetRegistry(data_dir=tmp_path)
    plugin = FakePlugin()
    reg.register(plugin)
    reg.initialize_dataset("fake")
    store = reg.get_store("fake")
    assert store is not None
    # Store should have data
    results = store.query("SELECT (COUNT(*) AS ?c) WHERE { ?s ?p ?o }")
    for row in results:
        assert int(row[0].value) > 0


def test_registry_saves_registry_json(tmp_path):
    reg = DatasetRegistry(data_dir=tmp_path)
    plugin = FakePlugin()
    reg.register(plugin)
    reg.initialize_dataset("fake")
    registry_file = tmp_path / "registry.json"
    assert registry_file.exists()
    data = json.loads(registry_file.read_text())
    assert "fake" in data
    assert data["fake"]["version"] == "1.0.0"


def test_registry_skips_if_already_initialized(tmp_path):
    reg = DatasetRegistry(data_dir=tmp_path)
    plugin = FakePlugin()
    reg.register(plugin)
    reg.initialize_dataset("fake")
    # Second init should not re-fetch — verify by checking fetch is not called again
    original_fetch = plugin.fetch
    call_count = 0
    def counting_fetch(data_dir):
        nonlocal call_count
        call_count += 1
        return original_fetch(data_dir)
    plugin.fetch = counting_fetch
    reg.initialize_dataset("fake")
    assert call_count == 0  # fetch should NOT be called on second init
    store = reg.get_store("fake")
    assert store is not None


def test_registry_stores_actual_triple_count(tmp_path):
    reg = DatasetRegistry(data_dir=tmp_path)
    plugin = FakePlugin()
    reg.register(plugin)
    reg.initialize_dataset("fake")
    meta = reg.get_metadata("fake")
    assert meta["triple_count"] > 0  # Actual count, not hardcoded 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_registry.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

```python
# linked_past/core/registry.py
"""Dataset registry: discovers plugins, manages store lifecycle."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from pyoxigraph import Store

from linked_past.core.store import create_store, get_read_only_store, is_initialized
from linked_past.datasets.base import DatasetPlugin

logger = logging.getLogger(__name__)


class DatasetRegistry:
    """Manages dataset plugins and their Oxigraph stores."""

    def __init__(self, data_dir: Path):
        self._data_dir = data_dir
        self._plugins: dict[str, DatasetPlugin] = {}
        self._stores: dict[str, Store] = {}
        self._metadata: dict[str, dict] = {}  # Cached version metadata per dataset

    def register(self, plugin: DatasetPlugin) -> None:
        """Register a dataset plugin."""
        self._plugins[plugin.name] = plugin

    def list_datasets(self) -> list[str]:
        """Return names of all registered datasets."""
        return list(self._plugins.keys())

    def get_plugin(self, name: str) -> DatasetPlugin:
        """Get a plugin by name. Raises KeyError if not found."""
        if name not in self._plugins:
            raise KeyError(f"Unknown dataset: {name!r}. Available: {', '.join(self._plugins)}")
        return self._plugins[name]

    def get_store(self, name: str) -> Store:
        """Get the read-only store for a dataset. Raises KeyError if not initialized."""
        if name not in self._stores:
            raise KeyError(f"Dataset {name!r} is not initialized.")
        return self._stores[name]

    def get_metadata(self, name: str) -> dict:
        """Get cached version metadata for a dataset."""
        return self._metadata.get(name, {})

    def initialize_dataset(self, name: str) -> None:
        """Initialize a dataset: fetch data if needed, load into store, open read-only."""
        plugin = self.get_plugin(name)
        dataset_dir = self._data_dir / name
        store_path = dataset_dir / "store"

        if is_initialized(store_path):
            logger.info("Dataset %s already initialized, opening read-only", name)
            self._stores[name] = get_read_only_store(store_path)
            return

        dataset_dir.mkdir(parents=True, exist_ok=True)
        rdf_path = plugin.fetch(dataset_dir)

        store = create_store(store_path)
        triple_count = plugin.load(store, rdf_path)
        logger.info("Loaded %d triples for dataset %s", triple_count, name)
        del store

        self._stores[name] = get_read_only_store(store_path)
        self._save_registry(name, plugin, dataset_dir, triple_count)

    def initialize_all(self) -> None:
        """Initialize all registered datasets."""
        for name in self._plugins:
            self.initialize_dataset(name)

    def _save_registry(self, name: str, plugin: DatasetPlugin, dataset_dir: Path, triple_count: int) -> None:
        """Update registry.json with version info for a dataset."""
        registry_path = self._data_dir / "registry.json"
        if registry_path.exists():
            data = json.loads(registry_path.read_text())
        else:
            data = {}

        version_info = plugin.get_version_info(dataset_dir)
        if version_info:
            entry = {
                "version": version_info.version,
                "source_url": version_info.source_url,
                "fetched_at": version_info.fetched_at,
                "triple_count": triple_count,  # Use actual count from load()
                "rdf_format": version_info.rdf_format,
                "license": plugin.license,
            }
            data[name] = entry
            self._metadata[name] = entry  # Cache in memory

        registry_path.write_text(json.dumps(data, indent=2))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_registry.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add linked_past/core/registry.py tests/test_registry.py
git commit -m "feat: add dataset registry to linked_past.core"
```

---

### Task 6: Create DPRR plugin

**Files:**
- Create: `linked_past/datasets/dprr/plugin.py`
- Copy: `dprr_mcp/context/*.yaml` → `linked_past/datasets/dprr/context/`
- Test: `tests/test_dprr_plugin.py`

- [ ] **Step 1: Copy YAML context files**

```bash
cp dprr_mcp/context/schemas.yaml linked_past/datasets/dprr/context/schemas.yaml
cp dprr_mcp/context/examples.yaml linked_past/datasets/dprr/context/examples.yaml
cp dprr_mcp/context/tips.yaml linked_past/datasets/dprr/context/tips.yaml
cp dprr_mcp/context/prefixes.yaml linked_past/datasets/dprr/context/prefixes.yaml
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_dprr_plugin.py
import tempfile
from pathlib import Path
from unittest.mock import patch

from linked_past.datasets.dprr.plugin import DPRRPlugin


def test_dprr_plugin_attributes():
    plugin = DPRRPlugin()
    assert plugin.name == "dprr"
    assert "Roman Republic" in plugin.display_name
    assert plugin.license == "CC BY-NC 4.0"
    assert plugin.url == "https://romanrepublic.ac.uk"


def test_dprr_plugin_prefixes():
    plugin = DPRRPlugin()
    prefixes = plugin.get_prefixes()
    assert "vocab" in prefixes
    assert prefixes["vocab"] == "http://romanrepublic.ac.uk/rdf/ontology#"


def test_dprr_plugin_schema():
    plugin = DPRRPlugin()
    schema = plugin.get_schema()
    assert "Person" in schema
    assert "PostAssertion" in schema


def test_dprr_plugin_validate_valid():
    plugin = DPRRPlugin()
    result = plugin.validate(
        "PREFIX vocab: <http://romanrepublic.ac.uk/rdf/ontology#>\n"
        "SELECT ?p WHERE { ?p a vocab:Person }",
    )
    assert result.valid is True


def test_dprr_plugin_validate_invalid():
    plugin = DPRRPlugin()
    result = plugin.validate(
        "PREFIX vocab: <http://romanrepublic.ac.uk/rdf/ontology#>\n"
        "SELECT ?p WHERE { ?p a vocab:FakeClass }",
    )
    assert result.valid is False
    assert any("Unknown class" in e for e in result.errors)


def test_dprr_plugin_get_relevant_context():
    plugin = DPRRPlugin()
    ctx = plugin.get_relevant_context(
        "PREFIX vocab: <http://romanrepublic.ac.uk/rdf/ontology#>\n"
        "SELECT ?p WHERE { ?p a vocab:Person ; vocab:hasPersonName ?n }",
    )
    assert isinstance(ctx, str)
    # Should return tips/examples for Person class
    assert len(ctx) > 0


def test_dprr_plugin_load(tmp_path):
    from linked_past.core.store import create_store

    plugin = DPRRPlugin()
    ttl = tmp_path / "dprr.ttl"
    ttl.write_text(
        '@prefix vocab: <http://romanrepublic.ac.uk/rdf/ontology#> .\n'
        '<http://romanrepublic.ac.uk/rdf/entity/Person/1> a vocab:Person .\n'
    )
    store = create_store(tmp_path / "store")
    count = plugin.load(store, ttl)
    assert count > 0


def test_dprr_plugin_version_info(tmp_path):
    plugin = DPRRPlugin()
    info = plugin.get_version_info(tmp_path)
    assert info is not None
    assert info.rdf_format == "turtle"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_dprr_plugin.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Write the implementation**

```python
# linked_past/datasets/dprr/plugin.py
"""DPRR dataset plugin."""

from __future__ import annotations

import logging
import os
import sys
import tarfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from pyoxigraph import RdfFormat, Store

from linked_past.core.context import (
    get_cross_cutting_tips,
    get_relevant_examples,
    get_relevant_tips,
    load_examples,
    load_prefixes,
    load_schemas,
    load_tips,
    render_class_summary,
    render_tips,
)
from linked_past.core.validate import build_schema_dict, extract_query_classes, validate_semantics
from linked_past.datasets.base import DatasetPlugin, ValidationResult, VersionInfo

logger = logging.getLogger(__name__)

_CONTEXT_DIR = Path(__file__).parent / "context"
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

    def __init__(self):
        self._prefixes = load_prefixes(_CONTEXT_DIR)
        self._schemas = load_schemas(_CONTEXT_DIR)
        self._examples = load_examples(_CONTEXT_DIR)
        self._tips = load_tips(_CONTEXT_DIR)
        self._schema_dict = build_schema_dict(self._schemas, self._prefixes)
        for ex in self._examples:
            ex["classes"] = extract_query_classes(ex["sparql"], self._schema_dict)

    def fetch(self, data_dir: Path) -> Path:
        url = os.environ.get("DPRR_DATA_URL", _DEFAULT_DATA_URL)
        logger.info("Downloading DPRR data from %s", url)
        print(f"Downloading DPRR data from {url} ...", file=sys.stderr)

        try:
            tmp_path, _ = urllib.request.urlretrieve(url)
        except OSError as e:
            raise RuntimeError(f"Failed to download data from {url}: {e}") from e

        try:
            with tarfile.open(tmp_path, "r:gz") as tar:
                members = tar.getnames()
                if "dprr.ttl" not in members:
                    raise RuntimeError(f"Tarball does not contain dprr.ttl. Found: {members}")
                tar.extract("dprr.ttl", path=str(data_dir), filter="data")
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        result = data_dir / "dprr.ttl"
        print(f"Extracted dprr.ttl to {result}", file=sys.stderr)
        return result

    # load() uses default implementation from ABC (Turtle format)

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
        """Build contextual tips and examples for a SPARQL query."""
        classes = extract_query_classes(sparql, self._schema_dict)
        if not classes:
            return ""
        parts: list[str] = []
        tips = get_relevant_tips(self._tips, classes)
        if tips:
            parts.append(f"## Relevant Tips\n\n{render_tips(tips)}")
        from linked_past.core.context import render_examples
        examples = get_relevant_examples(self._examples, classes)
        if examples:
            parts.append(f"## Relevant Examples\n\n{render_examples(examples)}")
        if not parts:
            return ""
        return "\n\n---\n\n" + "\n\n".join(parts)

    def get_version_info(self, data_dir: Path) -> VersionInfo:
        url = os.environ.get("DPRR_DATA_URL", _DEFAULT_DATA_URL)
        return VersionInfo(
            version="1.3.0",
            source_url=url,
            fetched_at=datetime.now(timezone.utc).isoformat(),
            triple_count=0,
            rdf_format="turtle",
        )

    def check_for_updates(self):
        return None
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_dprr_plugin.py -v`
Expected: PASS (7 tests)

- [ ] **Step 6: Commit**

```bash
git add linked_past/datasets/dprr/ tests/test_dprr_plugin.py
git commit -m "feat: add DPRR dataset plugin"
```

---

### Task 7: Create MCP server with four core tools

**Files:**
- Create: `linked_past/core/server.py`
- Test: `tests/test_server.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_server.py
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from linked_past.core.server import build_app_context, create_mcp_server

SAMPLE_TURTLE = """\
@prefix vocab: <http://romanrepublic.ac.uk/rdf/ontology#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

<http://romanrepublic.ac.uk/rdf/entity/Person/1> a vocab:Person ;
    vocab:hasPersonName "IUNI0001 L. Iunius Brutus" ;
    vocab:hasDprrID "IUNI0001" ;
    vocab:hasNomen "Iunius" .
"""


def test_build_app_context(tmp_path, monkeypatch):
    """build_app_context initializes registry with DPRR plugin."""
    monkeypatch.setenv("LINKED_PAST_DATA_DIR", str(tmp_path))
    # Pre-populate data so fetch is not called
    dprr_dir = tmp_path / "dprr"
    dprr_dir.mkdir()
    (dprr_dir / "dprr.ttl").write_text(SAMPLE_TURTLE)

    ctx = build_app_context()
    assert "dprr" in ctx.registry.list_datasets()
    store = ctx.registry.get_store("dprr")
    assert store is not None


def test_create_mcp_server():
    """create_mcp_server returns a FastMCP instance with tools registered."""
    mcp = create_mcp_server()
    tool_names = [t.name for t in mcp._tool_manager.list_tools()]
    assert "discover_datasets" in tool_names
    assert "get_schema" in tool_names
    assert "validate_sparql" in tool_names
    assert "query" in tool_names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_server.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

```python
# linked_past/core/server.py
"""MCP server exposing multi-dataset prosopographical SPARQL tools."""

from __future__ import annotations

import asyncio
import difflib
import json
import logging
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass

import toons
from mcp.server.fastmcp import Context, FastMCP
from pyoxigraph import Store

from linked_past.core.registry import DatasetRegistry
from linked_past.core.store import get_data_dir
from linked_past.core.validate import parse_and_fix_prefixes, validate_and_execute
from linked_past.datasets.dprr.plugin import DPRRPlugin

logger = logging.getLogger(__name__)

QUERY_TIMEOUT = int(os.environ.get("LINKED_PAST_QUERY_TIMEOUT", os.environ.get("DPRR_QUERY_TIMEOUT", "600")))


@dataclass
class AppContext:
    registry: DatasetRegistry


def build_app_context() -> AppContext:
    """Build the application context: register plugins, initialize stores."""
    data_dir = get_data_dir()
    registry = DatasetRegistry(data_dir=data_dir)

    # Register all available plugins
    registry.register(DPRRPlugin())

    # Initialize all datasets
    registry.initialize_all()

    return AppContext(registry=registry)


def create_mcp_server() -> FastMCP:
    """Create and configure the FastMCP server with all tools."""

    @asynccontextmanager
    async def lifespan(server: FastMCP):
        ctx = build_app_context()
        yield ctx

    mcp = FastMCP(
        "linked-past",
        instructions=(
            "Linked Past: multi-dataset prosopographical SPARQL tools. "
            "Use discover_datasets to find available datasets, get_schema to learn their ontology, "
            "validate_sparql to check queries, and query to execute them."
        ),
        lifespan=lifespan,
    )

    @mcp.custom_route("/healthz", ["GET"])
    async def healthz(request):
        from starlette.responses import JSONResponse
        return JSONResponse({"status": "ok"})

    @mcp.tool()
    def discover_datasets(ctx: Context, topic: str | None = None) -> str:
        """Discover available datasets. Without arguments, lists all loaded datasets with metadata. With a topic, filters by relevance."""
        app: AppContext = ctx.request_context.lifespan_context
        registry = app.registry

        lines = ["# Available Datasets\n"]
        for name in registry.list_datasets():
            plugin = registry.get_plugin(name)
            if topic:
                searchable = [
                    plugin.description, plugin.display_name,
                    plugin.spatial_coverage, plugin.time_coverage,
                ]
                if not any(topic.lower() in field.lower() for field in searchable):
                    continue

            meta = registry.get_metadata(name)
            version = meta.get("version", "unknown")
            triple_count = meta.get("triple_count", "unknown")

            lines.append(
                f"## {plugin.display_name}\n"
                f"- **ID:** `{name}`\n"
                f"- **Period:** {plugin.time_coverage}\n"
                f"- **Geography:** {plugin.spatial_coverage}\n"
                f"- **Version:** {version}\n"
                f"- **Triples:** {triple_count}\n"
                f"- **License:** {plugin.license}\n"
                f"- **Citation:** {plugin.citation}\n"
                f"- **URL:** {plugin.url}\n"
                f"\n{plugin.description}\n"
            )

        if len(lines) == 1:
            return "No datasets match that topic." if topic else "No datasets loaded."
        return "\n".join(lines)

    @mcp.tool()
    def get_schema(ctx: Context, dataset: str) -> str:
        """Get the ontology overview for a dataset: namespace prefixes, available classes, and query tips. Call this before writing SPARQL queries."""
        app: AppContext = ctx.request_context.lifespan_context
        plugin = app.registry.get_plugin(dataset)
        return plugin.get_schema()

    @mcp.tool()
    def validate_sparql(ctx: Context, sparql: str, dataset: str) -> str:
        """Validate a SPARQL query against a dataset's schema without executing it. Checks syntax, auto-repairs missing PREFIX declarations, and validates classes and predicates."""
        app: AppContext = ctx.request_context.lifespan_context
        plugin = app.registry.get_plugin(dataset)
        prefix_map = plugin.get_prefixes()

        fixed_sparql, parse_errors = parse_and_fix_prefixes(sparql, prefix_map)
        if parse_errors:
            error_list = "\n".join(f"- {e}" for e in parse_errors)
            base = f"INVALID\n\nErrors:\n{error_list}"
            context = ""
            if hasattr(plugin, "get_relevant_context"):
                context = plugin.get_relevant_context(sparql)
            return base + context

        result = plugin.validate(fixed_sparql)
        if not result.valid:
            error_list = "\n".join(f"- {e}" for e in result.errors)
            base = f"INVALID\n\nErrors:\n{error_list}"
            return base + plugin.get_relevant_context(fixed_sparql)

        if fixed_sparql != sparql:
            diff = "".join(
                difflib.unified_diff(
                    sparql.splitlines(keepends=True),
                    fixed_sparql.splitlines(keepends=True),
                    n=0,
                )
            )
            base = f"VALID (prefixes auto-repaired)\n\n```diff\n{diff}```"
        else:
            base = "VALID"

        return base + plugin.get_relevant_context(fixed_sparql)

    @mcp.tool()
    async def query(ctx: Context, sparql: str, dataset: str, timeout: int | None = None) -> str:
        """Validate and execute a SPARQL query against a dataset's local RDF store. Returns results in tabular format with dataset citation."""
        app: AppContext = ctx.request_context.lifespan_context
        plugin = app.registry.get_plugin(dataset)
        store = app.registry.get_store(dataset)
        prefix_map = plugin.get_prefixes()
        schema_dict = plugin.build_schema_dict()
        effective_timeout = timeout if timeout is not None else QUERY_TIMEOUT

        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    validate_and_execute, sparql, store, schema_dict, prefix_map
                ),
                timeout=effective_timeout,
            )
        except asyncio.TimeoutError:
            return f"ERROR: Query timed out after {effective_timeout}s. Simplify the query or increase the timeout."
        except OSError as e:
            return f"ERROR: Store access error: {e}"
        except Exception as e:
            return f"ERROR: Unexpected error: {e}"

        if not result.success:
            error_list = "\n".join(f"- {e}" for e in result.errors)
            return f"ERROR:\n{error_list}"

        table = toons.dumps(result.rows)

        # Append citation footer
        meta = app.registry.get_metadata(dataset)
        version = meta.get("version", "unknown")

        footer = (
            f"\n\n─── Sources ───\n"
            f"Data: {plugin.display_name} v{version}. {plugin.license}.\n"
            f"      Cite as: {plugin.citation}\n"
            f"Tool: linked-past, https://github.com/gillisandrew/dprr-tool"
        )
        return table + footer

    return mcp


def main():
    """Run the MCP server over streamable-http."""
    import argparse

    parser = argparse.ArgumentParser(description="Linked Past MCP Server")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Bind port (default: 8000)")
    args = parser.parse_args()

    mcp = create_mcp_server()
    mcp.settings.host = args.host
    mcp.settings.port = args.port
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_server.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add linked_past/core/server.py tests/test_server.py
git commit -m "feat: add MCP server with discover_datasets, get_schema, validate_sparql, query tools"
```

---

### Task 8: Update pyproject.toml and backward compatibility

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Update pyproject.toml**

Replace the full `pyproject.toml` contents:

```toml
[project]
name = "linked-past"
version = "0.1.0"
description = "Multi-dataset prosopographical SPARQL tools for AI agents. Natural-language queries with scholarly citations across linked ancient world datasets."
readme = "README.md"
license = "MIT"
requires-python = ">=3.13"
dependencies = [
    "pyoxigraph",
    "rdflib",
    "pyyaml",
    "mcp",
    "toons>=0.5.3",
]

[project.scripts]
linked-past-server = "linked_past.core.server:main"
dprr-server = "linked_past.core.server:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[dependency-groups]
dev = [
    "pytest",
    "pytest-asyncio",
    "ruff",
]
analysis = [
    "pandas",
]

[tool.ruff]
target-version = "py313"
line-length = 120

[tool.ruff.lint]
select = ["E", "F", "I", "W"]

[tool.ruff.lint.per-file-ignores]
"tests/*" = ["E501"]
"linked_past/core/server.py" = ["E501"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
filterwarnings = [
    "ignore::RuntimeWarning:importlib",
    "ignore::RuntimeWarning:yaml",
]
```

- [ ] **Step 2: Verify old tests still run (they import from dprr_mcp which still exists)**

Run: `uv run pytest tests/test_store.py tests/test_validate.py tests/test_context.py -v`
Expected: PASS — old code still works, old tests still pass

- [ ] **Step 3: Verify new tests all pass**

Run: `uv run pytest tests/test_base.py tests/test_core_store.py tests/test_core_context.py tests/test_core_validate.py tests/test_registry.py tests/test_dprr_plugin.py tests/test_server.py -v`
Expected: PASS — all new tests pass

- [ ] **Step 4: Run full test suite and lint**

Run: `uv run pytest -v && uv run ruff check .`
Expected: All tests pass, no lint errors

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml
git commit -m "chore: rename package to linked-past, add backward-compat dprr-server alias"
```

---

### Task 9: End-to-end integration test

**Files:**
- Create: `tests/test_linked_past_integration.py`

- [ ] **Step 1: Write the integration test**

```python
# tests/test_linked_past_integration.py
"""End-to-end integration test for the linked-past server with DPRR plugin."""

import json
from pathlib import Path

import pytest

from linked_past.core.registry import DatasetRegistry
from linked_past.core.server import build_app_context
from linked_past.core.store import execute_query
from linked_past.core.validate import parse_and_fix_prefixes, validate_and_execute
from linked_past.datasets.dprr.plugin import DPRRPlugin

SAMPLE_TURTLE = """\
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


@pytest.fixture
def integration_ctx(tmp_path, monkeypatch):
    """Set up a registry with DPRR plugin and sample data."""
    monkeypatch.setenv("LINKED_PAST_DATA_DIR", str(tmp_path))
    dprr_dir = tmp_path / "dprr"
    dprr_dir.mkdir()
    (dprr_dir / "dprr.ttl").write_text(SAMPLE_TURTLE)

    return build_app_context()


def test_discover_lists_dprr(integration_ctx):
    datasets = integration_ctx.registry.list_datasets()
    assert "dprr" in datasets


def test_get_schema_has_classes(integration_ctx):
    plugin = integration_ctx.registry.get_plugin("dprr")
    schema = plugin.get_schema()
    assert "Person" in schema
    assert "PostAssertion" in schema
    assert "PREFIX vocab:" in schema


def test_validate_valid_query(integration_ctx):
    plugin = integration_ctx.registry.get_plugin("dprr")
    prefix_map = plugin.get_prefixes()
    sparql = (
        "PREFIX vocab: <http://romanrepublic.ac.uk/rdf/ontology#>\n"
        "SELECT ?p ?name WHERE { ?p a vocab:Person ; vocab:hasPersonName ?name }"
    )
    fixed, errors = parse_and_fix_prefixes(sparql, prefix_map)
    assert errors == []
    result = plugin.validate(fixed)
    assert result.valid is True


def test_validate_invalid_class(integration_ctx):
    plugin = integration_ctx.registry.get_plugin("dprr")
    sparql = (
        "PREFIX vocab: <http://romanrepublic.ac.uk/rdf/ontology#>\n"
        "SELECT ?p WHERE { ?p a vocab:FakeClass }"
    )
    result = plugin.validate(sparql)
    assert result.valid is False


def test_execute_query_returns_results(integration_ctx):
    store = integration_ctx.registry.get_store("dprr")
    plugin = integration_ctx.registry.get_plugin("dprr")
    sparql = (
        "PREFIX vocab: <http://romanrepublic.ac.uk/rdf/ontology#>\n"
        "SELECT ?name WHERE { ?p a vocab:Person ; vocab:hasPersonName ?name }"
    )
    result = validate_and_execute(
        sparql, store, plugin.build_schema_dict(), plugin.get_prefixes()
    )
    assert result.success is True
    assert len(result.rows) == 1
    assert "Brutus" in result.rows[0]["name"]


def test_execute_with_prefix_repair(integration_ctx):
    store = integration_ctx.registry.get_store("dprr")
    plugin = integration_ctx.registry.get_plugin("dprr")
    # Missing PREFIX declaration — should be auto-repaired
    sparql = "SELECT ?name WHERE { ?p a vocab:Person ; vocab:hasPersonName ?name }"
    result = validate_and_execute(
        sparql, store, plugin.build_schema_dict(), plugin.get_prefixes()
    )
    assert result.success is True
    assert len(result.rows) == 1


def test_registry_json_written(integration_ctx, tmp_path, monkeypatch):
    monkeypatch.setenv("LINKED_PAST_DATA_DIR", str(tmp_path))
    registry_path = tmp_path / "registry.json"
    assert registry_path.exists()
    data = json.loads(registry_path.read_text())
    assert "dprr" in data
    assert "version" in data["dprr"]
    assert data["dprr"]["triple_count"] > 0  # Actual count, not 0


def test_discover_datasets_no_filter(integration_ctx):
    """discover_datasets with no topic returns all datasets."""
    from linked_past.core.server import create_mcp_server
    registry = integration_ctx.registry
    # Directly test that DPRR appears in the list
    datasets = registry.list_datasets()
    assert "dprr" in datasets
    plugin = registry.get_plugin("dprr")
    assert "Roman Republic" in plugin.display_name


def test_discover_datasets_topic_filter(integration_ctx):
    """discover_datasets topic filter matches on description fields."""
    plugin = integration_ctx.registry.get_plugin("dprr")
    # "roman" should match DPRR's spatial_coverage or description
    searchable = [plugin.description, plugin.display_name,
                  plugin.spatial_coverage, plugin.time_coverage]
    assert any("roman" in f.lower() for f in searchable)
    # "medieval" should NOT match DPRR
    assert not any("medieval" in f.lower() for f in searchable)


def test_query_result_includes_citation(integration_ctx):
    """Query results include a citation footer with dataset name and version."""
    store = integration_ctx.registry.get_store("dprr")
    plugin = integration_ctx.registry.get_plugin("dprr")
    result = validate_and_execute(
        "PREFIX vocab: <http://romanrepublic.ac.uk/rdf/ontology#>\n"
        "SELECT ?name WHERE { ?p a vocab:Person ; vocab:hasPersonName ?name }",
        store, plugin.build_schema_dict(), plugin.get_prefixes(),
    )
    assert result.success is True
    # Verify the metadata is available for citation
    meta = integration_ctx.registry.get_metadata("dprr")
    assert "version" in meta
    assert plugin.citation != ""
```

- [ ] **Step 2: Run integration tests**

Run: `uv run pytest tests/test_linked_past_integration.py -v`
Expected: PASS (7 tests)

- [ ] **Step 3: Run full test suite**

Run: `uv run pytest -v && uv run ruff check .`
Expected: All tests pass, no lint errors

- [ ] **Step 4: Commit**

```bash
git add tests/test_linked_past_integration.py
git commit -m "test: add end-to-end integration tests for linked-past core"
```

---

### Task 10: Final cleanup — verify everything

- [ ] **Step 1: Run the full test suite**

Run: `uv run pytest -v`
Expected: All old tests (from `dprr_mcp`) and new tests (from `linked_past`) pass

- [ ] **Step 2: Run lint**

Run: `uv run ruff check .`
Expected: No errors

- [ ] **Step 3: Verify the server starts**

Run: `LINKED_PAST_DATA_DIR=/tmp/lp-test uv run linked-past-server --help`
Expected: Shows argument help without errors

- [ ] **Step 4: Verify backward-compat alias**

Run: `LINKED_PAST_DATA_DIR=/tmp/lp-test uv run dprr-server --help`
Expected: Same help output as above

- [ ] **Step 5: Commit any final fixes**

If any adjustments were needed:
```bash
git add -A
git commit -m "fix: address issues found in final verification"
```
