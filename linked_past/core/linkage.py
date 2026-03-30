"""Oxigraph-based linkage graph for cross-dataset references with PROV-O provenance."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import yaml
from pyoxigraph import Literal, NamedNode, Quad, Store

_LINKPAST = "http://linked-past.org/ontology#"
_PROV = "http://www.w3.org/ns/prov#"
_DCTERMS = "http://purl.org/dc/terms/"

_RELATIONSHIP_MAP = {
    "owl:sameAs": "http://www.w3.org/2002/07/owl#sameAs",
    "skos:exactMatch": "http://www.w3.org/2004/02/skos/core#exactMatch",
    "skos:closeMatch": "http://www.w3.org/2004/02/skos/core#closeMatch",
    "dcterms:spatial": "http://purl.org/dc/terms/spatial",
    "dcterms:temporal": "http://purl.org/dc/terms/temporal",
}

_PROV_GRAPH = NamedNode(f"{_LINKPAST}provenance")


class LinkageGraph:
    """Manages cross-dataset linkages with provenance metadata in an Oxigraph store."""

    def __init__(self, store_path: str | Path | None = None) -> None:
        if store_path is None:
            self._store = Store()
        else:
            path = Path(store_path)
            path.mkdir(parents=True, exist_ok=True)
            self._store = Store(str(path))

    def load_yaml(self, yaml_path: str | Path) -> None:
        """Parse a linkage YAML file and add triples with provenance."""
        path = Path(yaml_path)
        with path.open() as f:
            data = yaml.safe_load(f)
        self._load_data(data)

    def load_data(self, data: dict[str, Any]) -> None:
        """Load linkage data from an already-parsed dict (useful for testing)."""
        self._load_data(data)

    def load_turtle(self, ttl_path: str | Path) -> int:
        """Load Turtle concordance triples directly into the store. Returns triple count added."""
        from pyoxigraph import RdfFormat

        before = len(self._store)
        path = Path(ttl_path)
        self._store.bulk_load(path=str(path), format=RdfFormat.TURTLE)
        added = len(self._store) - before
        return added

    def _load_data(self, data: dict[str, Any]) -> None:
        metadata = data["metadata"]
        relationship_key = metadata["relationship"]
        relationship_uri = _RELATIONSHIP_MAP.get(relationship_key)
        if relationship_uri is None:
            raise ValueError(f"Unknown relationship: {relationship_key}")

        predicate = NamedNode(relationship_uri)

        for link in data["links"]:
            source = NamedNode(link["source"])
            target = NamedNode(link["target"])
            graph_id = NamedNode(f"{_LINKPAST}link/{uuid.uuid4()}")

            # The link triple in its own named graph
            self._store.add(Quad(source, predicate, target, graph_id))

            # Provenance triples in the provenance graph
            self._store.add(Quad(
                graph_id,
                NamedNode(f"{_PROV}wasAttributedTo"),
                Literal(metadata.get("author", "")),
                _PROV_GRAPH,
            ))
            self._store.add(Quad(
                graph_id,
                NamedNode(f"{_DCTERMS}source"),
                Literal(metadata.get("basis", "")),
                _PROV_GRAPH,
            ))
            confidence = link.get("confidence", metadata.get("confidence", "candidate"))
            self._store.add(Quad(
                graph_id,
                NamedNode(f"{_LINKPAST}confidence"),
                Literal(confidence),
                _PROV_GRAPH,
            ))
            self._store.add(Quad(
                graph_id,
                NamedNode(f"{_LINKPAST}method"),
                Literal(metadata.get("method", "")),
                _PROV_GRAPH,
            ))
            if link.get("note"):
                self._store.add(Quad(
                    graph_id,
                    NamedNode(f"{_LINKPAST}note"),
                    Literal(link["note"]),
                    _PROV_GRAPH,
                ))
            # Store source/target URIs in provenance for easy lookup
            self._store.add(Quad(
                graph_id,
                NamedNode(f"{_LINKPAST}sourceEntity"),
                source,
                _PROV_GRAPH,
            ))
            self._store.add(Quad(
                graph_id,
                NamedNode(f"{_LINKPAST}targetEntity"),
                target,
                _PROV_GRAPH,
            ))

    def find_links(self, uri: str) -> list[dict[str, str]]:
        """Find forward and reverse links for a URI."""
        query = f"""
        SELECT ?target ?relationship ?confidence ?basis ?direction ?graph WHERE {{
            {{
                GRAPH ?graph {{ <{uri}> ?relationship ?target }}
                GRAPH <{_LINKPAST}provenance> {{
                    ?graph <{_LINKPAST}confidence> ?confidence .
                    ?graph <{_DCTERMS}source> ?basis .
                }}
                BIND("forward" AS ?direction)
            }}
            UNION
            {{
                GRAPH ?graph {{ ?target ?relationship <{uri}> }}
                GRAPH <{_LINKPAST}provenance> {{
                    ?graph <{_LINKPAST}confidence> ?confidence .
                    ?graph <{_DCTERMS}source> ?basis .
                }}
                BIND("reverse" AS ?direction)
            }}
        }}
        """
        results = self._store.query(query)
        variables = [v.value for v in results.variables]
        rows = []
        for solution in results:
            row = {}
            for var_name in variables:
                value = solution[var_name]
                row[var_name] = value.value if value is not None else None
            rows.append(row)
        return rows

    def get_provenance(self, source_uri: str, target_uri: str) -> dict[str, str] | None:
        """Return provenance metadata for a specific source->target link."""
        query = f"""
        SELECT ?author ?basis ?confidence ?method ?note WHERE {{
            GRAPH <{_LINKPAST}provenance> {{
                ?graph <{_LINKPAST}sourceEntity> <{source_uri}> .
                ?graph <{_LINKPAST}targetEntity> <{target_uri}> .
                ?graph <{_PROV}wasAttributedTo> ?author .
                ?graph <{_DCTERMS}source> ?basis .
                ?graph <{_LINKPAST}confidence> ?confidence .
                ?graph <{_LINKPAST}method> ?method .
                OPTIONAL {{ ?graph <{_LINKPAST}note> ?note }}
            }}
        }}
        """
        results = self._store.query(query)
        variables = [v.value for v in results.variables]
        for solution in results:
            row = {}
            for var_name in variables:
                value = solution[var_name]
                row[var_name] = value.value if value is not None else None
            return row
        return None

    def triple_count(self) -> int:
        """Return the total number of quads in the store."""
        return len(self._store)
