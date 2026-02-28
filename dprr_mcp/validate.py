import re
from dataclasses import dataclass, field

from pyparsing import ParseException
from rdflib.plugins.sparql import prepareQuery
from rdflib.plugins.sparql.algebra import translateQuery, traverse
from rdflib.plugins.sparql.parser import parseQuery
from rdflib.plugins.sparql.parserutils import CompValue
from rdflib.term import URIRef, Variable

from dprr_mcp.store import execute_query

RDF_TYPE = URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")


def _suggest(name: str, valid_names: list[str]) -> str:
    """Return a 'Did you mean' suffix if close matches exist, else empty string."""
    from difflib import get_close_matches

    matches = get_close_matches(name, valid_names, n=3, cutoff=0.6)
    return f" Did you mean: {', '.join(matches)}?" if matches else ""


def _local_name(uri: str) -> str:
    """Extract the local name from a URI, handling both # and / separators."""
    if "#" in uri:
        return uri.rsplit("#", 1)[-1]
    return uri.rsplit("/", 1)[-1]


@dataclass
class ValidationResult:
    success: bool
    sparql: str
    rows: list[dict[str, str]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _expand_uri(prefixed: str, prefix_map: dict[str, str]) -> str:
    """Expand a prefixed URI like 'vocab:Person' to full URI."""
    if ":" not in prefixed:
        return prefixed
    prefix, local = prefixed.split(":", 1)
    if prefix in prefix_map:
        return prefix_map[prefix] + local
    return prefixed


def _scan_used_prefixes(sparql: str) -> set[str]:
    """Scan SPARQL query text for prefix:localName patterns, returning prefix names used."""
    # Match prefixed names like vocab:Person, rdfs:label, etc.
    # Exclude things inside <> (full URIs) and string literals
    used = set()
    # Remove string literals and full URIs to avoid false positives
    cleaned = re.sub(r'"[^"]*"', '', sparql)
    cleaned = re.sub(r"'[^']*'", '', cleaned)
    cleaned = re.sub(r'<[^>]*>', '', cleaned)
    # Find prefix:localName patterns (prefix must be alphabetic)
    for match in re.finditer(r'\b([a-zA-Z][a-zA-Z0-9]*):([a-zA-Z_]\w*)', cleaned):
        prefix = match.group(1)
        # Exclude PREFIX declarations themselves
        if prefix.upper() != "PREFIX":
            used.add(prefix)
    return used


def _get_declared_prefixes(sparql: str) -> set[str]:
    """Extract prefix names already declared in PREFIX statements."""
    declared = set()
    for match in re.finditer(r'PREFIX\s+(\w+)\s*:', sparql, re.IGNORECASE):
        declared.add(match.group(1))
    return declared


def _split_comments_and_query(sparql: str) -> tuple[list[str], str]:
    """Split leading comment lines from the query body."""
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
    """Parse a SPARQL query, automatically fixing missing PREFIX declarations.

    Returns (fixed_sparql, errors) where errors is empty on success.
    """
    # First, try parsing as-is
    try:
        prepareQuery(sparql)
        return sparql, []
    except ParseException as e:
        return sparql, [str(e)]
    except Exception as e:
        error_msg = str(e)
        if "Unknown namespace prefix" not in error_msg:
            return sparql, [error_msg]

    # We have a missing prefix error -- attempt repair
    comments, query_body = _split_comments_and_query(sparql)
    declared = _get_declared_prefixes(query_body)
    used = _scan_used_prefixes(query_body)
    missing = used - declared

    # Build PREFIX declarations for missing prefixes
    new_prefixes = []
    for prefix in sorted(missing):
        if prefix in prefix_map:
            new_prefixes.append(f"PREFIX {prefix}: <{prefix_map[prefix]}>")

    # Reconstruct query with added prefixes
    parts = []
    if comments:
        parts.append('\n'.join(comments))
    if new_prefixes:
        parts.append('\n'.join(new_prefixes))
    parts.append(query_body)
    fixed = '\n'.join(parts)

    # Try parsing the fixed query
    try:
        prepareQuery(fixed)
        return fixed, []
    except ParseException as e:
        return fixed, [str(e)]
    except Exception as e:
        return fixed, [str(e)]


def build_schema_dict(schemas: dict, prefix_map: dict[str, str]) -> dict:
    """Convert schemas YAML to dict[class_full_uri][predicate_full_uri] = [range_types].

    Also includes rdfs:label and rdf:type as universal predicates.
    """
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
    """Parse query and collect all BGP triples from the algebra."""
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


def validate_semantics(sparql: str, schema_dict: dict) -> list[str]:
    """Validate a SPARQL query against the schema dictionary.

    Checks:
    - Classes used with rdf:type exist in schema
    - Predicates used on typed variables are valid for that class

    Returns list of error strings (empty if valid).
    """
    errors = []

    try:
        triples = _collect_triples(sparql)
    except Exception:
        # If we can't parse, skip semantic validation
        return errors

    # Build variable-to-class mapping from ?x a SomeClass patterns
    var_types: dict[str, list[str]] = {}
    all_class_uris = set(schema_dict.keys())

    for s, p, o in triples:
        if p == RDF_TYPE and isinstance(o, URIRef):
            class_uri = str(o)
            # Check if class exists in schema
            if class_uri not in all_class_uris:
                local_name = _local_name(class_uri)
                valid_classes = sorted(
                    _local_name(uri) for uri in all_class_uris
                )
                errors.append(
                    f"Unknown class '{local_name}'. Valid classes: {', '.join(valid_classes)}"
                    + _suggest(local_name, valid_classes)
                )
            if isinstance(s, Variable):
                var_name = str(s)
                if var_name not in var_types:
                    var_types[var_name] = []
                var_types[var_name].append(class_uri)

    # Check predicates on typed variables
    for s, p, o in triples:
        if p == RDF_TYPE:
            continue
        if not isinstance(p, URIRef):
            continue
        if not isinstance(s, Variable):
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
                valid_local = sorted(
                    _local_name(uri) for uri in valid_preds
                )
                errors.append(
                    f"Unknown predicate '{pred_local}' for class "
                    f"'{_local_name(class_uri)}'. "
                    f"Valid predicates: {', '.join(valid_local)}"
                    + _suggest(pred_local, valid_local)
                )

    return errors


def validate_and_execute(
    sparql: str,
    store,
    schema_dict: dict,
    prefix_map: dict[str, str],
) -> ValidationResult:
    """Validate and execute a SPARQL query through all three tiers.

    Tier 1: Parse and fix prefixes
    Tier 2: Semantic validation against schema
    Tier 3: Execute query and return results
    """
    # Tier 1: Syntax + prefix repair
    fixed_sparql, parse_errors = parse_and_fix_prefixes(sparql, prefix_map)
    if parse_errors:
        return ValidationResult(
            success=False,
            sparql=fixed_sparql,
            rows=[],
            errors=parse_errors,
        )

    # Tier 2: Semantic validation
    semantic_errors = validate_semantics(fixed_sparql, schema_dict)
    if semantic_errors:
        return ValidationResult(
            success=False,
            sparql=fixed_sparql,
            rows=[],
            errors=semantic_errors,
        )

    # Tier 3: Execute query
    try:
        rows = execute_query(store, fixed_sparql)
    except Exception as e:
        return ValidationResult(
            success=False,
            sparql=fixed_sparql,
            rows=[],
            errors=[f"Query execution error: {e}"],
        )

    return ValidationResult(
        success=True,
        sparql=fixed_sparql,
        rows=rows,
        errors=[],
    )
