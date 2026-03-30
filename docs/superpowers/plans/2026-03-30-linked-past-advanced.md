# Linked Past: Linkage Graph, Embeddings, and Advanced Tools — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add cross-dataset linkage graph with provenance, embedding-assisted retrieval for query routing, and five advanced MCP tools (search_entities, explore_entity, find_links, get_provenance, update_dataset).

**Architecture:** Three layers: (1) Linkage graph — a dedicated Oxigraph store holding cross-dataset references with PROV-O provenance, loaded from curated YAML files. (2) Embeddings — fastembed + SQLite for indexing examples/tips/schemas across all datasets, enabling semantic search for query routing and context selection. (3) Five new MCP tools that leverage both layers plus the existing dataset stores.

**Tech Stack:** Python 3.13+, fastembed, pyoxigraph, SQLite, numpy (via fastembed)

**Prerequisites:** Plans 1-2 complete. 4 dataset plugins (DPRR, Pleiades, PeriodO, Nomisma) operational with 178 tests passing.

---

## File Structure

```
linked_past/
├── core/
│   ├── linkage.py           # Linkage graph: load YAML, Oxigraph store, query cross-refs
│   ├── embeddings.py        # fastembed + SQLite: index, search, manage embeddings
│   ├── server.py            # (modify: add 5 new tools, wire linkage + embeddings into AppContext)
│   └── registry.py          # (modify: add dataset_for_uri() namespace lookup)
├── linkages/
│   ├── dprr_pleiades.yaml   # DPRR provinces → Pleiades places
│   └── dprr_periodo.yaml    # DPRR eras → PeriodO period definitions
tests/
├── test_linkage.py
├── test_embeddings.py
├── test_advanced_tools.py
```

---

### Task 1: Linkage graph store

**Files:**
- Create: `linked_past/core/linkage.py`
- Create: `linked_past/linkages/dprr_pleiades.yaml` (starter with ~5 entries)
- Create: `linked_past/linkages/dprr_periodo.yaml` (starter with ~3 entries)
- Test: `tests/test_linkage.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_linkage.py
import tempfile
from pathlib import Path

import yaml

from linked_past.core.linkage import LinkageGraph


SAMPLE_LINKAGE_YAML = {
    "metadata": {
        "source_dataset": "dprr",
        "target_dataset": "pleiades",
        "relationship": "owl:sameAs",
        "confidence": "confirmed",
        "method": "manual_alignment",
        "basis": "Barrington Atlas (Talbert 2000)",
        "author": "linked-past project",
        "date": "2026-03-30",
    },
    "links": [
        {
            "source": "http://romanrepublic.ac.uk/rdf/entity/Province/Sicilia",
            "target": "https://pleiades.stoa.org/places/462492#this",
            "note": "Map 47",
        },
        {
            "source": "http://romanrepublic.ac.uk/rdf/entity/Province/Africa",
            "target": "https://pleiades.stoa.org/places/775#this",
            "note": "Map 33",
        },
    ],
}


def test_linkage_graph_load(tmp_path):
    yaml_file = tmp_path / "test_linkage.yaml"
    yaml_file.write_text(yaml.dump(SAMPLE_LINKAGE_YAML))

    graph = LinkageGraph(tmp_path / "store")
    graph.load_yaml(yaml_file)
    assert graph.triple_count() > 0


def test_linkage_graph_find_links(tmp_path):
    yaml_file = tmp_path / "test_linkage.yaml"
    yaml_file.write_text(yaml.dump(SAMPLE_LINKAGE_YAML))

    graph = LinkageGraph(tmp_path / "store")
    graph.load_yaml(yaml_file)

    links = graph.find_links("http://romanrepublic.ac.uk/rdf/entity/Province/Sicilia")
    assert len(links) == 1
    assert links[0]["target"] == "https://pleiades.stoa.org/places/462492#this"
    assert links[0]["relationship"] == "owl:sameAs"
    assert links[0]["confidence"] == "confirmed"


def test_linkage_graph_find_links_reverse(tmp_path):
    yaml_file = tmp_path / "test_linkage.yaml"
    yaml_file.write_text(yaml.dump(SAMPLE_LINKAGE_YAML))

    graph = LinkageGraph(tmp_path / "store")
    graph.load_yaml(yaml_file)

    links = graph.find_links("https://pleiades.stoa.org/places/462492#this")
    assert len(links) == 1
    assert links[0]["target"] == "http://romanrepublic.ac.uk/rdf/entity/Province/Sicilia"


def test_linkage_graph_find_links_empty(tmp_path):
    yaml_file = tmp_path / "test_linkage.yaml"
    yaml_file.write_text(yaml.dump(SAMPLE_LINKAGE_YAML))

    graph = LinkageGraph(tmp_path / "store")
    graph.load_yaml(yaml_file)

    links = graph.find_links("http://example.org/nonexistent")
    assert links == []


def test_linkage_graph_get_provenance(tmp_path):
    yaml_file = tmp_path / "test_linkage.yaml"
    yaml_file.write_text(yaml.dump(SAMPLE_LINKAGE_YAML))

    graph = LinkageGraph(tmp_path / "store")
    graph.load_yaml(yaml_file)

    prov = graph.get_provenance(
        "http://romanrepublic.ac.uk/rdf/entity/Province/Sicilia",
        "https://pleiades.stoa.org/places/462492#this",
    )
    assert prov is not None
    assert prov["basis"] == "Barrington Atlas (Talbert 2000)"
    assert prov["confidence"] == "confirmed"
    assert prov["method"] == "manual_alignment"


def test_linkage_graph_load_multiple_files(tmp_path):
    yaml1 = tmp_path / "link1.yaml"
    yaml1.write_text(yaml.dump(SAMPLE_LINKAGE_YAML))

    yaml2_data = {
        "metadata": {
            "source_dataset": "dprr",
            "target_dataset": "periodo",
            "relationship": "dcterms:temporal",
            "confidence": "confirmed",
            "method": "manual_alignment",
            "basis": "Standard periodization",
            "author": "linked-past project",
            "date": "2026-03-30",
        },
        "links": [
            {
                "source": "http://romanrepublic.ac.uk/rdf/entity/Era/Republic",
                "target": "http://n2t.net/ark:/99152/p05krdxmkzt",
                "note": "Roman Republic period",
            },
        ],
    }
    yaml2 = tmp_path / "link2.yaml"
    yaml2.write_text(yaml.dump(yaml2_data))

    graph = LinkageGraph(tmp_path / "store")
    graph.load_yaml(yaml1)
    graph.load_yaml(yaml2)

    links_sicilia = graph.find_links("http://romanrepublic.ac.uk/rdf/entity/Province/Sicilia")
    assert len(links_sicilia) == 1

    links_era = graph.find_links("http://romanrepublic.ac.uk/rdf/entity/Era/Republic")
    assert len(links_era) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_linkage.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

```python
# linked_past/core/linkage.py
"""Linkage graph: cross-dataset references with provenance."""

from __future__ import annotations

import logging
from pathlib import Path

import yaml
from pyoxigraph import Literal, NamedNode, Quad, Store

logger = logging.getLogger(__name__)

_LINKPAST = "http://linked-past.org/ontology#"
_PROV = "http://www.w3.org/ns/prov#"
_DCTERMS = "http://purl.org/dc/terms/"
_XSD = "http://www.w3.org/2001/XMLSchema#"

# Relationship URI mapping
_RELATIONSHIP_MAP = {
    "owl:sameAs": "http://www.w3.org/2002/07/owl#sameAs",
    "skos:exactMatch": "http://www.w3.org/2004/02/skos/core#exactMatch",
    "skos:closeMatch": "http://www.w3.org/2004/02/skos/core#closeMatch",
    "dcterms:spatial": f"{_DCTERMS}spatial",
    "dcterms:temporal": f"{_DCTERMS}temporal",
}


class LinkageGraph:
    """Manages cross-dataset linkages in a dedicated Oxigraph store."""

    def __init__(self, store_path: Path):
        store_path.mkdir(parents=True, exist_ok=True)
        self._store = Store(str(store_path))

    def triple_count(self) -> int:
        return len(self._store)

    def load_yaml(self, yaml_path: Path) -> int:
        """Load a linkage YAML file into the store. Returns number of links loaded."""
        with open(yaml_path) as f:
            data = yaml.safe_load(f)

        metadata = data["metadata"]
        links = data.get("links", [])
        rel_uri = _RELATIONSHIP_MAP.get(metadata["relationship"], metadata["relationship"])
        count = 0

        for link in links:
            source = NamedNode(link["source"])
            target = NamedNode(link["target"])
            rel = NamedNode(rel_uri)

            # Create a named graph for this link
            graph_name = NamedNode(
                f"http://linked-past.org/linkage/{metadata['source_dataset']}"
                f"--{metadata['target_dataset']}/{count}"
            )

            # The link triple
            self._store.add(Quad(source, rel, target, graph_name))

            # Provenance on the named graph
            self._store.add(Quad(
                graph_name,
                NamedNode(f"{_PROV}wasAttributedTo"),
                Literal(metadata.get("author", "unknown")),
                NamedNode(f"{_LINKPAST}provenance"),
            ))
            self._store.add(Quad(
                graph_name,
                NamedNode(f"{_DCTERMS}source"),
                Literal(metadata.get("basis", "")),
                NamedNode(f"{_LINKPAST}provenance"),
            ))
            self._store.add(Quad(
                graph_name,
                NamedNode(f"{_LINKPAST}confidence"),
                Literal(metadata.get("confidence", "candidate")),
                NamedNode(f"{_LINKPAST}provenance"),
            ))
            self._store.add(Quad(
                graph_name,
                NamedNode(f"{_LINKPAST}method"),
                Literal(metadata.get("method", "unknown")),
                NamedNode(f"{_LINKPAST}provenance"),
            ))
            if link.get("note"):
                self._store.add(Quad(
                    graph_name,
                    NamedNode(f"{_LINKPAST}note"),
                    Literal(link["note"]),
                    NamedNode(f"{_LINKPAST}provenance"),
                ))

            count += 1

        logger.info("Loaded %d links from %s", count, yaml_path.name)
        return count

    def find_links(self, uri: str) -> list[dict]:
        """Find all cross-dataset links for an entity (forward and reverse)."""
        query = f"""
        SELECT ?target ?rel ?graph WHERE {{
            GRAPH ?graph {{ <{uri}> ?rel ?target }}
        }}
        """
        results = []
        for row in self._store.query(query):
            graph_uri = row["graph"].value
            prov = self._get_graph_provenance(graph_uri)
            results.append({
                "target": row["target"].value,
                "relationship": self._shorten_uri(row["rel"].value),
                "confidence": prov.get("confidence", "unknown"),
                "basis": prov.get("basis", ""),
                "direction": "forward",
            })

        # Reverse lookup
        reverse_query = f"""
        SELECT ?source ?rel ?graph WHERE {{
            GRAPH ?graph {{ ?source ?rel <{uri}> }}
        }}
        """
        for row in self._store.query(reverse_query):
            graph_uri = row["graph"].value
            prov = self._get_graph_provenance(graph_uri)
            results.append({
                "target": row["source"].value,
                "relationship": self._shorten_uri(row["rel"].value),
                "confidence": prov.get("confidence", "unknown"),
                "basis": prov.get("basis", ""),
                "direction": "reverse",
            })

        return results

    def get_provenance(self, source_uri: str, target_uri: str) -> dict | None:
        """Get provenance for a specific link between two entities."""
        query = f"""
        SELECT ?graph WHERE {{
            GRAPH ?graph {{ <{source_uri}> ?rel <{target_uri}> }}
        }}
        """
        for row in self._store.query(query):
            return self._get_graph_provenance(row["graph"].value)

        # Try reverse
        query = f"""
        SELECT ?graph WHERE {{
            GRAPH ?graph {{ <{target_uri}> ?rel <{source_uri}> }}
        }}
        """
        for row in self._store.query(query):
            return self._get_graph_provenance(row["graph"].value)

        return None

    def _get_graph_provenance(self, graph_uri: str) -> dict:
        """Retrieve provenance metadata for a named graph."""
        prov_graph = NamedNode(f"{_LINKPAST}provenance")
        query = f"""
        SELECT ?pred ?obj WHERE {{
            GRAPH <{_LINKPAST}provenance> {{
                <{graph_uri}> ?pred ?obj
            }}
        }}
        """
        prov = {}
        for row in self._store.query(query):
            pred = row["pred"].value
            val = row["obj"].value
            if pred.endswith("source"):
                prov["basis"] = val
            elif pred.endswith("confidence"):
                prov["confidence"] = val
            elif pred.endswith("method"):
                prov["method"] = val
            elif pred.endswith("wasAttributedTo"):
                prov["author"] = val
            elif pred.endswith("note"):
                prov["note"] = val
        return prov

    @staticmethod
    def _shorten_uri(uri: str) -> str:
        """Shorten common URIs to prefixed form."""
        for prefix, ns in _RELATIONSHIP_MAP.items():
            if uri == ns:
                return prefix
        if "#" in uri:
            return uri.rsplit("#", 1)[-1]
        return uri.rsplit("/", 1)[-1]
```

- [ ] **Step 4: Create starter linkage YAML files**

```yaml
# linked_past/linkages/dprr_pleiades.yaml
metadata:
  source_dataset: dprr
  target_dataset: pleiades
  relationship: "owl:sameAs"
  confidence: confirmed
  method: manual_alignment
  basis: "Barrington Atlas of the Greek and Roman World (Talbert 2000)"
  author: linked-past project
  date: "2026-03-30"

links:
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/Sicilia"
    target: "https://pleiades.stoa.org/places/462492#this"
    note: "Map 47"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/Africa"
    target: "https://pleiades.stoa.org/places/775#this"
    note: "Map 33"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/Hispania"
    target: "https://pleiades.stoa.org/places/1027#this"
    note: "Map 25-27"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/Asia"
    target: "https://pleiades.stoa.org/places/837#this"
    note: "Map 56-62"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/Gallia"
    target: "https://pleiades.stoa.org/places/993#this"
    note: "Map 14-17"
```

```yaml
# linked_past/linkages/dprr_periodo.yaml
metadata:
  source_dataset: dprr
  target_dataset: periodo
  relationship: "dcterms:temporal"
  confidence: confirmed
  method: manual_alignment
  basis: "Standard periodization of the Roman Republic"
  author: linked-past project
  date: "2026-03-30"

links:
  - source: "http://romanrepublic.ac.uk/rdf/entity/Era/Republic"
    target: "http://n2t.net/ark:/99152/p05krdxmkzt"
    note: "Roman Republic period (509-31 BC)"
  - source: "http://romanrepublic.ac.uk/rdf/entity/Era/LateRepublic"
    target: "http://n2t.net/ark:/99152/p05krdxmkzv"
    note: "Late Roman Republic (133-31 BC)"
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_linkage.py -v`
Expected: PASS (6 tests)

- [ ] **Step 6: Commit**

```bash
git add linked_past/core/linkage.py linked_past/linkages/ tests/test_linkage.py
git commit -m "feat: add linkage graph with provenance for cross-dataset references"
```

---

### Task 2: Embedding-assisted retrieval

**Files:**
- Create: `linked_past/core/embeddings.py`
- Modify: `pyproject.toml` — add `fastembed` dependency
- Test: `tests/test_embeddings.py`

- [ ] **Step 1: Add fastembed dependency**

In `pyproject.toml`, add `"fastembed"` to dependencies.

Run: `uv sync`

- [ ] **Step 2: Write the failing test**

```python
# tests/test_embeddings.py
import tempfile
from pathlib import Path

from linked_past.core.embeddings import EmbeddingIndex


def test_embedding_index_add_and_search(tmp_path):
    idx = EmbeddingIndex(tmp_path / "embeddings.db")
    idx.add("dprr", "example", "Find all consuls of the Roman Republic")
    idx.add("dprr", "example", "Find female persons in DPRR")
    idx.add("pleiades", "example", "Find all places with coordinates")
    idx.build()

    results = idx.search("Roman magistrates", k=2)
    assert len(results) == 2
    # First result should be about consuls (Roman Republic)
    assert results[0]["dataset"] == "dprr"


def test_embedding_index_search_by_dataset(tmp_path):
    idx = EmbeddingIndex(tmp_path / "embeddings.db")
    idx.add("dprr", "tip", "Boolean properties use open-world semantics")
    idx.add("pleiades", "tip", "Coordinates are on Location, not Place")
    idx.build()

    results = idx.search("location coordinates", k=5, dataset="pleiades")
    assert all(r["dataset"] == "pleiades" for r in results)


def test_embedding_index_persistence(tmp_path):
    db_path = tmp_path / "embeddings.db"

    idx1 = EmbeddingIndex(db_path)
    idx1.add("dprr", "example", "Find all consuls")
    idx1.build()

    # Re-open from same path
    idx2 = EmbeddingIndex(db_path)
    results = idx2.search("consuls", k=1)
    assert len(results) == 1


def test_embedding_index_clear_dataset(tmp_path):
    idx = EmbeddingIndex(tmp_path / "embeddings.db")
    idx.add("dprr", "example", "Find consuls")
    idx.add("pleiades", "example", "Find places")
    idx.build()

    idx.clear_dataset("dprr")
    results = idx.search("consuls", k=5)
    assert all(r["dataset"] != "dprr" for r in results)


def test_embedding_index_empty_search(tmp_path):
    idx = EmbeddingIndex(tmp_path / "embeddings.db")
    results = idx.search("anything", k=5)
    assert results == []
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_embeddings.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Write the implementation**

```python
# linked_past/core/embeddings.py
"""Embedding-assisted retrieval using fastembed + SQLite."""

from __future__ import annotations

import json
import logging
import sqlite3
import struct
from pathlib import Path

import numpy as np
from fastembed import TextEmbedding

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"


class EmbeddingIndex:
    """Manages document embeddings in SQLite for semantic search."""

    def __init__(self, db_path: Path, model_name: str = _DEFAULT_MODEL):
        self._db_path = db_path
        self._model_name = model_name
        self._model: TextEmbedding | None = None
        self._conn = sqlite3.connect(str(db_path))
        self._init_db()

    def _init_db(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dataset TEXT NOT NULL,
                doc_type TEXT NOT NULL,
                text TEXT NOT NULL,
                embedding BLOB
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        self._conn.commit()

    def _get_model(self) -> TextEmbedding:
        if self._model is None:
            self._model = TextEmbedding(model_name=self._model_name)
        return self._model

    def add(self, dataset: str, doc_type: str, text: str) -> None:
        """Add a document to the index (embedding computed on build())."""
        self._conn.execute(
            "INSERT INTO documents (dataset, doc_type, text) VALUES (?, ?, ?)",
            (dataset, doc_type, text),
        )
        self._conn.commit()

    def build(self) -> None:
        """Compute embeddings for all documents without them."""
        rows = self._conn.execute(
            "SELECT id, text FROM documents WHERE embedding IS NULL"
        ).fetchall()

        if not rows:
            return

        model = self._get_model()
        texts = [r[1] for r in rows]
        embeddings = list(model.embed(texts))

        for (row_id, _), emb in zip(rows, embeddings):
            blob = _array_to_blob(emb)
            self._conn.execute(
                "UPDATE documents SET embedding = ? WHERE id = ?",
                (blob, row_id),
            )
        self._conn.commit()
        logger.info("Built embeddings for %d documents", len(rows))

    def search(
        self, query: str, k: int = 5, dataset: str | None = None
    ) -> list[dict]:
        """Search for documents similar to query. Returns top-k results."""
        # Get all documents with embeddings
        if dataset:
            rows = self._conn.execute(
                "SELECT id, dataset, doc_type, text, embedding FROM documents "
                "WHERE embedding IS NOT NULL AND dataset = ?",
                (dataset,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT id, dataset, doc_type, text, embedding FROM documents "
                "WHERE embedding IS NOT NULL"
            ).fetchall()

        if not rows:
            return []

        model = self._get_model()
        query_emb = list(model.embed([query]))[0]

        # Brute-force cosine similarity
        scored = []
        for row_id, ds, doc_type, text, blob in rows:
            doc_emb = _blob_to_array(blob)
            score = float(np.dot(query_emb, doc_emb) / (
                np.linalg.norm(query_emb) * np.linalg.norm(doc_emb) + 1e-10
            ))
            scored.append({
                "dataset": ds,
                "doc_type": doc_type,
                "text": text,
                "score": score,
            })

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:k]

    def clear_dataset(self, dataset: str) -> None:
        """Remove all documents for a dataset."""
        self._conn.execute("DELETE FROM documents WHERE dataset = ?", (dataset,))
        self._conn.commit()

    def close(self):
        self._conn.close()


def _array_to_blob(arr: np.ndarray) -> bytes:
    """Serialize a numpy array to bytes."""
    return arr.astype(np.float32).tobytes()


def _blob_to_array(blob: bytes) -> np.ndarray:
    """Deserialize bytes to numpy array."""
    return np.frombuffer(blob, dtype=np.float32)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_embeddings.py -v`
Expected: PASS (5 tests). Note: first run downloads the model (~50MB).

- [ ] **Step 6: Commit**

```bash
git add linked_past/core/embeddings.py pyproject.toml tests/test_embeddings.py
git commit -m "feat: add embedding-assisted retrieval with fastembed + SQLite"
```

---

### Task 3: search_entities tool

**Files:**
- Modify: `linked_past/core/registry.py` — add `dataset_for_uri()` helper
- Modify: `linked_past/core/server.py` — add `search_entities` tool
- Test: `tests/test_advanced_tools.py`

- [ ] **Step 1: Add namespace-to-dataset lookup to registry**

Add to `DatasetRegistry`:

```python
    _URI_NAMESPACES: dict[str, str] = {
        "http://romanrepublic.ac.uk/rdf/": "dprr",
        "https://pleiades.stoa.org/places/": "pleiades",
        "http://n2t.net/ark:/99152/": "periodo",
        "http://nomisma.org/id/": "nomisma",
    }

    def dataset_for_uri(self, uri: str) -> str | None:
        """Determine which dataset a URI belongs to based on namespace."""
        for ns, name in self._URI_NAMESPACES.items():
            if uri.startswith(ns) and name in self._plugins:
                return name
        return None
```

- [ ] **Step 2: Write the search_entities test**

```python
# tests/test_advanced_tools.py
"""Tests for advanced MCP tools."""

from pathlib import Path

import pytest

from linked_past.core.registry import DatasetRegistry
from linked_past.core.store import create_store, execute_query
from linked_past.datasets.dprr.plugin import DPRRPlugin

DPRR_TURTLE = """\
@prefix vocab: <http://romanrepublic.ac.uk/rdf/ontology#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

<http://romanrepublic.ac.uk/rdf/entity/Person/1> a vocab:Person ;
    vocab:hasPersonName "IUNI0001 L. Iunius Brutus" ;
    vocab:hasNomen "Iunius" .

<http://romanrepublic.ac.uk/rdf/entity/Person/2> a vocab:Person ;
    vocab:hasPersonName "IUNI0002 M. Iunius Brutus" ;
    vocab:hasNomen "Iunius" .

<http://romanrepublic.ac.uk/rdf/entity/Office/3> a vocab:Office ;
    rdfs:label "Office: consul" .
"""


@pytest.fixture
def dprr_store(tmp_path):
    store_path = tmp_path / "store"
    store = create_store(store_path)
    ttl = tmp_path / "data.ttl"
    ttl.write_text(DPRR_TURTLE)
    from pyoxigraph import RdfFormat
    store.bulk_load(path=str(ttl), format=RdfFormat.TURTLE)
    return store


def test_search_entities_by_label(dprr_store):
    """search_entities finds entities matching a text query."""
    # Search for "Brutus" across labels
    sparql = """
    PREFIX vocab: <http://romanrepublic.ac.uk/rdf/ontology#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?uri ?label ?type WHERE {
        { ?uri vocab:hasPersonName ?label } UNION { ?uri rdfs:label ?label }
        FILTER(CONTAINS(LCASE(?label), "brutus"))
        OPTIONAL { ?uri a ?type }
    }
    """
    results = execute_query(dprr_store, sparql)
    assert len(results) == 2
    assert all("Brutus" in r["label"] for r in results)


def test_dataset_for_uri():
    reg = DatasetRegistry(data_dir=Path("/tmp"))
    assert reg.dataset_for_uri("http://romanrepublic.ac.uk/rdf/entity/Person/1") == "dprr"
    assert reg.dataset_for_uri("https://pleiades.stoa.org/places/423025") == "pleiades"
    assert reg.dataset_for_uri("http://nomisma.org/id/augustus") == "nomisma"
    assert reg.dataset_for_uri("http://n2t.net/ark:/99152/p05krdxmkzt") == "periodo"
    assert reg.dataset_for_uri("http://example.org/unknown") is None
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_advanced_tools.py -v`
Expected: FAIL — `dataset_for_uri` not found

- [ ] **Step 4: Add search_entities tool to server.py**

Add after the `query` tool in `server.py`:

```python
    @mcp.tool()
    def search_entities(ctx: Context, query: str, dataset: str | None = None) -> str:
        """Search entity labels across datasets. Returns matching entities with URIs, labels, types, and dataset provenance. Use for entity disambiguation."""
        app: AppContext = ctx.request_context.lifespan_context
        registry = app.registry

        datasets_to_search = [dataset] if dataset else registry.list_datasets()
        all_results = []

        for ds_name in datasets_to_search:
            try:
                store = registry.get_store(ds_name)
            except KeyError:
                continue

            plugin = registry.get_plugin(ds_name)
            prefix_block = "\n".join(f"PREFIX {k}: <{v}>" for k, v in plugin.get_prefixes().items())

            # Search common label predicates
            sparql = f"""
            {prefix_block}
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
            SELECT DISTINCT ?uri ?label ?type WHERE {{
                {{
                    ?uri rdfs:label ?label
                }} UNION {{
                    ?uri skos:prefLabel ?label
                }}
                FILTER(CONTAINS(LCASE(STR(?label)), LCASE("{query}")))
                OPTIONAL {{ ?uri a ?type }}
            }}
            LIMIT 20
            """
            try:
                from linked_past.core.store import execute_query as eq
                rows = eq(store, sparql)
                for row in rows:
                    all_results.append({
                        "dataset": ds_name,
                        "uri": row.get("uri", ""),
                        "label": row.get("label", ""),
                        "type": row.get("type", ""),
                    })
            except Exception as e:
                logger.warning("Search failed for %s: %s", ds_name, e)

        if not all_results:
            return f"No entities found matching '{query}'."

        # Group by dataset
        by_dataset: dict[str, list] = {}
        for r in all_results:
            by_dataset.setdefault(r["dataset"], []).append(r)

        lines = [f"# Search Results for '{query}'\n"]
        for ds_name, results in by_dataset.items():
            plugin = registry.get_plugin(ds_name)
            lines.append(f"## {plugin.display_name}\n")
            for r in results[:10]:
                type_str = f" ({r['type'].rsplit('/', 1)[-1].rsplit('#', 1)[-1]})" if r["type"] else ""
                lines.append(f"- **{r['label']}**{type_str}\n  `{r['uri']}`")
            if len(results) > 10:
                lines.append(f"  ... and {len(results) - 10} more")
            lines.append("")

        return "\n".join(lines)
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/test_advanced_tools.py -v && uv run pytest -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add linked_past/core/registry.py linked_past/core/server.py tests/test_advanced_tools.py
git commit -m "feat: add search_entities tool and dataset_for_uri lookup"
```

---

### Task 4: explore_entity and find_links tools

**Files:**
- Modify: `linked_past/core/server.py` — add `explore_entity` and `find_links` tools
- Modify: `tests/test_advanced_tools.py` — add tests

- [ ] **Step 1: Add tests**

Append to `tests/test_advanced_tools.py`:

```python
def test_explore_entity_query(dprr_store):
    """explore_entity retrieves key properties of an entity."""
    sparql = """
    PREFIX vocab: <http://romanrepublic.ac.uk/rdf/ontology#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?pred ?obj WHERE {
        <http://romanrepublic.ac.uk/rdf/entity/Person/1> ?pred ?obj .
    }
    """
    results = execute_query(dprr_store, sparql)
    assert len(results) > 0
    preds = {r["pred"] for r in results}
    assert "http://romanrepublic.ac.uk/rdf/ontology#hasPersonName" in preds
```

- [ ] **Step 2: Add explore_entity tool to server.py**

```python
    @mcp.tool()
    def explore_entity(ctx: Context, uri: str) -> str:
        """Explore an entity across datasets. Returns properties from its home dataset, cross-links from the linkage graph, and suggested next steps."""
        app: AppContext = ctx.request_context.lifespan_context
        registry = app.registry

        # Determine home dataset
        ds_name = registry.dataset_for_uri(uri)
        lines = [f"# Entity: `{uri}`\n"]

        if ds_name:
            plugin = registry.get_plugin(ds_name)
            lines.append(f"**Dataset:** {plugin.display_name}\n")

            try:
                store = registry.get_store(ds_name)
                sparql = f"""
                SELECT ?pred ?obj WHERE {{
                    <{uri}> ?pred ?obj .
                }} LIMIT 50
                """
                from linked_past.core.store import execute_query as eq
                rows = eq(store, sparql)
                if rows:
                    lines.append("## Properties\n")
                    for row in rows:
                        pred = row["pred"].rsplit("/", 1)[-1].rsplit("#", 1)[-1]
                        obj = row["obj"] or ""
                        if len(obj) > 100:
                            obj = obj[:100] + "..."
                        lines.append(f"- **{pred}:** {obj}")
                    lines.append("")
            except Exception as e:
                lines.append(f"Error querying {ds_name}: {e}\n")
        else:
            lines.append("**Dataset:** Unknown (URI namespace not recognized)\n")

        # Cross-links from linkage graph
        if app.linkage:
            links = app.linkage.find_links(uri)
            if links:
                lines.append("## Cross-Dataset Links\n")
                for link in links:
                    lines.append(
                        f"- **{link['relationship']}** → `{link['target']}`\n"
                        f"  Confidence: {link['confidence']} | {link['basis']}"
                    )
                lines.append("")

        # Suggest next steps
        lines.append("## Suggested Next Steps\n")
        if ds_name == "dprr":
            lines.append("- Query DPRR for office-holdings: `query(sparql, 'dprr')` with PostAssertion joins")
            lines.append("- Check family relationships via RelationshipAssertion")
        elif ds_name == "pleiades":
            lines.append("- Get coordinates via `pleiades:hasLocation`")
            lines.append("- Find ancient names via `pleiades:hasName`")
        lines.append(f"- Search for related entities: `search_entities('{uri.rsplit('/', 1)[-1]}')`")
        lines.append(f"- Find cross-dataset links: `find_links('{uri}')`")

        return "\n".join(lines)
```

- [ ] **Step 3: Add find_links tool to server.py**

```python
    @mcp.tool()
    def find_links(ctx: Context, uri: str) -> str:
        """Find all cross-dataset links for an entity from the linkage graph. Each link includes target URI, relationship type, confidence level, and scholarly basis."""
        app: AppContext = ctx.request_context.lifespan_context

        if not app.linkage:
            return "Linkage graph not initialized."

        links = app.linkage.find_links(uri)
        if not links:
            # Suggest datasets that might have relevant entities
            ds_name = app.registry.dataset_for_uri(uri)
            other_datasets = [n for n in app.registry.list_datasets() if n != ds_name]
            return (
                f"No confirmed links found for `{uri}`.\n\n"
                f"Try searching other datasets: {', '.join(other_datasets)}\n"
                f"Use `search_entities()` to find potential matches."
            )

        # Group by confidence
        by_confidence: dict[str, list] = {}
        for link in links:
            by_confidence.setdefault(link["confidence"], []).append(link)

        lines = [f"# Links for `{uri}`\n"]
        for level in ["confirmed", "probable", "candidate"]:
            group = by_confidence.get(level, [])
            if group:
                lines.append(f"## {level.title()} ({len(group)})\n")
                for link in group:
                    lines.append(
                        f"- **{link['relationship']}** → `{link['target']}`\n"
                        f"  Basis: {link['basis']}"
                    )
                lines.append("")

        return "\n".join(lines)
```

- [ ] **Step 4: Update AppContext to include linkage**

In `server.py`, update `AppContext`:

```python
@dataclass
class AppContext:
    registry: DatasetRegistry
    linkage: LinkageGraph | None = None
```

Update `build_app_context` to load linkage graph:

```python
def build_app_context() -> AppContext:
    data_dir = get_data_dir()
    registry = DatasetRegistry(data_dir=data_dir)
    registry.register(DPRRPlugin())
    registry.register(PleiadesPlugin())
    registry.register(PeriodOPlugin())
    registry.register(NomismaPlugin())
    registry.initialize_all()

    # Load linkage graph
    from linked_past.core.linkage import LinkageGraph
    linkage_store_path = data_dir / "_linkages" / "store"
    linkage = LinkageGraph(linkage_store_path)
    linkages_dir = Path(__file__).parent.parent / "linkages"
    if linkages_dir.exists():
        for yaml_file in sorted(linkages_dir.glob("*.yaml")):
            linkage.load_yaml(yaml_file)

    return AppContext(registry=registry, linkage=linkage)
```

Add import at top of server.py:
```python
from linked_past.core.linkage import LinkageGraph
```

- [ ] **Step 5: Run all tests**

Run: `uv run pytest -v && uv run ruff check .`

- [ ] **Step 6: Commit**

```bash
git add linked_past/core/server.py tests/test_advanced_tools.py
git commit -m "feat: add explore_entity and find_links tools with linkage graph integration"
```

---

### Task 5: get_provenance tool

**Files:**
- Modify: `linked_past/core/server.py` — add `get_provenance` tool

- [ ] **Step 1: Add get_provenance tool**

```python
    @mcp.tool()
    def get_provenance(ctx: Context, uri: str, predicate: str | None = None) -> str:
        """Get full provenance for an entity or a specific claim. Returns source → factoid → dataset chain plus linkage basis for cross-references."""
        app: AppContext = ctx.request_context.lifespan_context
        registry = app.registry

        ds_name = registry.dataset_for_uri(uri)
        lines = [f"# Provenance for `{uri}`\n"]

        if ds_name:
            plugin = registry.get_plugin(ds_name)
            store = registry.get_store(ds_name)
            meta = registry.get_metadata(ds_name)

            lines.append(f"## Dataset: {plugin.display_name}\n")
            lines.append(f"- **Version:** {meta.get('version', 'unknown')}")
            lines.append(f"- **License:** {plugin.license}")
            lines.append(f"- **Citation:** {plugin.citation}")
            lines.append(f"- **URL:** {plugin.url}\n")

            # Get properties (optionally filtered by predicate)
            if predicate:
                sparql = f"""
                SELECT ?obj WHERE {{
                    <{uri}> <{predicate}> ?obj .
                }}
                """
            else:
                sparql = f"""
                SELECT ?pred ?obj WHERE {{
                    <{uri}> ?pred ?obj .
                }} LIMIT 50
                """
            try:
                from linked_past.core.store import execute_query as eq
                rows = eq(store, sparql)
                if rows:
                    lines.append("## Assertions\n")
                    for row in rows:
                        if predicate:
                            lines.append(f"- {row['obj']}")
                        else:
                            pred_short = row["pred"].rsplit("/", 1)[-1].rsplit("#", 1)[-1]
                            lines.append(f"- **{pred_short}:** {row['obj'] or ''}")
                    lines.append("")
            except Exception as e:
                lines.append(f"Error: {e}\n")

            # Check for secondary sources (DPRR-specific)
            if ds_name == "dprr":
                source_sparql = f"""
                PREFIX vocab: <http://romanrepublic.ac.uk/rdf/ontology#>
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                SELECT ?assertion ?source ?sourceLabel WHERE {{
                    ?assertion vocab:isAboutPerson <{uri}> ;
                              vocab:hasSecondarySource ?source .
                    ?source rdfs:label ?sourceLabel .
                }}
                """
                try:
                    rows = eq(store, source_sparql)
                    if rows:
                        lines.append("## Secondary Sources\n")
                        seen = set()
                        for row in rows:
                            label = row.get("sourceLabel", "")
                            if label and label not in seen:
                                lines.append(f"- {label}")
                                seen.add(label)
                        lines.append("")
                except Exception:
                    pass

        # Cross-reference provenance
        if app.linkage:
            links = app.linkage.find_links(uri)
            if links:
                lines.append("## Cross-Reference Provenance\n")
                for link in links:
                    prov = app.linkage.get_provenance(uri, link["target"])
                    if prov:
                        lines.append(
                            f"- **{link['relationship']}** → `{link['target']}`\n"
                            f"  Basis: {prov.get('basis', 'unknown')}\n"
                            f"  Confidence: {prov.get('confidence', 'unknown')}\n"
                            f"  Method: {prov.get('method', 'unknown')}\n"
                            f"  Attributed to: {prov.get('author', 'unknown')}"
                        )
                lines.append("")

        return "\n".join(lines)
```

- [ ] **Step 2: Run tests and lint**

Run: `uv run pytest -v && uv run ruff check .`

- [ ] **Step 3: Commit**

```bash
git add linked_past/core/server.py
git commit -m "feat: add get_provenance tool for scholarly citation drill-down"
```

---

### Task 6: update_dataset tool

**Files:**
- Modify: `linked_past/core/server.py` — add `update_dataset` tool

- [ ] **Step 1: Add update_dataset tool**

```python
    @mcp.tool()
    def update_dataset(ctx: Context, dataset: str | None = None) -> str:
        """Check for available updates to dataset(s). Reports current version and whether newer data exists."""
        app: AppContext = ctx.request_context.lifespan_context
        registry = app.registry

        datasets_to_check = [dataset] if dataset else registry.list_datasets()
        lines = ["# Dataset Update Status\n"]

        for ds_name in datasets_to_check:
            try:
                plugin = registry.get_plugin(ds_name)
            except KeyError:
                lines.append(f"## {ds_name}\n- **Error:** Unknown dataset\n")
                continue

            meta = registry.get_metadata(ds_name)
            version = meta.get("version", "unknown")
            triple_count = meta.get("triple_count", "unknown")

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

        return "\n".join(lines)
```

- [ ] **Step 2: Update server instructions**

Update the `instructions` string in `create_mcp_server()`:

```python
        instructions=(
            "Linked Past: multi-dataset prosopographical SPARQL tools. "
            "Use discover_datasets to find datasets, get_schema to learn ontologies, "
            "validate_sparql to check queries, query to execute them, "
            "search_entities to find entities across datasets, "
            "explore_entity to inspect an entity, find_links for cross-references, "
            "get_provenance for scholarly citations, and update_dataset to check freshness."
        ),
```

- [ ] **Step 3: Run all tests and lint**

Run: `uv run pytest -v && uv run ruff check .`

- [ ] **Step 4: Commit**

```bash
git add linked_past/core/server.py
git commit -m "feat: add update_dataset tool and update server instructions"
```

---

### Task 7: Wire embeddings into the server

**Files:**
- Modify: `linked_past/core/server.py` — add embedding index to AppContext, use for discover_datasets

- [ ] **Step 1: Update AppContext and build_app_context**

```python
@dataclass
class AppContext:
    registry: DatasetRegistry
    linkage: LinkageGraph | None = None
    embeddings: EmbeddingIndex | None = None
```

Add import:
```python
from linked_past.core.embeddings import EmbeddingIndex
```

In `build_app_context`, after linkage graph loading, add:

```python
    # Build embedding index
    embeddings_path = data_dir / "embeddings.db"
    embeddings = EmbeddingIndex(embeddings_path)

    # Index all plugin context
    for name in registry.list_datasets():
        plugin = registry.get_plugin(name)
        # Index dataset description
        embeddings.add(name, "dataset", f"{plugin.display_name}: {plugin.description}")

        # Index context files
        context_dir = Path(plugin.__class__.__module__).parent / "context" if hasattr(plugin, '_schemas') else None
        if hasattr(plugin, '_examples'):
            for ex in plugin._examples:
                embeddings.add(name, "example", f"{ex['question']}\n{ex['sparql']}")
        if hasattr(plugin, '_tips'):
            for tip in plugin._tips:
                embeddings.add(name, "tip", f"{tip['title']}: {tip['body']}")
        if hasattr(plugin, '_schemas'):
            for cls_name, cls_data in plugin._schemas.items():
                embeddings.add(name, "schema", f"{cls_name}: {cls_data.get('comment', '')}")

    embeddings.build()

    return AppContext(registry=registry, linkage=linkage, embeddings=embeddings)
```

- [ ] **Step 2: Enhance discover_datasets with embeddings**

Replace the topic filtering in `discover_datasets` with embedding search when available:

```python
    @mcp.tool()
    def discover_datasets(ctx: Context, topic: str | None = None) -> str:
        """Discover available datasets. Without arguments, lists all loaded datasets with metadata. With a topic, uses semantic search to find relevant datasets."""
        app: AppContext = ctx.request_context.lifespan_context
        registry = app.registry

        if topic and app.embeddings:
            # Use embeddings for semantic search
            results = app.embeddings.search(topic, k=10)
            relevant_datasets = set()
            for r in results:
                relevant_datasets.add(r["dataset"])
        else:
            relevant_datasets = None  # Show all

        lines = ["# Available Datasets\n"]
        for name in registry.list_datasets():
            if relevant_datasets is not None and name not in relevant_datasets:
                continue
            plugin = registry.get_plugin(name)
            if topic and relevant_datasets is None:
                # Fallback: text matching
                searchable = [plugin.description, plugin.display_name,
                              plugin.spatial_coverage, plugin.time_coverage]
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
```

- [ ] **Step 3: Run all tests**

Run: `uv run pytest -v && uv run ruff check .`

- [ ] **Step 4: Commit**

```bash
git add linked_past/core/server.py
git commit -m "feat: wire embedding index into server for semantic dataset discovery"
```

---

### Task 8: Final verification

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest -v`
Expected: All tests pass

- [ ] **Step 2: Run lint**

Run: `uv run ruff check .`
Expected: Clean

- [ ] **Step 3: Verify server starts**

Run: `LINKED_PAST_DATA_DIR=/tmp/lp-test uv run linked-past-server --help`
Expected: Shows help

- [ ] **Step 4: Verify all 9 tools are registered**

```python
python -c "
from linked_past.core.server import create_mcp_server
mcp = create_mcp_server()
tools = [t.name for t in mcp._tool_manager.list_tools()]
print(sorted(tools))
assert len(tools) == 9, f'Expected 9 tools, got {len(tools)}: {tools}'
print('All 9 tools registered!')
"
```

- [ ] **Step 5: Commit any fixes**

```bash
git add -A && git commit -m "fix: address issues found in final verification"
```
