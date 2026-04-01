"""SPARQL validation pipeline: parse, prefix repair, semantic checks."""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from difflib import get_close_matches
from typing import TYPE_CHECKING

from pyparsing import ParseException
from rdflib.plugins.sparql import prepareQuery
from rdflib.plugins.sparql.algebra import translateQuery, traverse
from rdflib.plugins.sparql.parser import parseQuery
from rdflib.plugins.sparql.parserutils import CompValue
from rdflib.term import Literal, URIRef, Variable

if TYPE_CHECKING:
    from pyoxigraph import Store

logger = logging.getLogger(__name__)

RDF_TYPE = URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")
_DATE_SUFFIXES = ("gYear", "date", "dateTime")


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


@dataclass
class DiagnosticResult:
    """Result of diagnosing why a query returned 0 rows."""
    hints: list[str] = field(default_factory=list)
    probe_results: dict[str, bool] = field(default_factory=dict)


def diagnose_empty_result(
    sparql: str,
    store: Store,
    schema_dict: dict,
    prefix_map: dict[str, str],
    dataset: str | None = None,
    semantic_hints: list[str] | None = None,
    budget_ms: int = 500,
) -> DiagnosticResult:
    """Diagnose why a valid SPARQL query returned 0 rows."""
    result = DiagnosticResult()
    result.hints.extend(_run_heuristics(sparql, schema_dict, prefix_map, dataset, semantic_hints))
    probe_hints, probe_results = _run_probes(sparql, store, budget_ms)
    result.hints.extend(probe_hints)
    result.probe_results = probe_results
    return result


def log_zero_result(
    dataset: str | None,
    sparql: str,
    diagnostics: DiagnosticResult,
    semantic_hints: list[str],
    duration_ms: int,
) -> None:
    """Append a zero-result query entry to the diagnostics JSONL log.

    Fire-and-forget: logs a warning on failure, never raises.
    """
    try:
        from linked_past.core.store import get_data_dir

        log_dir = get_data_dir() / "diagnostics"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "zero_results.jsonl"

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "dataset": dataset,
            "sparql": sparql,
            "diagnostics": diagnostics.hints,
            "probe_results": diagnostics.probe_results,
            "semantic_hints": semantic_hints,
            "duration_ms": duration_ms,
        }

        with open(log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        logger.warning("Failed to log zero-result query: %s", e)


def _parse_triples_and_types(sparql: str) -> tuple[list[tuple], dict[str, list[str]], dict[str, list[str]]]:
    """Parse SPARQL to extract triples, variable types, and variable predicates."""
    triples: list[tuple] = []
    var_types: dict[str, list[str]] = {}
    var_preds: dict[str, list[str]] = {}
    try:
        triples = _collect_triples(sparql)
        for s, p, o in triples:
            if p == RDF_TYPE and isinstance(s, Variable) and isinstance(o, URIRef):
                var_types.setdefault(str(s), []).append(str(o))
    except Exception:
        pass
    for s, p, o in triples:
        if isinstance(p, URIRef) and isinstance(o, Variable):
            var_preds.setdefault(str(o), []).append(str(p))
    return triples, var_types, var_preds


def _check_boolean_escalation(semantic_hints: list[str] | None) -> list[str]:
    """Escalate open-world boolean warnings from pre-execution."""
    hints: list[str] = []
    if semantic_hints:
        for hint in semantic_hints:
            if "open-world boolean" in hint.lower():
                hints.append(
                    "Diagnostic: This query returned 0 rows. The open-world boolean "
                    "warning above is likely the cause — the property only stores "
                    "true values, so filtering for false always yields nothing."
                )
                break
    return hints


def _check_contradictory_types(var_types: dict[str, list[str]], schema_dict: dict) -> list[str]:
    """Detect variables typed as multiple classes."""
    hints: list[str] = []
    for var_name, types in var_types.items():
        if len(types) > 1:
            known = [t for t in types if t in schema_dict]
            if len(known) > 1:
                names = [_local_name(t) for t in known]
                hints.append(
                    f"Diagnostic: ?{var_name} is typed as both {' and '.join(names)}. "
                    f"No entity is likely to satisfy both types simultaneously. "
                    f"Use separate variables for each type."
                )
    return hints


def _check_bc_date_sign(sparql: str, var_preds: dict[str, list[str]], schema_dict: dict) -> list[str]:
    """Detect positive integers on BC date fields."""
    hints: list[str] = []
    bc_preds: set[str] = set()
    for class_uri, preds in schema_dict.items():
        for pred_uri, pred_info in preds.items():
            if pred_uri == "_meta" or not isinstance(pred_info, dict):
                continue
            comment = pred_info.get("comment", "").lower()
            if "negative" in comment and "bc" in comment:
                bc_preds.add(pred_uri)

    if bc_preds:
        filter_pattern = re.compile(
            r"FILTER\s*\(.*?\?\s*(\w+)\s*(?:>|>=|=)\s*(\d+)",
            re.IGNORECASE,
        )
        for match in filter_pattern.finditer(sparql):
            var_name = match.group(1)
            value = int(match.group(2))
            if value > 0:
                for pred_uri in var_preds.get(var_name, []):
                    if pred_uri in bc_preds:
                        pred_local = _local_name(pred_uri)
                        hints.append(
                            f"Diagnostic: '{pred_local}' uses negative integers for BC dates. "
                            f"Your filter compares ?{var_name} against {value} (a positive "
                            f"number, meaning AD). For BC dates, use negative values "
                            f"(e.g., -100 for 100 BC)."
                        )
                        break
    return hints


def _check_date_padding(sparql: str, var_preds: dict[str, list[str]], schema_dict: dict) -> list[str]:
    """Detect unpadded years and string date comparisons."""
    hints: list[str] = []
    date_preds: dict[str, str] = {}  # pred_uri -> datatype suffix
    for class_uri, preds in schema_dict.items():
        for pred_uri, pred_info in preds.items():
            if pred_uri == "_meta" or not isinstance(pred_info, dict):
                continue
            dt = pred_info.get("datatype", "")
            if dt:
                for suffix in _DATE_SUFFIXES:
                    if dt.endswith(suffix):
                        date_preds[pred_uri] = suffix
                        break

    if date_preds:
        date_filter = re.compile(
            r"""FILTER\s*\(.*?\?(\w+)\s*(?:[<>=!]+)\s*"(-?\d{1,3})(?:["-])""",
            re.IGNORECASE,
        )
        for match in date_filter.finditer(sparql):
            var_name = match.group(1)
            year_val = match.group(2)
            for pred_uri in var_preds.get(var_name, []):
                if pred_uri in date_preds:
                    pred_local = _local_name(pred_uri)
                    dtype = date_preds[pred_uri]
                    padded = year_val.zfill(4) if not year_val.startswith("-") else "-" + year_val[1:].zfill(4)
                    if dtype == "gYear":
                        example = f'"{padded}"^^xsd:gYear'
                    else:
                        example = f'"{padded}-01-01"^^xsd:{dtype}'
                    hints.append(
                        f"Diagnostic: '{pred_local}' uses xsd:{dtype} with zero-padded 4-digit years. "
                        f'Your value "{year_val}" needs padding: use {example} '
                        f'(e.g., "-0044-03-15"^^xsd:date for 44 BC).'
                    )
                    break

    # Date string comparison without type cast — catches "-0100" compared as string
    if date_preds:
        untyped_date = re.compile(
            r"""FILTER\s*\(.*?\?(\w+)\s*[<>=!]+\s*"(-?\d{4})"(?!\s*\^\^)""",
            re.IGNORECASE,
        )
        for match in untyped_date.finditer(sparql):
            var_name = match.group(1)
            year_val = match.group(2)
            for pred_uri in var_preds.get(var_name, []):
                if pred_uri in date_preds:
                    pred_local = _local_name(pred_uri)
                    hints.append(
                        f'Diagnostic: Comparing \'{pred_local}\' as a plain string "{year_val}" '
                        f"will give wrong results for date ranges (string ordering ≠ chronological). "
                        f"Use xsd:integer cast: FILTER(xsd:integer(?{var_name}) >= {int(year_val)}) "
                        f'or typed literal: FILTER(?{var_name} >= "{year_val}"^^xsd:gYear).'
                    )
                    break
    return hints


def _check_string_uri_mismatch(
    sparql: str,
    triples: list[tuple],
    var_types: dict[str, list[str]],
    schema_dict: dict,
) -> list[str]:
    """Detect string vs URI range mismatches."""
    hints: list[str] = []
    var_range_types: dict[str, list[str]] = {}
    for s, p, o in triples:
        if isinstance(p, URIRef) and isinstance(o, Variable) and isinstance(s, Variable):
            pred_uri = str(p)
            s_name = str(s)
            for class_uri in var_types.get(s_name, []):
                if class_uri not in schema_dict:
                    continue
                pred_info = schema_dict[class_uri].get(pred_uri)
                if isinstance(pred_info, dict):
                    for range_uri in pred_info.get("ranges", []):
                        var_range_types.setdefault(str(o), []).append(range_uri)

    string_filter = re.compile(
        r"""FILTER\s*\(.*?\?(\w+)\s*=\s*"([^"]*)"(?:\^\^[^ )]*)?""",
        re.IGNORECASE,
    )
    for match in string_filter.finditer(sparql):
        var_name = match.group(1)
        ranges = var_range_types.get(var_name, [])
        for range_uri in ranges:
            if not range_uri.startswith(_XSD_NS):
                range_local = _local_name(range_uri)
                hints.append(
                    f"Diagnostic: ?{var_name} has range {range_local} (a URI/entity), "
                    f"but you're comparing it to a string literal. Use the entity URI "
                    f"or match via rdfs:label on the linked entity."
                )
                break
    return hints


def _run_heuristics(
    sparql: str,
    schema_dict: dict,
    prefix_map: dict[str, str],
    dataset: str | None,
    semantic_hints: list[str] | None,
) -> list[str]:
    """Zero-cost heuristic checks on the SPARQL AST."""
    triples, var_types, var_preds = _parse_triples_and_types(sparql)
    hints: list[str] = []
    hints.extend(_check_boolean_escalation(semantic_hints))
    hints.extend(_check_contradictory_types(var_types, schema_dict))
    hints.extend(_check_bc_date_sign(sparql, var_preds, schema_dict))
    hints.extend(_check_date_padding(sparql, var_preds, schema_dict))
    hints.extend(_check_string_uri_mismatch(sparql, triples, var_types, schema_dict))
    return hints


def _term_to_sparql(term, bnode_counter: dict) -> str:
    """Convert an rdflib term to a SPARQL string representation."""
    from rdflib.term import BNode

    if isinstance(term, Variable):
        return f"?{term}"
    elif isinstance(term, URIRef):
        return f"<{term}>"
    elif isinstance(term, BNode):
        key = str(term)
        if key not in bnode_counter:
            bnode_counter[key] = f"?_bnode_{len(bnode_counter)}"
        return bnode_counter[key]
    elif isinstance(term, Literal):
        if term.datatype:
            return f'"{term}"^^<{term.datatype}>'
        elif term.language:
            return f'"{term}"@{term.language}'
        else:
            return f'"{term}"'
    else:
        return f'"{term}"'


def _collect_bgp_triples(algebra, skip_optional: bool = True) -> list[tuple]:
    """Collect triple patterns from BGP nodes, skipping OPTIONAL (LeftJoin.p2) by default."""
    triples = []

    def _walk(node, in_optional: bool = False):
        if isinstance(node, CompValue):
            if node.name == "BGP" and not in_optional:
                for t in node.get("triples", []):
                    triples.append(t)
            elif node.name == "LeftJoin" and skip_optional:
                _walk(node.get("p1"), in_optional=False)
                _walk(node.get("p2"), in_optional=True)
                return
            for key in node:
                _walk(node[key], in_optional)
        elif isinstance(node, list):
            for item in node:
                _walk(item, in_optional)

    _walk(algebra)
    return triples


def _build_ask_from_triples(triples: list[tuple], prefix_decls: str) -> str:
    """Build an ASK query from raw triple patterns and prefix declarations."""
    bnode_counter: dict = {}
    patterns = []
    for s, p, o in triples:
        s_str = _term_to_sparql(s, bnode_counter)
        p_str = _term_to_sparql(p, bnode_counter)
        o_str = _term_to_sparql(o, bnode_counter)
        patterns.append(f"  {s_str} {p_str} {o_str} .")
    body = "\n".join(patterns)
    return f"{prefix_decls}\nASK {{\n{body}\n}}"


def _strip_filters_algebra(sparql: str) -> str | None:
    """Use rdflib's algebra to extract base graph pattern without filters.

    Parses the SPARQL, collects required BGP triples (skipping OPTIONAL),
    and rebuilds as an ASK query. Returns None if parsing fails.
    """
    try:
        parsed = parseQuery(sparql)
        q = translateQuery(parsed)
        triples = _collect_bgp_triples(q.algebra)
        if not triples:
            return None

        return _build_ask_from_triples(triples, _extract_prefix_decls(sparql))
    except Exception:
        return None


def _extract_prefix_decls(sparql: str) -> str:
    """Extract PREFIX declarations from a SPARQL query as a single string."""
    decls = []
    for match in re.finditer(r"PREFIX\s+\w+:\s*<[^>]+>", sparql, re.IGNORECASE):
        decls.append(match.group(0))
    return "\n".join(decls)


def _extract_filter_clauses(sparql: str) -> list[tuple[int, int, str]]:
    """Extract FILTER clause positions and text using brace/paren counting."""
    filters: list[tuple[int, int, str]] = []
    upper = sparql.upper()
    i = 0
    while i < len(upper):
        idx = upper.find("FILTER", i)
        if idx == -1:
            break
        if idx > 0 and upper[idx - 1].isalnum():
            i = idx + 6
            continue

        j = idx + 6
        while j < len(sparql) and sparql[j] in " \t\n\r":
            j += 1

        if j >= len(sparql):
            break

        if sparql[j] == "(":
            open_char, close_char = "(", ")"
        elif upper[j:].startswith("NOT") or upper[j:].startswith("EXISTS"):
            brace_start = sparql.find("{", j)
            if brace_start == -1:
                i = j
                continue
            j = brace_start
            open_char, close_char = "{", "}"
        else:
            i = j
            continue

        depth = 0
        k = j
        while k < len(sparql):
            if sparql[k] == open_char:
                depth += 1
            elif sparql[k] == close_char:
                depth -= 1
                if depth == 0:
                    filters.append((idx, k + 1, sparql[idx:k + 1]))
                    break
            k += 1

        i = k + 1 if k < len(sparql) else len(sparql)
    return filters


def _select_to_ask(sparql: str) -> str | None:
    """Convert a SELECT query to ASK, preserving all WHERE-clause content."""
    try:
        result = re.sub(
            r"SELECT\s+.*?(?=WHERE)",
            "ASK ",
            sparql,
            count=1,
            flags=re.IGNORECASE | re.DOTALL,
        )
        last_brace = result.rfind("}")
        if last_brace == -1:
            return None
        result = result[:last_brace + 1]
        return result
    except Exception:
        return None


def _run_probes(
    sparql: str,
    store: Store,
    budget_ms: int,
) -> tuple[list[str], dict[str, bool]]:
    """Budget-capped diagnostic ASK queries."""
    if store is None:
        return [], {}

    from linked_past.core.store import execute_ask

    hints: list[str] = []
    probe_results: dict[str, bool] = {}
    t0 = time.monotonic()

    def budget_remaining() -> int:
        elapsed = (time.monotonic() - t0) * 1000
        return int(budget_ms - elapsed)

    # Probe 1: ASK on base pattern (no filters) using algebra-based stripping
    ask_sparql = _strip_filters_algebra(sparql)
    if ask_sparql and budget_remaining() > 0:
        try:
            base_matches = execute_ask(store, ask_sparql)
            probe_results["base_pattern_matches"] = base_matches
            if base_matches:
                hints.append(
                    "Diagnostic: The base graph pattern matches data, but filters "
                    "exclude all results. Check your FILTER conditions."
                )

                # Probe 2: Strip individual filters to find the culprit
                if budget_remaining() > 0:
                    filters = _extract_filter_clauses(sparql)
                    for i, (start, end, filter_text) in enumerate(filters):
                        if budget_remaining() <= 0:
                            hints.append(
                                f"Diagnostic: Budget exhausted after checking {i}/{len(filters)} filters."
                            )
                            break
                        stripped = sparql[:start] + sparql[end:]
                        stripped_ask = _select_to_ask(stripped)
                        if not stripped_ask:
                            continue
                        try:
                            matches = execute_ask(store, stripped_ask)
                            probe_results[f"filter_{i}_stripped_matches"] = matches
                            if matches:
                                display = filter_text.strip()
                                if len(display) > 100:
                                    display = display[:100] + "..."
                                hints.append(
                                    f"Diagnostic: Removing `{display}` produces results. "
                                    f"This filter is likely too restrictive."
                                )
                        except Exception as e:
                            logger.debug("Filter isolation probe %d failed: %s", i, e)
            else:
                hints.append(
                    "Diagnostic: No entities match the base graph pattern (before "
                    "any filters). The triple patterns themselves have no matches — "
                    "check class names, predicates, and join paths."
                )

                # Probe 3: Join decomposition — check individual triple patterns
                if budget_remaining() > 0:
                    try:
                        parsed = parseQuery(sparql)
                        q = translateQuery(parsed)
                        probe_triples = _collect_bgp_triples(q.algebra)
                    except Exception:
                        probe_triples = []

                    prefix_str = _extract_prefix_decls(sparql)

                    for i, triple in enumerate(probe_triples):
                        if budget_remaining() <= 0:
                            break
                        single_ask = _build_ask_from_triples([triple], prefix_str)
                        s, p, o = triple
                        s_str = _term_to_sparql(s, {})
                        p_str = _term_to_sparql(p, {})
                        o_str = _term_to_sparql(o, {})
                        try:
                            matches = execute_ask(store, single_ask)
                            probe_results[f"triple_{i}_matches"] = matches
                            if not matches:
                                hints.append(
                                    f"Diagnostic: The pattern `{s_str} {p_str} {o_str}` has no "
                                    f"matches in the store. This is where the join breaks."
                                )
                        except Exception as e:
                            logger.debug("Join decomposition probe %d failed: %s", i, e)
        except Exception as e:
            logger.debug("Base pattern probe failed: %s", e)

    return hints, probe_results


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


_XSD_NS = "http://www.w3.org/2001/XMLSchema#"


def build_schema_dict(schemas: dict, prefix_map: dict[str, str]) -> dict:
    """Convert schemas YAML to dict[class_uri][pred_uri] = {ranges, datatype, open_world, ...}.

    Backwards-compatible: callers that check `pred_uri in schema_dict[class]`
    still work because dict keys are predicate URIs.
    """
    schema_dict: dict[str, dict] = {}
    for cls_name, cls_data in schemas.items():
        class_uri = _expand_uri(cls_data["uri"], prefix_map)
        predicates: dict[str, dict] = {}
        for prop in cls_data.get("properties", []):
            pred_uri = _expand_uri(prop["pred"], prefix_map)
            range_uri = _expand_uri(prop.get("range", ""), prefix_map)
            ranges = predicates.get(pred_uri, {}).get("ranges", [])
            if range_uri:
                ranges.append(range_uri)
            pred_info: dict = {
                "ranges": ranges,
                "datatype": range_uri if range_uri.startswith(_XSD_NS) else None,
                "open_world": prop.get("open_world", False),
                "comment": prop.get("comment", ""),
            }
            predicates[pred_uri] = pred_info
        predicates["_meta"] = {
            "count_distinct": cls_data.get("count_distinct", False),
        }
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


def validate_semantics(
    sparql: str,
    schema_dict: dict,
    class_counts: dict[str, int] | None = None,
) -> list[str]:
    """Validate a SPARQL query against the schema dictionary.

    Returns constructive hints. Performs:
    1. Unknown class/predicate detection (with suggestions)
    2. Recursive type inference through property ranges
    3. Literal datatype checking
    4. Domain-specific pattern checks (LIMIT, COUNT(DISTINCT), open-world booleans, uncertainty flags)
    """
    hints = []
    try:
        triples = _collect_triples(sparql)
    except Exception:
        return hints

    all_class_uris = set(k for k in schema_dict.keys())
    var_types: dict[str, list[str]] = {}

    # Pass 1: Explicit types from rdf:type
    for s, p, o in triples:
        if p == RDF_TYPE and isinstance(o, URIRef):
            class_uri = str(o)
            if class_uri not in all_class_uris:
                local_name = _local_name(class_uri)
                valid_classes = sorted(_local_name(uri) for uri in all_class_uris if uri != "_meta")
                suggestion = _suggest(local_name, valid_classes)
                hints.append(
                    f"Hint: Class '{local_name}' not in this dataset's schema. "
                    f"Available classes: {', '.join(valid_classes[:15])}.{suggestion}"
                )
            if isinstance(s, Variable):
                var_types.setdefault(str(s), []).append(class_uri)

    # Pass 2: Infer types from property ranges (fixed-point iteration)
    for _ in range(10):
        new_inferences = False
        for s, p, o in triples:
            if p == RDF_TYPE or not isinstance(p, URIRef) or not isinstance(o, Variable):
                continue
            if not isinstance(s, Variable):
                continue
            pred_uri = str(p)
            if pred_uri in _UNIVERSAL_PREDS:
                continue
            s_name = str(s)
            o_name = str(o)
            for class_uri in var_types.get(s_name, []):
                if class_uri not in schema_dict:
                    continue
                pred_info = schema_dict[class_uri].get(pred_uri)
                if pred_info is None or not isinstance(pred_info, dict):
                    continue
                for range_uri in pred_info.get("ranges", []):
                    if range_uri in all_class_uris and range_uri not in var_types.get(o_name, []):
                        var_types.setdefault(o_name, []).append(range_uri)
                        new_inferences = True
        if not new_inferences:
            break

    # Pass 3: Validate predicates against typed variables
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
            valid_preds = {k: v for k, v in schema_dict[class_uri].items() if k != "_meta"}
            if pred_uri not in valid_preds:
                pred_local = _local_name(pred_uri)
                class_local = _local_name(class_uri)
                valid_local = sorted(_local_name(uri) for uri in valid_preds)
                suggestion = _suggest(pred_local, valid_local)
                owner_classes = []
                for other_class, other_preds in schema_dict.items():
                    if pred_uri in other_preds and other_class != class_uri:
                        owner_classes.append(_local_name(other_class))
                join_hint = ""
                if owner_classes:
                    join_hint = f" This predicate belongs to: {', '.join(owner_classes)}."
                hints.append(
                    f"Hint: '{pred_local}' not a known predicate for {class_local}. "
                    f"Available: {', '.join(valid_local[:15])}.{suggestion}{join_hint}"
                )

    # Pass 4: Literal datatype checking
    hints.extend(_check_literal_datatypes(triples, var_types, schema_dict))

    # Pass 5: Domain-specific checks
    hints.extend(_check_open_world_booleans(sparql, triples, var_types, schema_dict))
    hints.extend(_check_count_distinct(sparql, var_types, schema_dict))
    hints.extend(_check_limit(sparql, var_types, schema_dict, class_counts))
    hints.extend(_check_uncertainty_flags(sparql, triples, var_types, schema_dict))

    return hints


def _check_literal_datatypes(
    triples: list[tuple],
    var_types: dict[str, list[str]],
    schema_dict: dict,
) -> list[str]:
    """Detect literal type mismatches in triple patterns."""
    hints = []
    for s, p, o in triples:
        if not isinstance(p, URIRef) or not isinstance(s, Variable):
            continue
        if not isinstance(o, Literal):
            continue
        pred_uri = str(p)
        s_name = str(s)
        for class_uri in var_types.get(s_name, []):
            if class_uri not in schema_dict:
                continue
            pred_info = schema_dict[class_uri].get(pred_uri)
            if not isinstance(pred_info, dict):
                continue
            expected_dt = pred_info.get("datatype")
            if not expected_dt:
                continue
            actual_dt = str(o.datatype) if o.datatype else None
            if actual_dt and actual_dt != expected_dt:
                pred_local = _local_name(pred_uri)
                expected_local = _local_name(expected_dt)
                actual_local = _local_name(actual_dt)
                hints.append(
                    f"Hint: '{pred_local}' expects {expected_local} but got {actual_local}. "
                    f"Example: use -63 (integer) instead of \"63 BC\" (string)."
                )
            elif not actual_dt and expected_dt.endswith("integer"):
                try:
                    int(str(o))
                except ValueError:
                    pred_local = _local_name(pred_uri)
                    hints.append(
                        f"Hint: '{pred_local}' expects xsd:integer but got string \"{o}\". "
                        f"Use an integer value (negative for BC, e.g., -63)."
                    )
    return hints


def _check_open_world_booleans(
    sparql: str,
    triples: list[tuple],
    var_types: dict[str, list[str]],
    schema_dict: dict,
) -> list[str]:
    """Detect FILTER(?var = false) on open-world boolean properties."""
    hints = []
    false_pattern = re.compile(
        r"FILTER\s*\(\s*\?(\w+)\s*=\s*(?:false|\"false\")", re.IGNORECASE
    )
    for match in false_pattern.finditer(sparql):
        var_name = match.group(1)
        for s, p, o in triples:
            if isinstance(o, Variable) and str(o) == var_name and isinstance(s, Variable) and isinstance(p, URIRef):
                pred_uri = str(p)
                s_name = str(s)
                for class_uri in var_types.get(s_name, []):
                    if class_uri not in schema_dict:
                        continue
                    pred_info = schema_dict[class_uri].get(pred_uri)
                    if isinstance(pred_info, dict) and pred_info.get("open_world"):
                        pred_local = _local_name(pred_uri)
                        hints.append(
                            f"Hint: '{pred_local}' only stores true values (open-world boolean). "
                            f"FILTER(?{var_name} = false) returns 0 rows. "
                            f"Use: FILTER NOT EXISTS {{ ?{s_name} <{pred_uri}> true }}"
                        )
    return hints


def _check_count_distinct(
    sparql: str,
    var_types: dict[str, list[str]],
    schema_dict: dict,
) -> list[str]:
    """Detect COUNT(?var) without DISTINCT on classes marked count_distinct."""
    hints = []
    count_pattern = re.compile(r"COUNT\s*\(\s*(?!DISTINCT\b)\?(\w+)\s*\)", re.IGNORECASE)
    for match in count_pattern.finditer(sparql):
        var_name = match.group(1)
        for class_uri in var_types.get(var_name, []):
            if class_uri not in schema_dict:
                continue
            meta = schema_dict[class_uri].get("_meta", {})
            if meta.get("count_distinct"):
                class_local = _local_name(class_uri)
                hints.append(
                    f"Hint: {class_local} can have multiple rows per entity (e.g. one per source). "
                    f"Use COUNT(DISTINCT ?{var_name}) instead of COUNT(?{var_name})."
                )
    return hints


def _check_limit(
    sparql: str,
    var_types: dict[str, list[str]],
    schema_dict: dict,
    class_counts: dict[str, int] | None,
) -> list[str]:
    """Warn when SELECT has no LIMIT and target class has many instances."""
    hints = []
    if class_counts is None:
        return hints
    sparql_upper = sparql.upper()
    if "LIMIT" in sparql_upper or "COUNT" in sparql_upper or "ASK" in sparql_upper:
        return hints
    max_count = 0
    max_class = ""
    for var_name, types in var_types.items():
        for class_uri in types:
            count = class_counts.get(class_uri, 0)
            if count > max_count:
                max_count = count
                max_class = _local_name(class_uri)
    if max_count > 1000:
        hints.append(
            f"Hint: Query targets {max_class} (~{max_count:,} instances) with no LIMIT. "
            f"Consider adding LIMIT 100 for exploration, or use COUNT/GROUP BY for aggregation."
        )
    return hints


def _check_uncertainty_flags(
    sparql: str,
    triples: list[tuple],
    var_types: dict[str, list[str]],
    schema_dict: dict,
) -> list[str]:
    """Suggest surfacing uncertainty flags when querying assertion classes."""
    hints = []
    used_preds: set[str] = set()
    for s, p, o in triples:
        if isinstance(p, URIRef):
            used_preds.add(str(p))
    # Also capture URIs used inside FILTER NOT EXISTS / FILTER EXISTS blocks,
    # which are not returned by _collect_triples.
    for uri_match in re.finditer(r"<([^>]+)>", sparql):
        used_preds.add(uri_match.group(1))
    # Expand prefixed names from PREFIX declarations in the query.
    inline_prefixes: dict[str, str] = {}
    for pm in re.finditer(r"PREFIX\s+(\w+)\s*:\s*<([^>]+)>", sparql, re.IGNORECASE):
        inline_prefixes[pm.group(1)] = pm.group(2)
    for pm in re.finditer(r"\b(\w+):(\w+)\b", sparql):
        prefix, local = pm.group(1), pm.group(2)
        if prefix in inline_prefixes:
            used_preds.add(inline_prefixes[prefix] + local)

    seen_classes: set[str] = set()
    for var_name, types in var_types.items():
        for class_uri in types:
            if class_uri in seen_classes or class_uri not in schema_dict:
                continue
            seen_classes.add(class_uri)
            flags = []
            for pred_uri, pred_info in schema_dict[class_uri].items():
                if pred_uri == "_meta":
                    continue
                if isinstance(pred_info, dict) and pred_info.get("open_world") and pred_uri not in used_preds:
                    flags.append(_local_name(pred_uri))
            if flags:
                class_local = _local_name(class_uri)
                hints.append(
                    f"Hint: {class_local} has uncertainty flags not in your query: "
                    f"{', '.join(flags)}. Consider OPTIONAL {{ ?{var_name} ... }} to surface them, "
                    f"or FILTER NOT EXISTS {{ ... true }} to exclude uncertain data."
                )
    return hints


def validate_and_execute(
    sparql: str,
    store,
    schema_dict: dict,
    prefix_map: dict[str, str],
    dataset: str | None = None,
) -> QueryResult:
    """Validate and execute a SPARQL query through all three tiers."""
    t0 = time.monotonic()
    fixed_sparql, parse_errors = parse_and_fix_prefixes(sparql, prefix_map)
    if parse_errors:
        return QueryResult(success=False, sparql=fixed_sparql, errors=parse_errors)

    # Semantic hints are non-blocking — unknown classes/predicates are warnings, not errors
    semantic_hints = validate_semantics(fixed_sparql, schema_dict)

    try:
        from linked_past.core.store import execute_query

        # Compress result URIs: dataset prefixes + query-declared prefixes (query wins on conflict)
        result_prefixes = dict(prefix_map)
        for match in re.finditer(r"PREFIX\s+(\w+):\s*<([^>]+)>", fixed_sparql, re.IGNORECASE):
            result_prefixes[match.group(1)] = match.group(2)
        rows = execute_query(store, fixed_sparql, prefix_map=result_prefixes)
    except Exception as e:
        return QueryResult(success=False, sparql=fixed_sparql, errors=[f"Query execution error: {e}"])

    # Empty-result diagnostics
    if not rows:
        diagnostics = diagnose_empty_result(
            fixed_sparql, store, schema_dict, prefix_map,
            dataset=dataset,
            semantic_hints=semantic_hints,
        )
        log_zero_result(
            dataset=dataset,
            sparql=fixed_sparql,
            diagnostics=diagnostics,
            semantic_hints=semantic_hints,
            duration_ms=int((time.monotonic() - t0) * 1000),
        )
        semantic_hints.extend(diagnostics.hints)

    return QueryResult(success=True, sparql=fixed_sparql, rows=rows, errors=semantic_hints)
