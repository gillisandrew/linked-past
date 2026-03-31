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

# Namespaces to filter from empirical extraction (ontology machinery, not domain classes)
_META_NAMESPACES = frozenset({
    "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "http://www.w3.org/2000/01/rdf-schema#",
    "http://www.w3.org/2002/07/owl#",
})


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

    def to_schemas_yaml(self, prefix_map: dict[str, str] | None = None) -> str:
        """Convert to schemas.yaml string compatible with linked-past plugin context format.

        Output structure matches hand-written schemas.yaml files:
        ```yaml
        classes:
          ClassName:
            label: "Human Label"
            comment: "Description"
            uri: "vocab:ClassName"
            properties:
              - pred: "vocab:hasFoo"
                range: "xsd:string"
                comment: "..."
        ```
        """
        pm = prefix_map or {}
        classes_dict: dict[str, Any] = {}
        for local_name, cls in self.classes.items():
            entry: dict[str, Any] = {}
            if cls.label:
                entry["label"] = cls.label
            if cls.comment:
                entry["comment"] = cls.comment
            entry["uri"] = _shorten(cls.uri, pm)
            if cls.properties:
                props_list = []
                for prop in cls.properties:
                    prop_entry: dict[str, Any] = {"pred": _shorten(prop.predicate, pm)}
                    if prop.range:
                        prop_entry["range"] = _shorten(prop.range, pm)
                    if prop.comment:
                        prop_entry["comment"] = prop.comment
                    props_list.append(prop_entry)
                entry["properties"] = props_list
            classes_dict[local_name] = entry

        return yaml.dump(
            {"classes": classes_dict},
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
        )


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

    # Build URI -> local name mapping
    uri_to_local: dict[str, str] = {}
    for uri in class_uris:
        local = uri.rsplit("#", 1)[-1] if "#" in uri else uri.rsplit("/", 1)[-1]
        uri_to_local[uri] = local

    for uri in class_uris:
        label = _get_literal(store, uri, _RDFS_LABEL)
        comment = _get_literal(store, uri, _RDFS_COMMENT)
        parent = _get_named_node(store, uri, _RDFS_SUBCLASS_OF)
        local_name = uri_to_local[uri]
        schema.classes[local_name] = ClassInfo(
            uri=uri,
            label=label,
            comment=comment,
            parent=parent,
        )

    # Build reverse lookup: URI -> local name (for property assignment)
    uri_to_key: dict[str, str] = {cls.uri: key for key, cls in schema.classes.items()}

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

    # Assign direct properties to classes (look up by URI)
    for domain_uri, props in domain_props.items():
        key = uri_to_key.get(domain_uri)
        if key:
            schema.classes[key].properties.extend(props)
        else:
            # Domain class not declared as owl:Class — add it anyway
            local = domain_uri.rsplit("#", 1)[-1] if "#" in domain_uri else domain_uri.rsplit("/", 1)[-1]
            schema.classes[local] = ClassInfo(uri=domain_uri, properties=list(props))
            uri_to_key[domain_uri] = local

    # Property inheritance: subclasses get parent properties
    # parent field stores a URI — resolve to local key for lookup
    changed = True
    while changed:
        changed = False
        for _key, cls in schema.classes.items():
            if cls.parent:
                parent_key = uri_to_key.get(cls.parent)
                if parent_key and parent_key in schema.classes:
                    parent_cls = schema.classes[parent_key]
                    existing_preds = {p.predicate for p in cls.properties}
                    for parent_prop in parent_cls.properties:
                        if parent_prop.predicate not in existing_preds:
                            cls.properties.append(parent_prop)
                            existing_preds.add(parent_prop.predicate)
                            changed = True

    logger.info("Extracted %d classes from ontology %s", len(schema.classes), path.name)
    return schema


def extract_from_data(store: Store, *, filter_meta: bool = False) -> Schema:
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

    if filter_meta:
        class_uris = [u for u in class_uris if not any(u.startswith(ns) for ns in _META_NAMESPACES)]

    for class_uri in class_uris:
        local = class_uri.rsplit("#", 1)[-1] if "#" in class_uri else class_uri.rsplit("/", 1)[-1]
        schema.classes[local] = ClassInfo(uri=class_uri, label=local)

    # Build URI -> local name lookup for property assignment
    uri_to_key: dict[str, str] = {cls.uri: key for key, cls in schema.classes.items()}

    # For each class, find used predicates with a sample object (for range inference)
    for class_uri in class_uris:
        pred_results = store.query(
            f"SELECT ?pred (SAMPLE(?o) AS ?sample) "
            f"WHERE {{ ?s a <{class_uri}> ; ?pred ?o }} GROUP BY ?pred"
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
            # Infer range from sample object
            obj_str = str(obj_node)
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

        key = uri_to_key.get(class_uri, class_uri)
        if key in schema.classes:
            schema.classes[key].properties = list(props.values())

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
        return extract_from_data(store, filter_meta=True)
    raise ValueError("At least one of data_path or ontology_path must be provided")


def generate_schemas_yaml(
    schema: Schema,
    output_path: Path | str,
    prefix_map: dict[str, str] | None = None,
) -> None:
    """Write schema to a schemas.yaml file compatible with plugin context format."""
    output_path = Path(output_path)
    content = schema.to_schemas_yaml(prefix_map)
    output_path.write_text(content)
    logger.info("Wrote schemas.yaml to %s", output_path)
