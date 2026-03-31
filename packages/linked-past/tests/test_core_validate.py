# tests/test_core_validate.py
from linked_past.core.store import create_store, load_rdf
from linked_past.core.validate import (
    QueryResult,
    build_schema_dict,
    extract_query_classes,
    parse_and_fix_prefixes,
    validate_and_execute,
    validate_semantics,
)

SAMPLE_TURTLE = """\
@prefix ex: <http://example.org/> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
ex:Thing1 a ex:Widget ; rdfs:label "One" .
"""

PREFIXES = {
    "ex": "http://example.org/",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
}

SCHEMAS = {
    "Widget": {
        "label": "Widget",
        "comment": "A widget",
        "uri": "ex:Widget",
        "properties": [
            {"pred": "ex:hasName", "range": "xsd:string"},
            {"pred": "ex:hasColor", "range": "xsd:string"},
        ],
    }
}


def test_parse_valid_query():
    sparql = "PREFIX ex: <http://example.org/>\nSELECT ?w WHERE { ?w a ex:Widget }"
    fixed, errors = parse_and_fix_prefixes(sparql, PREFIXES)
    assert errors == []
    assert fixed == sparql


def test_parse_fixes_missing_prefix():
    sparql = "SELECT ?w WHERE { ?w a ex:Widget }"
    fixed, errors = parse_and_fix_prefixes(sparql, PREFIXES)
    assert errors == []
    assert "PREFIX ex:" in fixed


def test_parse_syntax_error():
    sparql = "SELEC ?w WHERE { ?w a ex:Widget }"
    _, errors = parse_and_fix_prefixes(sparql, PREFIXES)
    assert len(errors) > 0


def test_build_schema_dict():
    sd = build_schema_dict(SCHEMAS, PREFIXES)
    assert "http://example.org/Widget" in sd
    assert "http://example.org/hasName" in sd["http://example.org/Widget"]


def test_extract_query_classes():
    sd = build_schema_dict(SCHEMAS, PREFIXES)
    sparql = "PREFIX ex: <http://example.org/>\nSELECT ?w WHERE { ?w a ex:Widget }"
    classes = extract_query_classes(sparql, sd)
    assert "Widget" in classes


def test_extract_classes_via_predicate():
    sd = build_schema_dict(SCHEMAS, PREFIXES)
    sparql = "PREFIX ex: <http://example.org/>\nSELECT ?w ?n WHERE { ?w ex:hasName ?n }"
    classes = extract_query_classes(sparql, sd)
    assert "Widget" in classes


def test_validate_semantics_valid():
    sd = build_schema_dict(SCHEMAS, PREFIXES)
    sparql = "PREFIX ex: <http://example.org/>\nSELECT ?w WHERE { ?w a ex:Widget ; ex:hasName ?n }"
    errors = validate_semantics(sparql, sd)
    assert errors == []


def test_validate_semantics_unknown_class_is_warning_not_error():
    """Unknown classes are warnings (logged), not errors — datasets use shared vocabularies."""
    sd = build_schema_dict(SCHEMAS, PREFIXES)
    sparql = "PREFIX ex: <http://example.org/>\nSELECT ?w WHERE { ?w a ex:Gadget }"
    errors = validate_semantics(sparql, sd)
    assert errors == []  # No errors — unknown classes are only logged as info


def test_validate_semantics_unknown_predicate_is_warning_not_error():
    """Unknown predicates are warnings (logged), not errors — multi-vocab datasets
    commonly use predicates from shared ontologies not in the schema."""
    sd = build_schema_dict(SCHEMAS, PREFIXES)
    sparql = "PREFIX ex: <http://example.org/>\nSELECT ?w WHERE { ?w a ex:Widget ; ex:hasFlavor ?f }"
    errors = validate_semantics(sparql, sd)
    assert errors == []  # No errors — unknown predicates are only logged as info


def test_query_result_dataclass():
    r = QueryResult(success=True, sparql="SELECT ?s WHERE { ?s ?p ?o }", rows=[{"s": "x"}])
    assert r.success is True
    assert len(r.rows) == 1


def test_validate_and_execute_success(tmp_path):
    store_path = tmp_path / "store"
    store = create_store(store_path)
    ttl = tmp_path / "data.ttl"
    ttl.write_text(SAMPLE_TURTLE)
    load_rdf(store, ttl)
    sd = build_schema_dict(SCHEMAS, PREFIXES)
    result = validate_and_execute(
        "PREFIX ex: <http://example.org/>\nSELECT ?w WHERE { ?w a ex:Widget }",
        store, sd, PREFIXES,
    )
    assert result.success is True
    assert len(result.rows) == 1


def test_validate_and_execute_parse_error(tmp_path):
    store_path = tmp_path / "store"
    store = create_store(store_path)
    result = validate_and_execute("SELEC ?w WHERE { ?w ?p ?o }", store, {}, PREFIXES)
    assert result.success is False
    assert len(result.errors) > 0


def test_validate_and_execute_unknown_class_still_executes(tmp_path):
    """Unknown classes are warnings — query still executes (returns empty results)."""
    store_path = tmp_path / "store"
    store = create_store(store_path)
    ttl = tmp_path / "data.ttl"
    ttl.write_text(SAMPLE_TURTLE)
    load_rdf(store, ttl)
    sd = build_schema_dict(SCHEMAS, PREFIXES)
    result = validate_and_execute(
        "PREFIX ex: <http://example.org/>\nSELECT ?w WHERE { ?w a ex:Gadget }",
        store, sd, PREFIXES,
    )
    assert result.success is True
    assert result.rows == []  # No Gadgets exist, but query ran
