# tests/test_core_validate.py
from linked_past.core.store import create_store, load_rdf
from linked_past.core.validate import (
    DiagnosticResult,
    QueryResult,
    build_schema_dict,
    diagnose_empty_result,
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


def test_validate_semantics_unknown_class_is_hint_not_error():
    """Unknown classes produce constructive hints, not blocking errors."""
    sd = build_schema_dict(SCHEMAS, PREFIXES)
    sparql = "PREFIX ex: <http://example.org/>\nSELECT ?w WHERE { ?w a ex:Gadget }"
    hints = validate_semantics(sparql, sd)
    assert len(hints) == 1
    assert "Hint:" in hints[0]
    assert "Gadget" in hints[0]
    assert "Widget" in hints[0]  # suggests the correct class


def test_validate_semantics_unknown_predicate_is_hint_not_error():
    """Unknown predicates produce constructive hints, not blocking errors."""
    sd = build_schema_dict(SCHEMAS, PREFIXES)
    sparql = "PREFIX ex: <http://example.org/>\nSELECT ?w WHERE { ?w a ex:Widget ; ex:hasFlavor ?f }"
    hints = validate_semantics(sparql, sd)
    assert len(hints) == 1
    assert "Hint:" in hints[0]
    assert "hasFlavor" in hints[0]


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


def test_build_schema_dict_rich_metadata():
    schemas = {
        "PostAssertion": {
            "uri": "ex:PostAssertion",
            "count_distinct": True,
            "properties": [
                {"pred": "ex:hasDateStart", "range": "xsd:integer"},
                {"pred": "ex:isUncertain", "range": "xsd:boolean", "open_world": True},
                {"pred": "ex:hasOffice", "range": "ex:Office"},
            ],
        },
    }
    sd = build_schema_dict(schemas, PREFIXES)
    pa = sd["http://example.org/PostAssertion"]

    # Keys still work for membership checks (backwards compatible)
    assert "http://example.org/hasDateStart" in pa
    assert "http://example.org/isUncertain" in pa

    # Rich metadata available
    date_info = pa["http://example.org/hasDateStart"]
    assert date_info["ranges"] == ["http://www.w3.org/2001/XMLSchema#integer"]
    assert date_info["datatype"] == "http://www.w3.org/2001/XMLSchema#integer"
    assert date_info.get("open_world") is not True

    uncertain_info = pa["http://example.org/isUncertain"]
    assert uncertain_info["open_world"] is True
    assert uncertain_info["datatype"] == "http://www.w3.org/2001/XMLSchema#boolean"

    office_info = pa["http://example.org/hasOffice"]
    assert office_info["ranges"] == ["http://example.org/Office"]
    assert office_info.get("datatype") is None

    # Class-level metadata
    assert pa["_meta"]["count_distinct"] is True


def test_validate_and_execute_unknown_class_still_executes(tmp_path):
    """Unknown classes produce hints but query still executes (returns empty results)."""
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
    assert result.success is True  # Hints are non-blocking
    assert result.rows == []  # No Gadgets exist, but query ran
    assert len(result.errors) == 1  # Contains a hint about unknown class
    assert "Hint:" in result.errors[0]


def test_validate_infers_type_from_range():
    schemas = {
        "PostAssertion": {
            "uri": "ex:PostAssertion",
            "properties": [
                {"pred": "ex:hasOffice", "range": "ex:Office"},
                {"pred": "ex:isAboutPerson", "range": "ex:Person"},
            ],
        },
        "Office": {
            "uri": "ex:Office",
            "properties": [
                {"pred": "rdfs:label", "range": "xsd:string"},
                {"pred": "ex:hasAbbreviation", "range": "xsd:string"},
            ],
        },
        "Person": {
            "uri": "ex:Person",
            "properties": [
                {"pred": "ex:hasName", "range": "xsd:string"},
            ],
        },
    }
    sd = build_schema_dict(schemas, PREFIXES)
    sparql = (
        "PREFIX ex: <http://example.org/>\n"
        "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n"
        "SELECT ?name WHERE {\n"
        "  ?pa a ex:PostAssertion ; ex:hasOffice ?office .\n"
        "  ?office ex:hasAbbreviation ?abbr .\n"
        "}"
    )
    hints = validate_semantics(sparql, sd)
    assert not any("hasAbbreviation" in h for h in hints)


def test_validate_wrong_predicate_on_inferred_type():
    schemas = {
        "PostAssertion": {
            "uri": "ex:PostAssertion",
            "properties": [
                {"pred": "ex:hasOffice", "range": "ex:Office"},
            ],
        },
        "Office": {
            "uri": "ex:Office",
            "properties": [
                {"pred": "rdfs:label", "range": "xsd:string"},
            ],
        },
    }
    sd = build_schema_dict(schemas, PREFIXES)
    sparql = (
        "PREFIX ex: <http://example.org/>\n"
        "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n"
        "SELECT ?name WHERE {\n"
        "  ?pa a ex:PostAssertion ; ex:hasOffice ?office .\n"
        "  ?office ex:hasName ?name .\n"
        "}"
    )
    hints = validate_semantics(sparql, sd)
    assert any("hasName" in h for h in hints)


def test_validate_predicate_on_wrong_class():
    schemas = {
        "Person": {
            "uri": "ex:Person",
            "properties": [
                {"pred": "ex:hasName", "range": "xsd:string"},
            ],
        },
        "PostAssertion": {
            "uri": "ex:PostAssertion",
            "properties": [
                {"pred": "ex:hasOffice", "range": "ex:Office"},
            ],
        },
    }
    sd = build_schema_dict(schemas, PREFIXES)
    sparql = (
        "PREFIX ex: <http://example.org/>\n"
        "SELECT ?o WHERE { ?p a ex:Person ; ex:hasOffice ?o }"
    )
    hints = validate_semantics(sparql, sd)
    assert any("hasOffice" in h and "Person" in h for h in hints)


def test_join_hint_shows_owner_class():
    schemas = {
        "Person": {
            "uri": "ex:Person",
            "properties": [
                {"pred": "ex:hasName", "range": "xsd:string"},
            ],
        },
        "PostAssertion": {
            "uri": "ex:PostAssertion",
            "properties": [
                {"pred": "ex:hasOffice", "range": "ex:Office"},
            ],
        },
    }
    sd = build_schema_dict(schemas, PREFIXES)
    sparql = (
        "PREFIX ex: <http://example.org/>\n"
        "SELECT ?o WHERE { ?p a ex:Person ; ex:hasOffice ?o }"
    )
    hints = validate_semantics(sparql, sd)
    assert any("PostAssertion" in h for h in hints)


def test_literal_datatype_mismatch():
    schemas = {
        "PostAssertion": {
            "uri": "ex:PostAssertion",
            "properties": [
                {"pred": "ex:hasDateStart", "range": "xsd:integer"},
            ],
        },
    }
    sd = build_schema_dict(schemas, PREFIXES)
    sparql = (
        "PREFIX ex: <http://example.org/>\n"
        'SELECT ?pa WHERE { ?pa a ex:PostAssertion ; ex:hasDateStart "63 BC" }'
    )
    hints = validate_semantics(sparql, sd)
    assert any("integer" in h.lower() for h in hints)


def test_literal_datatype_correct():
    schemas = {
        "PostAssertion": {
            "uri": "ex:PostAssertion",
            "properties": [
                {"pred": "ex:hasDateStart", "range": "xsd:integer"},
            ],
        },
    }
    sd = build_schema_dict(schemas, PREFIXES)
    sparql = (
        "PREFIX ex: <http://example.org/>\n"
        "SELECT ?pa WHERE { ?pa a ex:PostAssertion ; ex:hasDateStart -63 }"
    )
    hints = validate_semantics(sparql, sd)
    assert not any("integer" in h.lower() for h in hints)


def test_open_world_boolean_hint():
    schemas = {
        "Person": {
            "uri": "ex:Person",
            "properties": [
                {"pred": "ex:isPatrician", "range": "xsd:boolean", "open_world": True},
            ],
        },
    }
    sd = build_schema_dict(schemas, PREFIXES)
    sparql = (
        "PREFIX ex: <http://example.org/>\n"
        "SELECT ?p WHERE { ?p a ex:Person ; ex:isPatrician ?v . FILTER(?v = false) }"
    )
    hints = validate_semantics(sparql, sd)
    assert any("open-world" in h and "FILTER NOT EXISTS" in h for h in hints)


def test_open_world_no_false_positive():
    schemas = {
        "Person": {
            "uri": "ex:Person",
            "properties": [
                {"pred": "ex:isPatrician", "range": "xsd:boolean", "open_world": True},
            ],
        },
    }
    sd = build_schema_dict(schemas, PREFIXES)
    sparql = (
        "PREFIX ex: <http://example.org/>\n"
        "SELECT ?p WHERE { ?p a ex:Person ; ex:isPatrician true }"
    )
    hints = validate_semantics(sparql, sd)
    assert not any("open-world" in h for h in hints)


def test_count_distinct_hint():
    schemas = {
        "PostAssertion": {
            "uri": "ex:PostAssertion",
            "count_distinct": True,
            "properties": [
                {"pred": "ex:isAboutPerson", "range": "ex:Person"},
            ],
        },
    }
    sd = build_schema_dict(schemas, PREFIXES)
    sparql = (
        "PREFIX ex: <http://example.org/>\n"
        "SELECT (COUNT(?pa) AS ?n) WHERE { ?pa a ex:PostAssertion }"
    )
    hints = validate_semantics(sparql, sd)
    assert any("COUNT(DISTINCT" in h for h in hints)


def test_count_distinct_no_false_positive():
    schemas = {
        "PostAssertion": {
            "uri": "ex:PostAssertion",
            "count_distinct": True,
            "properties": [],
        },
    }
    sd = build_schema_dict(schemas, PREFIXES)
    sparql = (
        "PREFIX ex: <http://example.org/>\n"
        "SELECT (COUNT(DISTINCT ?pa) AS ?n) WHERE { ?pa a ex:PostAssertion }"
    )
    hints = validate_semantics(sparql, sd)
    assert not any("COUNT(DISTINCT" in h for h in hints)


def test_limit_warning():
    schemas = {
        "Person": {
            "uri": "ex:Person",
            "properties": [],
        },
    }
    sd = build_schema_dict(schemas, PREFIXES)
    class_counts = {"http://example.org/Person": 5000}
    sparql = (
        "PREFIX ex: <http://example.org/>\n"
        "SELECT ?p WHERE { ?p a ex:Person }"
    )
    hints = validate_semantics(sparql, sd, class_counts=class_counts)
    assert any("LIMIT" in h and "5,000" in h for h in hints)


def test_limit_no_warning_when_present():
    schemas = {
        "Person": {
            "uri": "ex:Person",
            "properties": [],
        },
    }
    sd = build_schema_dict(schemas, PREFIXES)
    class_counts = {"http://example.org/Person": 5000}
    sparql = (
        "PREFIX ex: <http://example.org/>\n"
        "SELECT ?p WHERE { ?p a ex:Person } LIMIT 100"
    )
    hints = validate_semantics(sparql, sd, class_counts=class_counts)
    assert not any("LIMIT" in h for h in hints)


def test_uncertainty_flags_hint():
    schemas = {
        "PostAssertion": {
            "uri": "ex:PostAssertion",
            "properties": [
                {"pred": "ex:hasOffice", "range": "ex:Office"},
                {"pred": "ex:isUncertain", "range": "xsd:boolean", "open_world": True},
                {"pred": "ex:isDateUncertain", "range": "xsd:boolean", "open_world": True},
            ],
        },
    }
    sd = build_schema_dict(schemas, PREFIXES)
    sparql = (
        "PREFIX ex: <http://example.org/>\n"
        "SELECT ?pa WHERE { ?pa a ex:PostAssertion ; ex:hasOffice ?o }"
    )
    hints = validate_semantics(sparql, sd)
    assert any("uncertainty" in h.lower() and "isUncertain" in h for h in hints)


def test_diagnose_empty_result_returns_dataclass(tmp_path):
    store_path = tmp_path / "store"
    store = create_store(store_path)
    ttl = tmp_path / "data.ttl"
    ttl.write_text(SAMPLE_TURTLE)
    load_rdf(store, ttl)
    sd = build_schema_dict(SCHEMAS, PREFIXES)
    sparql = "PREFIX ex: <http://example.org/>\nSELECT ?w WHERE { ?w a ex:Gadget }"
    result = diagnose_empty_result(sparql, store, sd, PREFIXES)
    assert isinstance(result, DiagnosticResult)
    assert isinstance(result.hints, list)
    assert isinstance(result.probe_results, dict)


def test_uncertainty_flags_no_hint_when_used():
    schemas = {
        "PostAssertion": {
            "uri": "ex:PostAssertion",
            "properties": [
                {"pred": "ex:hasOffice", "range": "ex:Office"},
                {"pred": "ex:isUncertain", "range": "xsd:boolean", "open_world": True},
            ],
        },
    }
    sd = build_schema_dict(schemas, PREFIXES)
    sparql = (
        "PREFIX ex: <http://example.org/>\n"
        "SELECT ?pa WHERE { ?pa a ex:PostAssertion ; ex:hasOffice ?o . "
        "FILTER NOT EXISTS { ?pa ex:isUncertain true } }"
    )
    hints = validate_semantics(sparql, sd)
    assert not any("uncertainty" in h.lower() for h in hints)
