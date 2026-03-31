"""VoID (Vocabulary of Interlinked Datasets) description generation."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from pyoxigraph import Store

from linked_past_store.verify import detect_format

logger = logging.getLogger(__name__)

_RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"

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
class VoidDescription:
    """VoID description of an RDF dataset."""

    dataset_id: str
    title: str
    triples: int = 0
    entities: int = 0
    classes: int = 0
    properties: int = 0
    uri_space: str = ""
    example_resource: str = ""
    license_uri: str = ""
    source_uri: str = ""
    citation: str = ""
    publisher: str = ""
    description: str = ""
    linksets: list[dict] = field(default_factory=list)

    def to_turtle(self) -> str:
        """Produce valid VoID Turtle for this description."""
        lines: list[str] = [_VOID_PREFIXES, f"<{self.dataset_id}> a void:Dataset"]

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

        # Join with " ;\n" separator and close with " ."
        # First line is the subject declaration, rest are property lines
        subject_line = lines[len(_VOID_PREFIXES.splitlines()) + 1]  # noqa: F841
        prefix_block = _VOID_PREFIXES
        prop_lines = lines[len(_VOID_PREFIXES.splitlines()) + 1:]

        if len(prop_lines) == 1:
            # Just the type declaration, no properties
            return prefix_block + prop_lines[0] + " .\n"

        turtle = prefix_block + prop_lines[0] + " ;\n"
        for i, prop_line in enumerate(prop_lines[1:], 1):
            if i < len(prop_lines) - 1:
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
        uri_space=uri_space,
        example_resource=example_resource,
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
