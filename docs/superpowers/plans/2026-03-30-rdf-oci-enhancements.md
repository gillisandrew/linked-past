# RDF OCI Distribution Enhancements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add ontology-aware schema generation, multi-document embeddings, VoID generation, and refactored packaging scripts to the linked-past monorepo.

**Architecture:** Four independent modules — `ontology.py` and `void.py` in `linked-past-store`, a `_build_embeddings` enhancement in `linked-past` server, and refactored `scripts/package_*.py` that use `linked-past-store` APIs instead of inline logic. Each task is independently testable and committable.

**Tech Stack:** Python 3.13, pyoxigraph (RDF store), PyYAML (schema output), uv workspace monorepo, pytest.

---

## File Structure

| File | Responsibility |
|---|---|
| `packages/linked-past-store/linked_past_store/ontology.py` | Parse OWL/RDFS ontologies or extract schemas empirically from data via SPARQL |
| `packages/linked-past-store/tests/test_ontology.py` | Tests for ontology extraction |
| `packages/linked-past-store/linked_past_store/void.py` | Generate VoID descriptions from loaded RDF data + metadata |
| `packages/linked-past-store/tests/test_void.py` | Tests for VoID generation |
| `packages/linked-past/linked_past/core/server.py` | Modified `_build_embeddings` for multi-document embedding per class |
| `packages/linked-past/tests/test_embeddings_multi.py` | Tests for multi-document embedding logic |
| `packages/linked-past-store/linked_past_store/push.py` | Extended to support multi-file push + VoID sidecar |
| `packages/linked-past-store/linked_past_store/cli.py` | New `ontology` and `void` subcommands |
| `scripts/package_dprr.py` | Refactored to use `linked-past-store` APIs |
| `scripts/package_pleiades.py` | Refactored to use `linked-past-store` APIs |
| `scripts/package_edh.py` | Refactored to use `linked-past-store` APIs |

---

### Task 1: Ontology-Aware Schema Extraction (`ontology.py`)

**Files:**
- Create: `packages/linked-past-store/linked_last_store/ontology.py`
- Create: `packages/linked-past-store/tests/test_ontology.py`

#### Step 1.1: Write test for OWL class extraction

- [ ] **Write test**

Create `packages/linked-past-store/tests/test_ontology.py`:

```python
"""Tests for ontology extraction."""

import yaml

from linked_past_store.ontology import extract_from_ontology, Schema


# Minimal OWL ontology with 2 classes, hierarchy, properties, comments
SAMPLE_OWL = """\
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix : <http://example.org/onto#> .

:Person a owl:Class ;
    rdfs:label "Person" ;
    rdfs:comment "A historical person." ;
    rdfs:subClassOf :ThingWithName .

:ThingWithName a owl:Class ;
    rdfs:label "Thing With Name" ;
    rdfs:comment "An entity that has a name." .

:hasName a owl:DatatypeProperty ;
    rdfs:domain :ThingWithName ;
    rdfs:range xsd:string ;
    rdfs:comment "The name of the entity." .

:hasAge a owl:DatatypeProperty ;
    rdfs:domain :Person ;
    rdfs:range xsd:integer ;
    rdfs:comment "Age of the person." .

:hasFriend a owl:ObjectProperty ;
    rdfs:domain :Person ;
    rdfs:range :Person ;
    rdfs:comment "A friend relationship." .
"""


def test_extract_classes_from_owl(tmp_path):
    owl_file = tmp_path / "ontology.ttl"
    owl_file.write_text(SAMPLE_OWL)

    schema = extract_from_ontology(owl_file)

    assert isinstance(schema, Schema)
    assert "Person" in schema.classes
    assert "ThingWithName" in schema.classes

    person = schema.classes["Person"]
    assert person.label == "Person"
    assert person.comment == "A historical person."
    assert person.uri == "http://example.org/onto#Person"
    assert person.parent == "http://example.org/onto#ThingWithName"


def test_extract_properties_from_owl(tmp_path):
    owl_file = tmp_path / "ontology.ttl"
    owl_file.write_text(SAMPLE_OWL)

    schema = extract_from_ontology(owl_file)
    person = schema.classes["Person"]

    # Direct property
    preds = {p.predicate for p in person.properties}
    assert "http://example.org/onto#hasAge" in preds
    assert "http://example.org/onto#hasFriend" in preds

    # Find hasAge and check its range/comment
    has_age = next(p for p in person.properties if p.predicate == "http://example.org/onto#hasAge")
    assert has_age.range == "http://www.w3.org/2001/XMLSchema#integer"
    assert has_age.comment == "Age of the person."


def test_inherited_properties(tmp_path):
    owl_file = tmp_path / "ontology.ttl"
    owl_file.write_text(SAMPLE_OWL)

    schema = extract_from_ontology(owl_file)
    person = schema.classes["Person"]

    # hasName is declared on ThingWithName, should be inherited by Person
    preds = {p.predicate for p in person.properties}
    assert "http://example.org/onto#hasName" in preds


def test_hierarchy(tmp_path):
    owl_file = tmp_path / "ontology.ttl"
    owl_file.write_text(SAMPLE_OWL)

    schema = extract_from_ontology(owl_file)
    assert schema.classes["Person"].parent == "http://example.org/onto#ThingWithName"
    assert schema.classes["ThingWithName"].parent is None
```

- [ ] **Run test to verify it fails**

Run: `uv run pytest packages/linked-past-store/tests/test_ontology.py -v`
Expected: FAIL (module not found)

#### Step 1.2: Implement Schema data model and OWL extraction

- [ ] **Write implementation**

Create `packages/linked-past-store/linked_past_store/ontology.py`:

```python
"""Extract schemas from OWL/RDFS ontologies or empirically from RDF data."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from pyoxigraph import RdfFormat, Store

logger = logging.getLogger(__name__)

RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
RDFS_LABEL = "http://www.w3.org/2000/01/rdf-schema#label"
RDFS_COMMENT = "http://www.w3.org/2000/01/rdf-schema#comment"
RDFS_SUBCLASS = "http://www.w3.org/2000/01/rdf-schema#subClassOf"
RDFS_DOMAIN = "http://www.w3.org/2000/01/rdf-schema#domain"
RDFS_RANGE = "http://www.w3.org/2000/01/rdf-schema#range"
OWL_CLASS = "http://www.w3.org/2002/07/owl#Class"
RDFS_CLASS = "http://www.w3.org/2000/01/rdf-schema#Class"
OWL_DATATYPE_PROP = "http://www.w3.org/2002/07/owl#DatatypeProperty"
OWL_OBJECT_PROP = "http://www.w3.org/2002/07/owl#ObjectProperty"
RDF_PROPERTY = "http://www.w3.org/1999/02/22-rdf-syntax-ns#Property"


@dataclass
class PropertyInfo:
    """A property (predicate) with its range and documentation."""

    predicate: str
    range: str | None = None
    comment: str | None = None


@dataclass
class ClassInfo:
    """A class with its properties, hierarchy, and documentation."""

    uri: str
    label: str | None = None
    comment: str | None = None
    parent: str | None = None
    properties: list[PropertyInfo] = field(default_factory=list)


@dataclass
class Schema:
    """Extracted schema: classes with properties, hierarchy, and comments."""

    classes: dict[str, ClassInfo] = field(default_factory=dict)

    def to_schemas_yaml(self, prefix_map: dict[str, str] | None = None) -> str:
        """Generate schemas.yaml content compatible with linked-past plugin context format.

        Args:
            prefix_map: Optional mapping of namespace URI prefixes to short names
                        (e.g., {"http://example.org/onto#": "vocab:"}).
                        When provided, URIs matching a prefix are shortened.
        """
        data: dict = {"classes": {}}
        for name, cls in self.classes.items():
            cls_dict: dict = {}
            if cls.label:
                cls_dict["label"] = cls.label
            if cls.comment:
                cls_dict["comment"] = cls.comment
            cls_dict["uri"] = _shorten(cls.uri, prefix_map)
            if cls.properties:
                props = []
                for p in cls.properties:
                    prop_dict: dict = {"pred": _shorten(p.predicate, prefix_map)}
                    if p.range:
                        prop_dict["range"] = _shorten(p.range, prefix_map)
                    if p.comment:
                        prop_dict["comment"] = p.comment
                    props.append(prop_dict)
                cls_dict["properties"] = props
            data["classes"][name] = cls_dict

        return yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True)


def _shorten(uri: str, prefix_map: dict[str, str] | None) -> str:
    """Shorten a URI using a prefix map, or return as-is."""
    if not prefix_map:
        return uri
    for ns, prefix in prefix_map.items():
        if uri.startswith(ns):
            return prefix + uri[len(ns):]
    return uri


def _str(term) -> str:
    """Extract string value from a pyoxigraph term."""
    return str(term).strip("<>")


def extract_from_ontology(ontology_path: Path) -> Schema:
    """Parse OWL/RDFS ontology file. Returns complete schema with hierarchy."""
    store = Store()
    fmt = RdfFormat.TURTLE
    first_bytes = ontology_path.read_bytes()[:200]
    if first_bytes.lstrip().startswith(b"<?xml") or first_bytes.lstrip().startswith(b"<rdf:"):
        fmt = RdfFormat.RDF_XML
    store.bulk_load(path=str(ontology_path), format=fmt)

    schema = Schema()

    # 1. Find all classes (owl:Class or rdfs:Class)
    class_uris: set[str] = set()
    for quad in store.quads_for_pattern(None, store.parse_named_node(RDF_TYPE), store.parse_named_node(OWL_CLASS), None):
        class_uris.add(_str(quad.subject))
    for quad in store.quads_for_pattern(None, store.parse_named_node(RDF_TYPE), store.parse_named_node(RDFS_CLASS), None):
        class_uris.add(_str(quad.subject))

    # 2. Extract labels, comments, hierarchy for each class
    for uri in class_uris:
        node = store.parse_named_node(uri)
        label = None
        comment = None
        parent = None

        for quad in store.quads_for_pattern(node, store.parse_named_node(RDFS_LABEL), None, None):
            label = quad.object.value
        for quad in store.quads_for_pattern(node, store.parse_named_node(RDFS_COMMENT), None, None):
            comment = quad.object.value
        for quad in store.quads_for_pattern(node, store.parse_named_node(RDFS_SUBCLASS), None, None):
            parent_str = _str(quad.object)
            if parent_str in class_uris:
                parent = parent_str

        # Use local name as dict key
        local_name = uri.rsplit("#", 1)[-1] if "#" in uri else uri.rsplit("/", 1)[-1]
        schema.classes[local_name] = ClassInfo(
            uri=uri, label=label, comment=comment, parent=parent,
        )

    # 3. Find all properties and their domain/range
    prop_types = {OWL_DATATYPE_PROP, OWL_OBJECT_PROP, RDF_PROPERTY}
    prop_uris: set[str] = set()
    for pt in prop_types:
        for quad in store.quads_for_pattern(None, store.parse_named_node(RDF_TYPE), store.parse_named_node(pt), None):
            prop_uris.add(_str(quad.subject))

    # Also find properties declared via rdfs:domain without explicit type
    for quad in store.quads_for_pattern(None, store.parse_named_node(RDFS_DOMAIN), None, None):
        prop_uris.add(_str(quad.subject))

    for prop_uri in prop_uris:
        node = store.parse_named_node(prop_uri)
        domains: list[str] = []
        range_uri: str | None = None
        comment: str | None = None

        for quad in store.quads_for_pattern(node, store.parse_named_node(RDFS_DOMAIN), None, None):
            domains.append(_str(quad.object))
        for quad in store.quads_for_pattern(node, store.parse_named_node(RDFS_RANGE), None, None):
            range_uri = _str(quad.object)
        for quad in store.quads_for_pattern(node, store.parse_named_node(RDFS_COMMENT), None, None):
            comment = quad.object.value

        prop_info = PropertyInfo(predicate=prop_uri, range=range_uri, comment=comment)

        # Assign to domain classes
        for domain_uri in domains:
            for cls in schema.classes.values():
                if cls.uri == domain_uri:
                    cls.properties.append(prop_info)

    # 4. Propagate inherited properties down the hierarchy
    _propagate_inherited_properties(schema)

    del store
    return schema


def _propagate_inherited_properties(schema: Schema) -> None:
    """Copy properties from parent classes to subclasses (property inheritance)."""
    # Build uri → ClassInfo lookup
    uri_to_cls = {cls.uri: cls for cls in schema.classes.values()}

    def _get_ancestor_properties(cls: ClassInfo, visited: set[str] | None = None) -> list[PropertyInfo]:
        if visited is None:
            visited = set()
        if cls.uri in visited:
            return []
        visited.add(cls.uri)
        if cls.parent and cls.parent in uri_to_cls:
            parent_cls = uri_to_cls[cls.parent]
            parent_props = parent_cls.properties + _get_ancestor_properties(parent_cls, visited)
            return parent_props
        return []

    for cls in schema.classes.values():
        inherited = _get_ancestor_properties(cls)
        existing_preds = {p.predicate for p in cls.properties}
        for prop in inherited:
            if prop.predicate not in existing_preds:
                cls.properties.append(prop)
                existing_preds.add(prop.predicate)


def extract_from_data(store: Store) -> Schema:
    """Empirical schema extraction from loaded RDF data. Best-effort fallback.

    Queries the store for all used classes, their predicates, and infers
    ranges from literal datatypes and object types.
    """
    schema = Schema()

    # 1. Find all classes by usage
    class_results = store.query(
        "SELECT ?class (COUNT(DISTINCT ?s) AS ?count) "
        "WHERE { ?s a ?class } "
        "GROUP BY ?class ORDER BY DESC(?count)"
    )
    for row in class_results:
        uri = _str(row[0])
        local_name = uri.rsplit("#", 1)[-1] if "#" in uri else uri.rsplit("/", 1)[-1]
        schema.classes[local_name] = ClassInfo(uri=uri, label=local_name)

    # 2. Find properties per class with sample ranges
    prop_results = store.query(
        "SELECT ?class ?pred (SAMPLE(?o) AS ?sample_obj) (COUNT(*) AS ?usage) "
        "WHERE { ?s a ?class ; ?pred ?o } "
        "GROUP BY ?class ?pred ORDER BY ?class DESC(?usage)"
    )
    for row in prop_results:
        class_uri = _str(row[0])
        pred_uri = _str(row[1])

        # Skip rdf:type itself
        if pred_uri == RDF_TYPE:
            continue

        # Determine range from sample object
        sample = row[2]
        range_uri = None
        if hasattr(sample, "datatype") and sample.datatype:
            range_uri = _str(sample.datatype)
        elif hasattr(sample, "value") and sample.value.startswith("http"):
            # It's a named node — try to find its type
            type_results = store.query(
                f"SELECT ?type WHERE {{ <{sample.value}> a ?type }} LIMIT 1"
            )
            for type_row in type_results:
                range_uri = _str(type_row[0])

        prop_info = PropertyInfo(predicate=pred_uri, range=range_uri)

        # Add to the right class
        for cls in schema.classes.values():
            if cls.uri == class_uri:
                cls.properties.append(prop_info)
                break

    return schema


def extract_schema(
    data_path: Path | None = None,
    ontology_path: Path | None = None,
) -> Schema:
    """Extract schema from ontology (preferred) or data (fallback).

    If both are provided, uses the ontology for authoritative schema
    and the data could be used for enrichment (future).
    """
    if ontology_path and ontology_path.exists():
        logger.info("Extracting schema from ontology: %s", ontology_path)
        return extract_from_ontology(ontology_path)

    if data_path and data_path.exists():
        logger.info("Extracting schema empirically from data: %s", data_path)
        from linked_past_store.verify import detect_format
        store = Store()
        fmt = detect_format(data_path)
        store.bulk_load(path=str(data_path), format=fmt)
        schema = extract_from_data(store)
        del store
        return schema

    raise ValueError("Either ontology_path or data_path must be provided and exist")


def generate_schemas_yaml(
    schema: Schema,
    output_path: Path,
    prefix_map: dict[str, str] | None = None,
) -> None:
    """Write schema to YAML format compatible with linked-past plugin context."""
    content = schema.to_schemas_yaml(prefix_map=prefix_map)
    output_path.write_text(content)
    logger.info("Wrote schemas.yaml to %s (%d classes)", output_path, len(schema.classes))
```

- [ ] **Run test to verify it passes**

Run: `uv run pytest packages/linked-past-store/tests/test_ontology.py -v`
Expected: All 4 tests PASS

#### Step 1.3: Write and run tests for empirical extraction

- [ ] **Write test**

Add to `packages/linked-past-store/tests/test_ontology.py`:

```python
from linked_past_store.ontology import extract_from_data


SAMPLE_DATA = """\
@prefix ex: <http://example.org/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

ex:person1 a ex:Person ;
    ex:hasName "Julius Caesar" ;
    ex:hasAge 55 .

ex:person2 a ex:Person ;
    ex:hasName "Pompey" ;
    ex:hasAge 58 .

ex:office1 a ex:Office ;
    ex:hasTitle "Consul" .
"""


def test_extract_from_data(tmp_path):
    from pyoxigraph import RdfFormat, Store

    data_file = tmp_path / "data.ttl"
    data_file.write_text(SAMPLE_DATA)

    store = Store()
    store.bulk_load(path=str(data_file), format=RdfFormat.TURTLE)

    schema = extract_from_data(store)

    assert "Person" in schema.classes
    assert "Office" in schema.classes
    # Person should have hasName, hasAge properties
    person_preds = {p.predicate for p in schema.classes["Person"].properties}
    assert "http://example.org/hasName" in person_preds
    assert "http://example.org/hasAge" in person_preds
    del store
```

- [ ] **Run test**

Run: `uv run pytest packages/linked-past-store/tests/test_ontology.py::test_extract_from_data -v`
Expected: PASS

#### Step 1.4: Write and run test for YAML output

- [ ] **Write test**

Add to `packages/linked-past-store/tests/test_ontology.py`:

```python
from linked_past_store.ontology import generate_schemas_yaml


def test_generate_schemas_yaml(tmp_path):
    owl_file = tmp_path / "ontology.ttl"
    owl_file.write_text(SAMPLE_OWL)
    output = tmp_path / "schemas.yaml"

    schema = extract_from_ontology(owl_file)
    prefix_map = {"http://example.org/onto#": "vocab:"}
    generate_schemas_yaml(schema, output, prefix_map=prefix_map)

    content = yaml.safe_load(output.read_text())
    assert "classes" in content
    person = content["classes"]["Person"]
    assert person["uri"] == "vocab:Person"
    assert person["label"] == "Person"
    # Properties should use shortened URIs
    pred_names = [p["pred"] for p in person["properties"]]
    assert "vocab:hasAge" in pred_names
```

- [ ] **Run test**

Run: `uv run pytest packages/linked-past-store/tests/test_ontology.py::test_generate_schemas_yaml -v`
Expected: PASS

#### Step 1.5: Write and run test for extract_schema dispatcher

- [ ] **Write test**

Add to `packages/linked-past-store/tests/test_ontology.py`:

```python
from linked_past_store.ontology import extract_schema


def test_extract_schema_prefers_ontology(tmp_path):
    owl_file = tmp_path / "ontology.ttl"
    owl_file.write_text(SAMPLE_OWL)
    data_file = tmp_path / "data.ttl"
    data_file.write_text(SAMPLE_DATA)

    # When both provided, ontology wins
    schema = extract_schema(ontology_path=owl_file, data_path=data_file)
    # Ontology has ThingWithName; data does not
    assert "ThingWithName" in schema.classes


def test_extract_schema_falls_back_to_data(tmp_path):
    data_file = tmp_path / "data.ttl"
    data_file.write_text(SAMPLE_DATA)

    schema = extract_schema(data_path=data_file)
    assert "Person" in schema.classes
    assert "ThingWithName" not in schema.classes  # not in data
```

- [ ] **Run test**

Run: `uv run pytest packages/linked-past-store/tests/test_ontology.py -v`
Expected: All tests PASS

- [ ] **Commit**

```bash
git add packages/linked-past-store/linked_past_store/ontology.py packages/linked-past-store/tests/test_ontology.py
git commit -m "feat: ontology-aware schema extraction (OWL/RDFS + empirical fallback)"
```

---

### Task 2: Multi-Document Embedding per Schema Class

**Files:**
- Modify: `packages/linked-past/linked_past/core/server.py:49-81` (the `_build_embeddings` function)
- Create: `packages/linked-past/tests/test_embeddings_multi.py`

#### Step 2.1: Write test for multi-document embedding

- [ ] **Write test**

Create `packages/linked-past/tests/test_embeddings_multi.py`:

```python
"""Tests for multi-document embedding strategy in _build_embeddings."""

from unittest.mock import MagicMock, patch

from linked_past.core.embeddings import EmbeddingIndex


def test_schema_class_produces_multiple_documents():
    """Each schema class should produce separate documents for label+URI and comment."""
    index = EmbeddingIndex()  # in-memory

    # Simulate what _build_embeddings should do for a schema class
    cls_name = "Person"
    cls_data = {
        "comment": "A historical person from the Roman Republic period.",
        "uri": "vocab:Person",
        "label": "Person",
    }

    # Label + URI document
    index.add("dprr", "schema_label", f"{cls_data.get('label', cls_name)} ({cls_data['uri']})")
    # Comment document
    index.add("dprr", "schema_comment", f"{cls_name}: {cls_data['comment']}")

    rows = index._conn.execute("SELECT doc_type, text FROM documents ORDER BY id").fetchall()
    assert len(rows) == 2
    assert rows[0][0] == "schema_label"
    assert "Person" in rows[0][1]
    assert "vocab:Person" in rows[0][1]
    assert rows[1][0] == "schema_comment"
    assert "historical person" in rows[1][1]
    index.close()


def test_example_queries_embedded_per_class():
    """Example queries mentioning a class should be embedded as separate documents."""
    index = EmbeddingIndex()

    examples = [
        {"question": "Who held the office of consul?", "sparql": "SELECT ?p WHERE { ?p a vocab:Person }"},
        {"question": "List all offices", "sparql": "SELECT ?o WHERE { ?o a vocab:Office }"},
    ]

    for ex in examples:
        index.add("dprr", "example", f"{ex['question']}\n{ex['sparql']}")

    count = index._conn.execute("SELECT COUNT(*) FROM documents WHERE doc_type = 'example'").fetchone()[0]
    assert count == 2
    index.close()
```

- [ ] **Run test to verify it passes** (tests the embedding index API, not the integration)

Run: `uv run pytest packages/linked-past/tests/test_embeddings_multi.py -v`
Expected: PASS

#### Step 2.2: Update `_build_embeddings` for multi-document strategy

- [ ] **Modify `server.py`**

In `packages/linked-past/linked_past/core/server.py`, replace the `_build_embeddings` function (lines 49–81) with:

```python
def _build_embeddings(registry: DatasetRegistry, data_dir: Path) -> EmbeddingIndex | None:
    """Load or build embedding index from plugin context. Skips rebuild if DB is populated."""
    try:
        embeddings_path = data_dir / "embeddings.db"
        embeddings = EmbeddingIndex(embeddings_path)

        # Check if already populated — skip expensive rebuild
        existing = embeddings._conn.execute("SELECT COUNT(*) FROM documents WHERE embedding IS NOT NULL").fetchone()[0]
        if existing > 0:
            logger.info("Embedding index loaded from cache (%d documents)", existing)
            return embeddings

        # First time — build from scratch
        logger.info("Building embedding index (first time)...")
        for name in registry.list_datasets():
            plugin = registry.get_plugin(name)
            embeddings.add(name, "dataset", f"{plugin.display_name}: {plugin.description}")
            if hasattr(plugin, "_examples"):
                for ex in plugin._examples:
                    embeddings.add(name, "example", f"{ex['question']}\n{ex['sparql']}")
            if hasattr(plugin, "_tips"):
                for tip in plugin._tips:
                    embeddings.add(name, "tip", f"{tip['title']}: {tip['body']}")
            if hasattr(plugin, "_schemas"):
                for cls_name, cls_data in plugin._schemas.items():
                    # Multi-document: separate embeddings for label+URI vs comment
                    label = cls_data.get("label", cls_name)
                    uri = cls_data.get("uri", "")
                    comment = cls_data.get("comment", "")

                    # Document 1: class label + URI (matches "what class is X?")
                    if uri:
                        embeddings.add(name, "schema_label", f"{label} ({uri})")
                    else:
                        embeddings.add(name, "schema_label", label)

                    # Document 2: class description (matches semantic questions)
                    if comment:
                        embeddings.add(name, "schema_comment", f"{cls_name}: {comment}")

                    # Document 3+: example queries that reference this class
                    if hasattr(plugin, "_examples"):
                        for ex in plugin._examples:
                            if cls_name.lower() in ex.get("sparql", "").lower():
                                embeddings.add(
                                    name,
                                    "schema_example",
                                    f"{cls_name} — {ex['question']}\n{ex['sparql']}",
                                )

        embeddings.build()
        logger.info("Embedding index built and cached")
        return embeddings
    except Exception as e:
        logger.warning("Failed to build embedding index: %s", e)
        return None
```

- [ ] **Run lint**

Run: `uv run ruff check packages/linked-past/linked_past/core/server.py`
Expected: No errors

- [ ] **Commit**

```bash
git add packages/linked-past/linked_past/core/server.py packages/linked-past/tests/test_embeddings_multi.py
git commit -m "feat: multi-document embedding per schema class for improved recall"
```

---

### Task 3: VoID Generation Module (`void.py`)

**Files:**
- Create: `packages/linked-past-store/linked_past_store/void.py`
- Create: `packages/linked-past-store/tests/test_void.py`
- Modify: `packages/linked-past-store/linked_past_store/__init__.py` (export)

#### Step 3.1: Write test for VoID generation from data

- [ ] **Write test**

Create `packages/linked-past-store/tests/test_void.py`:

```python
"""Tests for VoID generation."""

from pyoxigraph import RdfFormat, Store

from linked_past_store.void import generate_void, VoidDescription


SAMPLE_DATA = """\
@prefix ex: <http://example.org/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

ex:person1 a ex:Person ;
    ex:hasName "Julius Caesar" ;
    ex:hasAge 55 .

ex:person2 a ex:Person ;
    ex:hasName "Pompey" ;
    ex:hasAge 58 .

ex:office1 a ex:Office ;
    ex:hasTitle "Consul" .
"""


def test_generate_void_from_data(tmp_path):
    data_file = tmp_path / "data.ttl"
    data_file.write_text(SAMPLE_DATA)

    void = generate_void(
        data_path=data_file,
        dataset_id="test",
        title="Test Dataset",
        license_uri="https://creativecommons.org/licenses/by/4.0/",
        source_uri="https://example.org",
    )

    assert isinstance(void, VoidDescription)
    assert void.triples == 7  # 2 type + 2 name + 2 age + 1 title
    assert void.classes == 2  # Person, Office
    assert void.properties == 4  # rdf:type, hasName, hasAge, hasTitle
    assert void.uri_space == "http://example.org/"


def test_generate_void_turtle_output(tmp_path):
    data_file = tmp_path / "data.ttl"
    data_file.write_text(SAMPLE_DATA)

    void = generate_void(
        data_path=data_file,
        dataset_id="test",
        title="Test Dataset",
        license_uri="https://creativecommons.org/licenses/by/4.0/",
        source_uri="https://example.org",
    )

    ttl = void.to_turtle()
    assert "void:Dataset" in ttl
    assert "Test Dataset" in ttl
    assert "void:triples" in ttl
    assert "void:classes" in ttl
    assert "void:properties" in ttl

    # Verify the output is valid Turtle
    store = Store()
    store.load(ttl.encode(), format=RdfFormat.TURTLE)
    assert len(store) > 0
    del store


def test_generate_void_writes_file(tmp_path):
    data_file = tmp_path / "data.ttl"
    data_file.write_text(SAMPLE_DATA)
    output = tmp_path / "void.ttl"

    void = generate_void(
        data_path=data_file,
        dataset_id="test",
        title="Test Dataset",
        license_uri="https://creativecommons.org/licenses/by/4.0/",
        source_uri="https://example.org",
        output_path=output,
    )

    assert output.exists()
    content = output.read_text()
    assert "void:Dataset" in content


def test_void_entities_count(tmp_path):
    data_file = tmp_path / "data.ttl"
    data_file.write_text(SAMPLE_DATA)

    void = generate_void(
        data_path=data_file,
        dataset_id="test",
        title="Test Dataset",
    )

    # 3 entities have rdf:type: person1, person2, office1
    assert void.entities == 3


def test_void_example_resource(tmp_path):
    data_file = tmp_path / "data.ttl"
    data_file.write_text(SAMPLE_DATA)

    void = generate_void(
        data_path=data_file,
        dataset_id="test",
        title="Test Dataset",
    )

    assert void.example_resource is not None
    assert void.example_resource.startswith("http://example.org/")
```

- [ ] **Run test to verify it fails**

Run: `uv run pytest packages/linked-past-store/tests/test_void.py -v`
Expected: FAIL (module not found)

#### Step 3.2: Implement VoID generation

- [ ] **Write implementation**

Create `packages/linked-past-store/linked_past_store/void.py`:

```python
"""Generate VoID (Vocabulary of Interlinked Datasets) descriptions from RDF data."""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from pyoxigraph import Store

from linked_past_store.verify import detect_format

logger = logging.getLogger(__name__)


@dataclass
class VoidDescription:
    """VoID dataset description with computed metrics."""

    dataset_id: str
    title: str
    triples: int = 0
    entities: int = 0
    classes: int = 0
    properties: int = 0
    uri_space: str = ""
    example_resource: str | None = None
    license_uri: str | None = None
    source_uri: str | None = None
    citation: str | None = None
    publisher: str | None = None
    description: str | None = None
    linksets: list[dict[str, str | int]] = field(default_factory=list)

    def to_turtle(self) -> str:
        """Serialize as VoID Turtle."""
        lines = [
            '@prefix void: <http://rdfs.org/ns/void#> .',
            '@prefix dcterms: <http://purl.org/dc/terms/> .',
            '@prefix foaf: <http://xmlns.com/foaf/0.1/> .',
            '@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .',
            '',
            '<> a void:Dataset ;',
            f'    dcterms:title "{_escape(self.title)}" ;',
        ]

        if self.description:
            lines.append(f'    dcterms:description "{_escape(self.description)}" ;')
        if self.license_uri:
            lines.append(f'    dcterms:license <{self.license_uri}> ;')
        if self.source_uri:
            lines.append(f'    dcterms:source <{self.source_uri}> ;')

        lines.append(f'    void:triples {self.triples} ;')
        lines.append(f'    void:entities {self.entities} ;')
        lines.append(f'    void:classes {self.classes} ;')
        lines.append(f'    void:properties {self.properties} ;')

        if self.uri_space:
            lines.append(f'    void:uriSpace "{self.uri_space}" ;')
        if self.example_resource:
            lines.append(f'    void:exampleResource <{self.example_resource}> ;')

        if self.publisher:
            lines.append('    dcterms:publisher [')
            lines.append('        a foaf:Organization ;')
            lines.append(f'        foaf:name "{_escape(self.publisher)}"')
            lines.append('    ] ;')

        if self.citation:
            lines.append(f'    dcterms:bibliographicCitation "{_escape(self.citation)}" ;')

        for ls in self.linksets:
            lines.append('    void:subset [')
            lines.append('        a void:Linkset ;')
            lines.append(f'        void:target <{ls["target"]}> ;')
            lines.append(f'        void:linkPredicate <{ls["predicate"]}> ;')
            lines.append(f'        void:triples {ls["count"]}')
            lines.append('    ] ;')

        # Replace trailing " ;" with " ."
        if lines[-1].endswith(" ;"):
            lines[-1] = lines[-1][:-2] + " ."
        else:
            lines.append('    .')

        return "\n".join(lines) + "\n"


def _escape(s: str) -> str:
    """Escape a string for use in Turtle literals."""
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _compute_uri_space(store: Store) -> str:
    """Find the most common URI prefix among typed subjects."""
    results = store.query(
        "SELECT ?s WHERE { ?s a ?type } LIMIT 500"
    )
    uris = []
    for row in results:
        uri = str(row[0]).strip("<>")
        if uri.startswith("http"):
            uris.append(uri)

    if not uris:
        return ""

    # Find longest common prefix
    prefix = uris[0]
    for uri in uris[1:]:
        while not uri.startswith(prefix):
            # Trim to last / or #
            cut = max(prefix.rfind("/"), prefix.rfind("#"))
            if cut <= 0:
                return ""
            prefix = prefix[: cut + 1]

    return prefix


def generate_void(
    data_path: Path | str,
    dataset_id: str,
    title: str,
    license_uri: str | None = None,
    source_uri: str | None = None,
    citation: str | None = None,
    publisher: str | None = None,
    description: str | None = None,
    output_path: Path | str | None = None,
) -> VoidDescription:
    """Generate a VoID description from an RDF data file.

    Args:
        data_path: Path to the RDF data file.
        dataset_id: Short identifier for the dataset (e.g., "dprr").
        title: Human-readable title.
        license_uri: License URI (e.g., Creative Commons).
        source_uri: Upstream source URL.
        citation: Bibliographic citation string.
        publisher: Publisher name.
        description: Dataset description.
        output_path: If provided, write VoID Turtle to this path.

    Returns:
        VoidDescription with computed metrics.
    """
    data_path = Path(data_path)
    fmt = detect_format(data_path)
    store = Store()
    store.bulk_load(path=str(data_path), format=fmt)

    triple_count = len(store)

    class_result = store.query(
        "SELECT (COUNT(DISTINCT ?c) AS ?n) WHERE { ?s a ?c }"
    )
    class_count = int(next(iter(class_result))[0].value)

    prop_result = store.query(
        "SELECT (COUNT(DISTINCT ?p) AS ?n) WHERE { ?s ?p ?o }"
    )
    prop_count = int(next(iter(prop_result))[0].value)

    entity_result = store.query(
        "SELECT (COUNT(DISTINCT ?s) AS ?n) WHERE { ?s a ?type }"
    )
    entity_count = int(next(iter(entity_result))[0].value)

    uri_space = _compute_uri_space(store)

    example = None
    example_result = store.query("SELECT ?s WHERE { ?s a ?type } LIMIT 1")
    for row in example_result:
        example = str(row[0]).strip("<>")

    del store

    void = VoidDescription(
        dataset_id=dataset_id,
        title=title,
        triples=triple_count,
        entities=entity_count,
        classes=class_count,
        properties=prop_count,
        uri_space=uri_space,
        example_resource=example,
        license_uri=license_uri,
        source_uri=source_uri,
        citation=citation,
        publisher=publisher,
        description=description,
    )

    if output_path:
        output_path = Path(output_path)
        output_path.write_text(void.to_turtle())
        logger.info("Wrote VoID to %s", output_path)

    return void
```

- [ ] **Run test to verify it passes**

Run: `uv run pytest packages/linked-past-store/tests/test_void.py -v`
Expected: All 5 tests PASS

#### Step 3.3: Update `__init__.py` exports

- [ ] **Modify exports**

In `packages/linked-past-store/linked_past_store/__init__.py`, add:

```python
from linked_past_store.void import generate_void
```

And update `__all__` to include `"generate_void"`.

- [ ] **Commit**

```bash
git add packages/linked-past-store/linked_past_store/void.py packages/linked-past-store/tests/test_void.py packages/linked-past-store/linked_past_store/__init__.py
git commit -m "feat: VoID generation module — auto-extract dataset metrics from RDF"
```

---

### Task 4: Add CLI Subcommands for Ontology and VoID

**Files:**
- Modify: `packages/linked-past-store/linked_past_store/cli.py`

#### Step 4.1: Add `ontology extract` and `void generate` CLI subcommands

- [ ] **Modify `cli.py`**

Add two new command functions and wire them into the argument parser in `packages/linked-past-store/linked_past_store/cli.py`:

```python
def cmd_ontology_extract(args):
    from pathlib import Path
    from linked_past_store.ontology import extract_schema, generate_schemas_yaml

    ontology_path = Path(args.ontology) if args.ontology else None
    data_path = Path(args.from_data) if args.from_data else None
    output = Path(args.output)

    prefix_map = {}
    if args.prefix:
        for p in args.prefix:
            ns, short = p.split("=", 1)
            prefix_map[ns] = short

    schema = extract_schema(ontology_path=ontology_path, data_path=data_path)
    generate_schemas_yaml(schema, output, prefix_map=prefix_map or None)
    print(f"Wrote {len(schema.classes)} classes to {output}")


def cmd_void_generate(args):
    from pathlib import Path
    from linked_past_store.void import generate_void

    void = generate_void(
        data_path=args.data,
        dataset_id=args.dataset_id,
        title=args.title,
        license_uri=args.license,
        source_uri=args.source,
        citation=args.citation,
        publisher=args.publisher,
        output_path=Path(args.output) if args.output else None,
    )

    print(f"Dataset: {void.title}")
    print(f"  Triples:    {void.triples:,}")
    print(f"  Entities:   {void.entities:,}")
    print(f"  Classes:    {void.classes}")
    print(f"  Properties: {void.properties}")
    print(f"  URI space:  {void.uri_space}")
    if args.output:
        print(f"  Written to: {args.output}")
    else:
        print(void.to_turtle())
```

Wire into `main()` parser:

```python
    # ontology
    onto_parser = sub.add_parser("ontology", help="Extract schema from ontology or data")
    onto_sub = onto_parser.add_subparsers(dest="ontology_command", required=True)

    p = onto_sub.add_parser("extract", help="Extract schema to YAML")
    p.add_argument("ontology", nargs="?", help="OWL/RDFS ontology file")
    p.add_argument("--from-data", help="RDF data file for empirical extraction")
    p.add_argument("--output", "-o", default="schemas.yaml", help="Output YAML file")
    p.add_argument("--prefix", action="append", help="Prefix mapping: namespace=short (e.g. http://example.org/#=vocab:)")
    p.set_defaults(func=cmd_ontology_extract)

    # void
    void_parser = sub.add_parser("void", help="Generate VoID dataset descriptions")
    void_sub = void_parser.add_subparsers(dest="void_command", required=True)

    p = void_sub.add_parser("generate", help="Generate VoID from data")
    p.add_argument("data", help="RDF data file")
    p.add_argument("--dataset-id", required=True, help="Short dataset identifier")
    p.add_argument("--title", required=True, help="Human-readable dataset title")
    p.add_argument("--license", help="License URI")
    p.add_argument("--source", help="Upstream source URL")
    p.add_argument("--citation", help="Bibliographic citation")
    p.add_argument("--publisher", help="Publisher name")
    p.add_argument("--output", "-o", help="Output file (prints to stdout if omitted)")
    p.set_defaults(func=cmd_void_generate)
```

- [ ] **Run lint**

Run: `uv run ruff check packages/linked-past-store/linked_past_store/cli.py`
Expected: No errors

- [ ] **Commit**

```bash
git add packages/linked-past-store/linked_past_store/cli.py
git commit -m "feat: CLI subcommands for ontology extract and void generate"
```

---

### Task 5: Update Push to Support Multi-File + VoID Sidecar

**Files:**
- Modify: `packages/linked-past-store/linked_past_store/push.py`

#### Step 5.1: Extend `push_dataset` for multi-file + VoID

- [ ] **Modify `push.py`**

Replace the `push_dataset` function in `packages/linked-past-store/linked_past_store/push.py`:

```python
def push_dataset(
    ref: str,
    path: str | Path | list[str | Path],
    annotations: dict[str, str] | None = None,
    media_type: str = "application/x-turtle",
    void_path: str | Path | None = None,
) -> str:
    """Push RDF file(s) to an OCI registry as an artifact.

    Args:
        ref: OCI reference (e.g., "ghcr.io/myorg/dataset:v1.0")
        path: Path(s) to RDF file(s) to push. Single path or list of paths.
        annotations: OCI manifest annotations (license, citation, etc.)
        media_type: MIME type for the artifact layers
        void_path: Optional path to VoID description file (pushed as additional layer)

    Returns:
        The digest of the pushed artifact (sha256:...)
    """
    # Normalize to list
    if isinstance(path, (str, Path)):
        paths = [Path(path)]
    else:
        paths = [Path(p) for p in path]

    for p in paths:
        if not p.exists():
            raise FileNotFoundError(f"File not found: {p}")

    if void_path:
        void_path = Path(void_path)
        if not void_path.exists():
            raise FileNotFoundError(f"VoID file not found: {void_path}")

    # All files must be in same directory for oras push
    # Use the first file's parent as cwd
    cwd = paths[0].parent

    cmd = ["oras", "push", ref]
    for p in paths:
        cmd.append(f"{p.name}:{media_type}")
    if void_path:
        cmd.append(f"{void_path.name}:{media_type}")

    if annotations:
        for key, val in annotations.items():
            cmd.extend(["--annotation", f"{key}={val}"])

    logger.info("Pushing %d file(s) to %s", len(paths), ref)
    result = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, check=True)

    # Extract digest from output
    for line in result.stdout.splitlines():
        if line.startswith("Digest:"):
            digest = line.split(":", 1)[1].strip()
            logger.info("Pushed %s (digest: %s)", ref, digest)
            return digest

    return ""
```

- [ ] **Run lint**

Run: `uv run ruff check packages/linked-past-store/linked_past_store/push.py`
Expected: No errors

- [ ] **Commit**

```bash
git add packages/linked-past-store/linked_past_store/push.py
git commit -m "feat: push_dataset supports multi-file artifacts + VoID sidecar"
```

---

### Task 6: Refactor Packaging Scripts to Use `linked-past-store`

**Files:**
- Modify: `scripts/package_dprr.py`
- Modify: `scripts/package_pleiades.py`
- Modify: `scripts/package_edh.py`

#### Step 6.1: Refactor `package_dprr.py`

- [ ] **Rewrite script**

Replace `scripts/package_dprr.py`:

```python
"""Download DPRR data, generate VoID, and push to OCI registry."""

import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

from linked_past_store import push_dataset, verify_turtle
from linked_past_store.void import generate_void

SOURCE_URL = "https://github.com/gillisandrew/dprr-mcp/releases/latest/download/dprr-data.tar.gz"
ARTIFACT_REF = "ghcr.io/gillisandrew/linked-past/dprr"

ANNOTATIONS = {
    "org.opencontainers.image.source": "https://romanrepublic.ac.uk",
    "org.opencontainers.image.description": "Digital Prosopography of the Roman Republic (DPRR) RDF dataset",
    "org.opencontainers.image.licenses": "CC-BY-NC-4.0",
    "org.opencontainers.image.url": "https://github.com/gillisandrew/linked-past",
    "org.opencontainers.image.vendor": "King's College London",
    "dev.linked-past.dataset": "dprr",
    "dev.linked-past.source-url": SOURCE_URL,
    "dev.linked-past.format": "text/turtle",
}


def main(version="latest"):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        print(f"Downloading {SOURCE_URL}...")
        tmp_path, _ = urllib.request.urlretrieve(SOURCE_URL)
        with tarfile.open(tmp_path, "r:gz") as tar:
            tar.extract("dprr.ttl", path=str(tmpdir), filter="data")
        Path(tmp_path).unlink()

        data_file = tmpdir / "dprr.ttl"

        # Verify
        result = verify_turtle(data_file)
        if not result.ok:
            print(f"Verification failed: {result.errors[0]}")
            sys.exit(1)
        print(f"Verified: {result.triple_count:,} triples")

        # Generate VoID
        void = generate_void(
            data_path=data_file,
            dataset_id="dprr",
            title="Digital Prosopography of the Roman Republic (DPRR)",
            license_uri="https://creativecommons.org/licenses/by-nc/4.0/",
            source_uri="https://romanrepublic.ac.uk/",
            citation="Mouritsen et al., DPRR, King's Digital Lab, 2017. https://romanrepublic.ac.uk/",
            publisher="King's College London",
            output_path=tmpdir / "void.ttl",
        )
        print(f"Generated VoID: {void.triples:,} triples, {void.classes} classes")

        # Push
        annotations = {
            **ANNOTATIONS,
            "org.opencontainers.image.version": version,
            "dev.linked-past.triples": str(result.triple_count),
        }
        ref = f"{ARTIFACT_REF}:{version}"
        digest = push_dataset(
            ref,
            data_file,
            annotations=annotations,
            void_path=tmpdir / "void.ttl",
        )
        print(f"Done: {ref}")
        if digest:
            print(f"Digest: {digest}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "latest")
```

#### Step 6.2: Refactor `package_pleiades.py`

- [ ] **Rewrite script**

Replace `scripts/package_pleiades.py`:

```python
"""Download Pleiades RDF dump, sanitize for Oxigraph, generate VoID, and push to OCI registry."""

import re
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

from linked_past_store import push_dataset, sanitize_turtle, verify_turtle
from linked_past_store.void import generate_void

SOURCE_URL = "https://atlantides.org/downloads/pleiades/rdf/pleiades-latest.tar.gz"
ARTIFACT_REF = "ghcr.io/gillisandrew/linked-past/pleiades"

ANNOTATIONS = {
    "org.opencontainers.image.source": "https://pleiades.stoa.org",
    "org.opencontainers.image.description": (
        "Pleiades: A Gazetteer of Past Places (sanitized for Oxigraph)"
    ),
    "org.opencontainers.image.licenses": "CC-BY-3.0",
    "org.opencontainers.image.url": "https://github.com/gillisandrew/linked-past",
    "org.opencontainers.image.vendor": "Institute for the Study of the Ancient World (NYU)",
    "dev.linked-past.dataset": "pleiades",
    "dev.linked-past.source-url": SOURCE_URL,
    "dev.linked-past.format": "text/turtle",
    "dev.linked-past.citation": (
        "Bagnall, R. et al. (eds.), Pleiades. DOI: 10.5281/zenodo.1193921"
    ),
}

# BCP 47: subtags must be max 8 characters
_LANG_TAG = re.compile(r'"([^"]*)"@([a-zA-Z][a-zA-Z0-9-]*)')
_BARE_DOI = re.compile(r'<(doi\.org/)')


def _fix_lang_tag(match: re.Match) -> str:
    text = match.group(1)
    tag = match.group(2)
    parts = tag.split("-")
    fixed_parts = [part[:8] if len(part) > 8 else part for part in parts]
    return f'"{text}"@{"-".join(fixed_parts)}'


def _sanitize_pleiades(text: str) -> tuple[str, int]:
    fixes = 0
    text, n = _LANG_TAG.subn(_fix_lang_tag, text)
    fixes += n
    text, n = _BARE_DOI.subn(r'<https://\1', text)
    fixes += n
    return text, fixes


def main(version="latest"):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        print(f"Downloading {SOURCE_URL}...")
        tmp_path, _ = urllib.request.urlretrieve(SOURCE_URL)

        print("Extracting and concatenating Turtle files...")
        raw = tmpdir / "pleiades_raw.ttl"
        with tarfile.open(tmp_path, "r:gz") as tar, open(raw, "w") as out:
            for member in sorted(tar.getnames()):
                if member.endswith(".ttl"):
                    f = tar.extractfile(member)
                    if f:
                        out.write(f"# Source: {member}\n")
                        out.write(f.read().decode("utf-8"))
                        out.write("\n\n")
        Path(tmp_path).unlink()
        print(f"Raw: {raw.stat().st_size:,} bytes")

        # Fix Pleiades-specific issues
        print("Sanitizing (fixing BCP 47 language tags)...")
        text = raw.read_text()
        fixed_text, fix_count = _sanitize_pleiades(text)
        print(f"Applied fixes to {fix_count} literals")

        output = tmpdir / "pleiades.ttl"
        output.write_text(fixed_text)

        # Verify
        result = verify_turtle(output)
        if not result.ok:
            print(f"Verification failed: {result.errors[0]}")
            sys.exit(1)
        print(f"Verified: {result.triple_count:,} triples")

        # Generate VoID
        void = generate_void(
            data_path=output,
            dataset_id="pleiades",
            title="Pleiades: A Gazetteer of Past Places",
            license_uri="https://creativecommons.org/licenses/by/3.0/",
            source_uri="https://pleiades.stoa.org/",
            citation="Bagnall, R. et al. (eds.), Pleiades. DOI: 10.5281/zenodo.1193921",
            publisher="Institute for the Study of the Ancient World (NYU)",
            output_path=tmpdir / "void.ttl",
        )
        print(f"Generated VoID: {void.triples:,} triples, {void.classes} classes")

        # Push
        annotations = {
            **ANNOTATIONS,
            "org.opencontainers.image.version": version,
            "dev.linked-past.triples": str(result.triple_count),
        }
        ref = f"{ARTIFACT_REF}:{version}"
        digest = push_dataset(
            ref,
            output,
            annotations=annotations,
            void_path=tmpdir / "void.ttl",
        )
        print(f"Done: {ref}")
        if digest:
            print(f"Digest: {digest}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "latest")
```

#### Step 6.3: Refactor `package_edh.py`

- [ ] **Rewrite script**

Replace `scripts/package_edh.py`:

```python
"""Extract EDH Turtle files from local zip, generate VoID, and push to OCI registry."""

import sys
import tempfile
import zipfile
from pathlib import Path

from linked_past_store import push_dataset, verify_turtle
from linked_past_store.void import generate_void

LOCAL_ZIP = Path(__file__).parent.parent / "edh_linked_data.zip"
ARTIFACT_REF = "ghcr.io/gillisandrew/linked-past/edh"

ANNOTATIONS = {
    "org.opencontainers.image.source": "https://edh.ub.uni-heidelberg.de",
    "org.opencontainers.image.description": "Epigraphic Database Heidelberg — 81K+ Latin inscriptions",
    "org.opencontainers.image.licenses": "CC-BY-SA-4.0",
    "org.opencontainers.image.url": "https://github.com/gillisandrew/linked-past",
    "org.opencontainers.image.vendor": "Heidelberg Academy of Sciences",
    "dev.linked-past.dataset": "edh",
    "dev.linked-past.source-url": "https://edh.ub.uni-heidelberg.de/data/export",
    "dev.linked-past.format": "text/turtle",
    "dev.linked-past.citation": "Epigraphic Database Heidelberg, CC BY-SA 4.0",
}


def main(version="2021-12-16"):
    if not LOCAL_ZIP.exists():
        print(f"ERROR: {LOCAL_ZIP} not found. Place edh_linked_data.zip in the project root.")
        sys.exit(1)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        print(f"Extracting {LOCAL_ZIP}...")
        with zipfile.ZipFile(LOCAL_ZIP) as zf:
            zf.extractall(tmpdir / "raw")

        raw_dir = tmpdir / "raw"
        ttl_files = sorted(raw_dir.glob("*.ttl"))
        print(f"Found {len(ttl_files)} Turtle files")

        out_path = tmpdir / "edh.ttl"
        with open(out_path, "w") as out:
            for i, ttl in enumerate(ttl_files):
                print(f"  Appending {ttl.name} ({ttl.stat().st_size:,} bytes)")
                content = ttl.read_text()
                if i > 0:
                    out.write("\n")
                out.write(content)

        print(f"Created {out_path} ({out_path.stat().st_size:,} bytes)")

        # Verify
        result = verify_turtle(out_path)
        if not result.ok:
            print(f"Verification failed: {result.errors[0]}")
            sys.exit(1)
        print(f"Verified: {result.triple_count:,} triples")

        # Generate VoID
        void = generate_void(
            data_path=out_path,
            dataset_id="edh",
            title="Epigraphic Database Heidelberg (EDH)",
            license_uri="https://creativecommons.org/licenses/by-sa/4.0/",
            source_uri="https://edh.ub.uni-heidelberg.de/",
            citation="Epigraphic Database Heidelberg, CC BY-SA 4.0",
            publisher="Heidelberg Academy of Sciences",
            output_path=tmpdir / "void.ttl",
        )
        print(f"Generated VoID: {void.triples:,} triples, {void.classes} classes")

        # Push
        annotations = {
            **ANNOTATIONS,
            "org.opencontainers.image.version": version,
            "dev.linked-past.triples": str(result.triple_count),
        }
        ref = f"{ARTIFACT_REF}:{version}"
        digest = push_dataset(
            ref,
            out_path,
            annotations=annotations,
            void_path=tmpdir / "void.ttl",
        )
        print(f"Done: {ref}")
        if digest:
            print(f"Digest: {digest}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "2021-12-16")
```

- [ ] **Run lint on all modified scripts**

Run: `uv run ruff check scripts/package_dprr.py scripts/package_pleiades.py scripts/package_edh.py`
Expected: No errors

- [ ] **Commit**

```bash
git add scripts/package_dprr.py scripts/package_pleiades.py scripts/package_edh.py
git commit -m "refactor: packaging scripts use linked-past-store (sanitize, verify, void, push)"
```

---

### Task 7: Add PyYAML Dependency + Final Lint Pass

**Files:**
- Modify: `packages/linked-past-store/pyproject.toml`

#### Step 7.1: Add PyYAML dependency

- [ ] **Modify `pyproject.toml`**

In `packages/linked-past-store/pyproject.toml`, add `"pyyaml"` to the dependencies list:

```toml
dependencies = [
    "oras",
    "pyoxigraph",
    "pyyaml",
]
```

- [ ] **Sync dependencies**

Run: `uv sync`

- [ ] **Run full lint and test suite for linked-past-store**

Run: `uv run ruff check packages/linked-past-store/ && uv run pytest packages/linked-past-store/tests/ -v`
Expected: All pass

- [ ] **Commit**

```bash
git add packages/linked-past-store/pyproject.toml uv.lock
git commit -m "chore: add pyyaml dependency to linked-past-store"
```
