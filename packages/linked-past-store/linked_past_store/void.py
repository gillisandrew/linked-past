"""VoID (Vocabulary of Interlinked Datasets) description generation."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from pyoxigraph import Store

from linked_past_store.verify import detect_format

logger = logging.getLogger(__name__)

_DATASET_BASE = "https://gillisandrew.github.io/linked-past/datasets/"

_VOID_PREFIXES = """\
@prefix void: <http://rdfs.org/ns/void#> .
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix foaf: <http://xmlns.com/foaf/0.1/> .
"""


def _longest_common_prefix(uris: list[str]) -> str:
    """Compute longest common prefix of a list of URI strings."""
    if not uris:
        return ""
    shortest = min(uris, key=len)
    for i, char in enumerate(shortest):
        for uri in uris:
            if uri[i] != char:
                return shortest[:i]
    return shortest


@dataclass
class ClassPartition:
    """A VoID class partition: a class URI with its instance count."""

    class_uri: str
    entities: int = 0


@dataclass
class PropertyPartition:
    """A VoID property partition: a predicate URI with its triple count."""

    property_uri: str
    triples: int = 0
    distinct_subjects: int = 0
    distinct_objects: int = 0


@dataclass
class VoidDescription:
    """VoID description of an RDF dataset."""

    dataset_id: str
    title: str
    triples: int = 0
    entities: int = 0
    classes: int = 0
    properties: int = 0
    distinct_subjects: int = 0
    distinct_objects: int = 0
    uri_space: str = ""
    example_resource: str = ""
    license_uri: str = ""
    source_uri: str = ""
    citation: str = ""
    publisher: str = ""
    description: str = ""
    class_partitions: list[ClassPartition] = field(default_factory=list)
    property_partitions: list[PropertyPartition] = field(default_factory=list)
    linksets: list[dict] = field(default_factory=list)

    def to_turtle(self) -> str:
        """Produce valid VoID Turtle for this description."""
        # Expand bare IDs to full URIs under the linked-past namespace
        uri = self.dataset_id if "://" in self.dataset_id else f"{_DATASET_BASE}{self.dataset_id}"
        lines: list[str] = [_VOID_PREFIXES, f"<{uri}> a void:Dataset"]

        def _prop(pred: str, value: str, is_literal: bool = False) -> None:
            if value:
                if is_literal:
                    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
                    lines.append(f'    {pred} "{escaped}"')
                else:
                    lines.append(f"    {pred} <{value}>")

        _prop("dcterms:title", self.title, is_literal=True)
        if self.description:
            _prop("dcterms:description", self.description, is_literal=True)
        if self.triples:
            lines.append(f"    void:triples {self.triples}")
        if self.entities:
            lines.append(f"    void:entities {self.entities}")
        if self.classes:
            lines.append(f"    void:classes {self.classes}")
        if self.properties:
            lines.append(f"    void:properties {self.properties}")
        if self.distinct_subjects:
            lines.append(f"    void:distinctSubjects {self.distinct_subjects}")
        if self.distinct_objects:
            lines.append(f"    void:distinctObjects {self.distinct_objects}")
        if self.uri_space:
            escaped_space = self.uri_space.replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'    void:uriSpace "{escaped_space}"')
        if self.example_resource:
            lines.append(f"    void:exampleResource <{self.example_resource}>")
        _prop("dcterms:license", self.license_uri)
        _prop("dcterms:source", self.source_uri)
        if self.citation:
            escaped_cite = self.citation.replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'    dcterms:bibliographicCitation "{escaped_cite}"')
        if self.publisher:
            escaped_pub = self.publisher.replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'    dcterms:publisher [ a foaf:Agent ; foaf:name "{escaped_pub}" ]')

        # Class partitions
        for cp in self.class_partitions:
            lines.append(
                f"    void:classPartition [ void:class <{cp.class_uri}> ; void:entities {cp.entities} ]"
            )

        # Property partitions
        for pp in self.property_partitions:
            pp_parts = [f"void:property <{pp.property_uri}>"]
            if pp.triples:
                pp_parts.append(f"void:triples {pp.triples}")
            if pp.distinct_subjects:
                pp_parts.append(f"void:distinctSubjects {pp.distinct_subjects}")
            if pp.distinct_objects:
                pp_parts.append(f"void:distinctObjects {pp.distinct_objects}")
            lines.append(f"    void:propertyPartition [ {' ; '.join(pp_parts)} ]")

        # Linksets
        for ls in self.linksets:
            target = ls.get("target", "")
            link_pred = ls.get("predicate", "")
            count = ls.get("triples", 0)
            if target:
                subset_lines = ["    void:subset ["]
                subset_lines.append("        a void:Linkset")
                subset_lines.append(f"        ; void:target <{target}>")
                if link_pred:
                    subset_lines.append(f"        ; void:linkPredicate <{link_pred}>")
                if count:
                    subset_lines.append(f"        ; void:triples {count}")
                subset_lines.append("    ]")
                lines.append("\n".join(subset_lines))

        # lines[0] = prefix block, lines[1] = subject declaration, lines[2:] = properties
        prefix_block = lines[0]
        subject = lines[1]
        props = lines[2:]

        if not props:
            return prefix_block + subject + " .\n"

        turtle = prefix_block + subject + " ;\n"
        for i, prop_line in enumerate(props):
            if i < len(props) - 1:
                turtle += prop_line + " ;\n"
            else:
                turtle += prop_line + " .\n"
        return turtle


def generate_void(
    data_path: Path | str,
    dataset_id: str,
    title: str,
    license_uri: str = "",
    source_uri: str = "",
    citation: str = "",
    publisher: str = "",
    description: str = "",
    output_path: Path | str | None = None,
) -> VoidDescription:
    """Generate a VoID description for an RDF dataset file.

    Loads the data, computes statistics, and optionally writes Turtle to a file.
    """
    data_path = Path(data_path)
    fmt = detect_format(data_path)
    store = Store()
    store.bulk_load(path=str(data_path), format=fmt)

    triple_count = len(store)

    # Count distinct typed subjects (entities)
    entity_results = store.query(
        "SELECT DISTINCT ?s WHERE { ?s a ?class . FILTER(isIRI(?s)) }"
    )
    typed_subjects: list[str] = []
    for row in entity_results:
        node = row[0]  # type: ignore[index]
        s = str(node)
        if s.startswith("<") and s.endswith(">"):
            typed_subjects.append(s[1:-1])

    entity_count = len(typed_subjects)

    # Count distinct classes
    class_results = store.query("SELECT DISTINCT ?c WHERE { ?s a ?c . FILTER(isIRI(?c)) }")
    class_count = sum(1 for _ in class_results)

    # Count distinct predicates
    pred_results = store.query("SELECT DISTINCT ?p WHERE { ?s ?p ?o . }")
    prop_count = sum(1 for _ in pred_results)

    # Distinct subjects and objects (borrowed from void-generator)
    ds_results = store.query("SELECT (COUNT(DISTINCT ?s) AS ?n) WHERE { ?s ?p ?o }")
    distinct_subjects = int(next(iter(ds_results))[0].value)

    do_results = store.query("SELECT (COUNT(DISTINCT ?o) AS ?n) WHERE { ?s ?p ?o }")
    distinct_objects = int(next(iter(do_results))[0].value)

    # Class partitions: instance count per class
    cp_results = store.query(
        "SELECT ?c (COUNT(DISTINCT ?s) AS ?n) WHERE { ?s a ?c . FILTER(isIRI(?c)) } "
        "GROUP BY ?c ORDER BY DESC(?n)"
    )
    class_partitions = []
    for row in cp_results:
        uri = str(row[0])
        if uri.startswith("<") and uri.endswith(">"):
            uri = uri[1:-1]
        class_partitions.append(ClassPartition(class_uri=uri, entities=int(row[1].value)))

    # Property partitions: triple count, distinct subjects/objects per predicate
    pp_results = store.query(
        "SELECT ?p (COUNT(*) AS ?triples) (COUNT(DISTINCT ?s) AS ?ds) (COUNT(DISTINCT ?o) AS ?do) "
        "WHERE { ?s ?p ?o } GROUP BY ?p ORDER BY DESC(?triples)"
    )
    property_partitions = []
    for row in pp_results:
        uri = str(row[0])
        if uri.startswith("<") and uri.endswith(">"):
            uri = uri[1:-1]
        property_partitions.append(PropertyPartition(
            property_uri=uri,
            triples=int(row[1].value),
            distinct_subjects=int(row[2].value),
            distinct_objects=int(row[3].value),
        ))

    # Compute URI space from typed subjects
    uri_space = _longest_common_prefix(typed_subjects) if typed_subjects else ""

    # Pick an example resource
    example_resource = typed_subjects[0] if typed_subjects else ""

    void_desc = VoidDescription(
        dataset_id=dataset_id,
        title=title,
        triples=triple_count,
        entities=entity_count,
        classes=class_count,
        properties=prop_count,
        distinct_subjects=distinct_subjects,
        distinct_objects=distinct_objects,
        uri_space=uri_space,
        example_resource=example_resource,
        class_partitions=class_partitions,
        property_partitions=property_partitions,
        license_uri=license_uri,
        source_uri=source_uri,
        citation=citation,
        publisher=publisher,
        description=description,
    )

    if output_path is not None:
        out = Path(output_path)
        out.write_text(void_desc.to_turtle())
        logger.info("Wrote VoID description to %s", out)

    return void_desc
