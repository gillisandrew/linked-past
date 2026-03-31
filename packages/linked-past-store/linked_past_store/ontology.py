"""Ontology-aware schema extraction for RDF datasets."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from pyoxigraph import NamedNode, Store

from linked_past_store.verify import detect_format

logger = logging.getLogger(__name__)

# Well-known ontology URIs
_RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
_RDFS_LABEL = "http://www.w3.org/2000/01/rdf-schema#label"
_RDFS_COMMENT = "http://www.w3.org/2000/01/rdf-schema#comment"
_RDFS_SUBCLASS_OF = "http://www.w3.org/2000/01/rdf-schema#subClassOf"
_RDFS_DOMAIN = "http://www.w3.org/2000/01/rdf-schema#domain"
_RDFS_RANGE = "http://www.w3.org/2000/01/rdf-schema#range"
_OWL_CLASS = "http://www.w3.org/2002/07/owl#Class"
_RDFS_CLASS = "http://www.w3.org/2000/01/rdf-schema#Class"
_OWL_DATATYPE_PROPERTY = "http://www.w3.org/2002/07/owl#DatatypeProperty"
_OWL_OBJECT_PROPERTY = "http://www.w3.org/2002/07/owl#ObjectProperty"
_RDF_PROPERTY = "http://www.w3.org/1999/02/22-rdf-syntax-ns#Property"


def _uri(node: Any) -> str:
    """Extract URI string from a NamedNode (strips angle brackets)."""
    s = str(node)
    if s.startswith("<") and s.endswith(">"):
        return s[1:-1]
    return s


def _literal_value(node: Any) -> str:
    """Extract string value from a Literal node."""
    try:
        return node.value
    except AttributeError:
        return str(node)


def _shorten(uri: str, prefix_map: dict[str, str]) -> str:
    """Shorten a URI using the prefix map (longest prefix wins)."""
    best_prefix = ""
    best_ns = ""
    for ns, prefix in prefix_map.items():
        if uri.startswith(ns) and len(ns) > len(best_ns):
            best_ns = ns
            best_prefix = prefix
    if best_ns:
        return best_prefix + uri[len(best_ns):]
    return uri


@dataclass
class PropertyInfo:
    """Information about an RDF property."""

    predicate: str
    range: str = ""
    comment: str = ""


@dataclass
class ClassInfo:
    """Information about an RDF class."""

    uri: str
    label: str = ""
    comment: str = ""
    parent: str = ""
    properties: list[PropertyInfo] = field(default_factory=list)


@dataclass
class Schema:
    """Extracted schema with classes and their properties."""

    classes: dict[str, ClassInfo] = field(default_factory=dict)

    def to_schemas_yaml(self, prefix_map: dict[str, str] | None = None) -> dict[str, Any]:
        """Convert to schemas.yaml compatible dict with optional URI shortening."""
        pm = prefix_map or {}
        result: dict[str, Any] = {}
        for uri, cls in self.classes.items():
            short_uri = _shorten(uri, pm)
            entry: dict[str, Any] = {}
            if cls.comment:
                entry["comment"] = cls.comment
            if cls.parent:
                entry["parent"] = _shorten(cls.parent, pm)
            props: dict[str, Any] = {}
            for prop in cls.properties:
                short_pred = _shorten(prop.predicate, pm)
                prop_entry: dict[str, Any] = {}
                if prop.range:
                    prop_entry["range"] = _shorten(prop.range, pm)
                if prop.comment:
                    prop_entry["comment"] = prop.comment
                props[short_pred] = prop_entry
            if props:
                entry["properties"] = props
            result[short_uri] = entry
        return result


def _load_store(path: Path) -> Store:
    """Load an RDF file into an in-memory Oxigraph store."""
    fmt = detect_format(path)
    store = Store()
    store.bulk_load(path=str(path), format=fmt)
    return store


def _get_literal(store: Store, subject_uri: str, predicate_uri: str) -> str:
    """Get first literal value for subject/predicate pair."""
    for quad in store.quads_for_pattern(
        NamedNode(subject_uri), NamedNode(predicate_uri), None, None
    ):
        obj = quad.object
        try:
            return obj.value
        except AttributeError:
            pass
    return ""


def _get_named_node(store: Store, subject_uri: str, predicate_uri: str) -> str:
    """Get first named node URI for subject/predicate pair."""
    for quad in store.quads_for_pattern(
        NamedNode(subject_uri), NamedNode(predicate_uri), None, None
    ):
        obj = quad.object
        obj_str = str(obj)
        if obj_str.startswith("<") and obj_str.endswith(">"):
            return obj_str[1:-1]
    return ""


def extract_from_ontology(path: Path | str) -> Schema:
    """Parse OWL/RDFS ontology file to extract class and property schema."""
    path = Path(path)
    store = _load_store(path)
    schema = Schema()

    # Find all classes (owl:Class and rdfs:Class)
    class_uris: set[str] = set()
    for class_type in (_OWL_CLASS, _RDFS_CLASS):
        for quad in store.quads_for_pattern(None, NamedNode(_RDF_TYPE), NamedNode(class_type), None):
            subj = quad.subject
            subj_str = str(subj)
            if subj_str.startswith("<") and subj_str.endswith(">"):
                class_uris.add(subj_str[1:-1])

    for uri in class_uris:
        label = _get_literal(store, uri, _RDFS_LABEL)
        comment = _get_literal(store, uri, _RDFS_COMMENT)
        parent = _get_named_node(store, uri, _RDFS_SUBCLASS_OF)
        schema.classes[uri] = ClassInfo(
            uri=uri,
            label=label,
            comment=comment,
            parent=parent,
        )

    # Find all properties (owl:DatatypeProperty, owl:ObjectProperty, rdf:Property)
    # Map domain URI -> list of PropertyInfo
    domain_props: dict[str, list[PropertyInfo]] = {}
    for prop_type in (_OWL_DATATYPE_PROPERTY, _OWL_OBJECT_PROPERTY, _RDF_PROPERTY):
        for quad in store.quads_for_pattern(None, NamedNode(_RDF_TYPE), NamedNode(prop_type), None):
            subj = quad.subject
            subj_str = str(subj)
            if not (subj_str.startswith("<") and subj_str.endswith(">")):
                continue
            prop_uri = subj_str[1:-1]
            domain = _get_named_node(store, prop_uri, _RDFS_DOMAIN)
            range_uri = _get_named_node(store, prop_uri, _RDFS_RANGE)
            comment = _get_literal(store, prop_uri, _RDFS_COMMENT)
            if domain:
                prop_info = PropertyInfo(predicate=prop_uri, range=range_uri, comment=comment)
                domain_props.setdefault(domain, []).append(prop_info)

    # Assign direct properties to classes
    for domain_uri, props in domain_props.items():
        if domain_uri in schema.classes:
            schema.classes[domain_uri].properties.extend(props)
        else:
            # Domain class not declared as owl:Class — add it anyway
            schema.classes[domain_uri] = ClassInfo(uri=domain_uri, properties=list(props))

    # Property inheritance: subclasses get parent properties
    # Build parent map and iterate until stable
    changed = True
    while changed:
        changed = False
        for uri, cls in schema.classes.items():
            if cls.parent and cls.parent in schema.classes:
                parent_cls = schema.classes[cls.parent]
                existing_preds = {p.predicate for p in cls.properties}
                for parent_prop in parent_cls.properties:
                    if parent_prop.predicate not in existing_preds:
                        cls.properties.append(parent_prop)
                        existing_preds.add(parent_prop.predicate)
                        changed = True

    logger.info("Extracted %d classes from ontology %s", len(schema.classes), path.name)
    return schema


def extract_from_data(store: Store) -> Schema:
    """Empirically extract schema by querying used classes/predicates in a store."""
    schema = Schema()

    # Find all used classes
    class_results = store.query("SELECT DISTINCT ?class WHERE { ?s a ?class . }")
    class_uris: list[str] = []
    for row in class_results:
        cls_node = row[0]  # type: ignore[index]
        cls_str = str(cls_node)
        if cls_str.startswith("<") and cls_str.endswith(">"):
            class_uris.append(cls_str[1:-1])

    for class_uri in class_uris:
        schema.classes[class_uri] = ClassInfo(uri=class_uri)

    # For each class, find used predicates and infer ranges
    for class_uri in class_uris:
        pred_results = store.query(
            f"SELECT DISTINCT ?pred ?o WHERE {{ ?s a <{class_uri}> ; ?pred ?o . }}"
        )
        props: dict[str, PropertyInfo] = {}
        for row in pred_results:
            pred_node = row[0]  # type: ignore[index]
            obj_node = row[1]  # type: ignore[index]
            pred_str = str(pred_node)
            if not (pred_str.startswith("<") and pred_str.endswith(">")):
                continue
            pred_uri = pred_str[1:-1]
            if pred_uri == _RDF_TYPE:
                continue
            # Infer range from object type
            obj_str = str(obj_node)
            if pred_uri not in props:
                if obj_str.startswith("<") and obj_str.endswith(">"):
                    range_uri = ""  # Named node but we don't know the type
                else:
                    # Literal — try to get datatype
                    try:
                        dt = obj_node.datatype
                        range_uri = _uri(dt) if dt else ""
                    except AttributeError:
                        range_uri = ""
                props[pred_uri] = PropertyInfo(predicate=pred_uri, range=range_uri)

        schema.classes[class_uri].properties = list(props.values())

    logger.info("Empirically extracted %d classes from store", len(schema.classes))
    return schema


def extract_schema(
    data_path: Path | str | None = None,
    ontology_path: Path | str | None = None,
) -> Schema:
    """Extract schema, preferring ontology when available, falling back to data."""
    if ontology_path is not None:
        logger.info("Using ontology extraction from %s", ontology_path)
        return extract_from_ontology(Path(ontology_path))
    if data_path is not None:
        logger.info("Falling back to empirical extraction from %s", data_path)
        store = _load_store(Path(data_path))
        return extract_from_data(store)
    raise ValueError("At least one of data_path or ontology_path must be provided")


def generate_schemas_yaml(
    schema: Schema,
    output_path: Path | str,
    prefix_map: dict[str, str] | None = None,
) -> None:
    """Write schema to a schemas.yaml file compatible with plugin context format."""
    output_path = Path(output_path)
    data = schema.to_schemas_yaml(prefix_map or {})
    output_path.write_text(yaml.dump(data, default_flow_style=False, allow_unicode=True))
    logger.info("Wrote schemas.yaml to %s", output_path)
