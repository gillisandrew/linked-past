"""SPARQL validation pipeline: parse, prefix repair, semantic checks."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from difflib import get_close_matches

from pyparsing import ParseException
from rdflib.plugins.sparql import prepareQuery
from rdflib.plugins.sparql.algebra import translateQuery, traverse
from rdflib.plugins.sparql.parser import parseQuery
from rdflib.plugins.sparql.parserutils import CompValue
from rdflib.term import URIRef, Variable

logger = logging.getLogger(__name__)

RDF_TYPE = URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")


def _suggest(name: str, valid_names: list[str]) -> str:
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
    cleaned = re.sub(r'"[^"]*"', "", sparql)
    cleaned = re.sub(r"'[^']*'", "", cleaned)
    cleaned = re.sub(r"<[^>]*>", "", cleaned)
    used = set()
    for match in re.finditer(r"\b([a-zA-Z][a-zA-Z0-9]*):([a-zA-Z_]\w*)", cleaned):
        prefix = match.group(1)
        if prefix.upper() != "PREFIX":
            used.add(prefix)
    return used


def _get_declared_prefixes(sparql: str) -> set[str]:
    declared = set()
    for match in re.finditer(r"PREFIX\s+(\w+)\s*:", sparql, re.IGNORECASE):
        declared.add(match.group(1))
    return declared


def _split_comments_and_query(sparql: str) -> tuple[list[str], str]:
    lines = sparql.split("\n")
    comments = []
    rest_start = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("#") or stripped == "":
            comments.append(line)
            rest_start = i + 1
        else:
            break
    query_body = "\n".join(lines[rest_start:])
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
        parts.append("\n".join(comments))
    if new_prefixes:
        parts.append("\n".join(new_prefixes))
    parts.append(query_body)
    fixed = "\n".join(parts)

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
    # RDF/RDFS
    "http://www.w3.org/1999/02/22-rdf-syntax-ns#type",
    "http://www.w3.org/2000/01/rdf-schema#label",
    "http://www.w3.org/2000/01/rdf-schema#comment",
    "http://www.w3.org/2000/01/rdf-schema#seeAlso",
    # SKOS (commonly used across all datasets)
    "http://www.w3.org/2004/02/skos/core#prefLabel",
    "http://www.w3.org/2004/02/skos/core#altLabel",
    "http://www.w3.org/2004/02/skos/core#broader",
    "http://www.w3.org/2004/02/skos/core#narrower",
    "http://www.w3.org/2004/02/skos/core#related",
    "http://www.w3.org/2004/02/skos/core#exactMatch",
    "http://www.w3.org/2004/02/skos/core#closeMatch",
    "http://www.w3.org/2004/02/skos/core#inScheme",
    "http://www.w3.org/2004/02/skos/core#definition",
    "http://www.w3.org/2004/02/skos/core#note",
    # Dublin Core (commonly used across all datasets)
    "http://purl.org/dc/terms/title",
    "http://purl.org/dc/terms/description",
    "http://purl.org/dc/terms/source",
    "http://purl.org/dc/terms/isPartOf",
    "http://purl.org/dc/terms/isReplacedBy",
    # OWL
    "http://www.w3.org/2002/07/owl#sameAs",
    "http://www.w3.org/2002/07/owl#deprecated",
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
    """Validate a SPARQL query against the schema dictionary.

    Returns a list of strings. No blocking errors — all issues are
    constructive hints that help the LLM self-correct.

    Hints include available alternatives so the LLM knows what vocabulary
    to use (e.g., "Class 'City' not in schema. Available: Place, Location, Name").
    """
    hints = []
    try:
        triples = _collect_triples(sparql)
    except Exception:
        return hints

    var_types: dict[str, list[str]] = {}
    all_class_uris = set(schema_dict.keys())

    for s, p, o in triples:
        if p == RDF_TYPE and isinstance(o, URIRef):
            class_uri = str(o)
            if class_uri not in all_class_uris:
                local_name = _local_name(class_uri)
                valid_classes = sorted(_local_name(uri) for uri in all_class_uris)
                suggestion = _suggest(local_name, valid_classes)
                hints.append(
                    f"Hint: Class '{local_name}' not in this dataset's schema. "
                    f"Available classes: {', '.join(valid_classes[:15])}.{suggestion}"
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
        if pred_uri in _UNIVERSAL_PREDS:
            continue
        for class_uri in var_types[var_name]:
            if class_uri not in schema_dict:
                continue
            valid_preds = schema_dict[class_uri]
            if pred_uri not in valid_preds:
                pred_local = _local_name(pred_uri)
                class_local = _local_name(class_uri)
                valid_local = sorted(_local_name(uri) for uri in valid_preds)
                suggestion = _suggest(pred_local, valid_local)
                hints.append(
                    f"Hint: '{pred_local}' not a known predicate for {class_local}. "
                    f"Available: {', '.join(valid_local[:15])}.{suggestion}"
                )
    return hints


def validate_and_execute(
    sparql: str,
    store,
    schema_dict: dict,
    prefix_map: dict[str, str],
) -> QueryResult:
    """Validate and execute a SPARQL query through all three tiers."""
    fixed_sparql, parse_errors = parse_and_fix_prefixes(sparql, prefix_map)
    if parse_errors:
        return QueryResult(success=False, sparql=fixed_sparql, errors=parse_errors)

    semantic_errors = validate_semantics(fixed_sparql, schema_dict)
    if semantic_errors:
        return QueryResult(success=False, sparql=fixed_sparql, errors=semantic_errors)

    try:
        from linked_past.core.store import execute_query
        rows = execute_query(store, fixed_sparql)
    except Exception as e:
        return QueryResult(success=False, sparql=fixed_sparql, errors=[f"Query execution error: {e}"])

    return QueryResult(success=True, sparql=fixed_sparql, rows=rows)
