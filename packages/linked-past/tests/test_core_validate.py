# tests/test_core_validate.py
import json

from linked_past.core.store import create_store, load_rdf
from linked_past.core.validate import (
    DiagnosticResult,
    QueryResult,
    _check_bc_date_sign,
    _check_boolean_escalation,
    _check_contradictory_types,
    _parse_triples_and_types,
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
    assert any("Gadget" in e for e in result.errors)  # Contains a hint about unknown class
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


# Task 3 tests
def test_heuristic_escalates_open_world_boolean():
    """When pre-execution warned about open-world boolean and result is empty, escalate."""
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
    semantic_hints = [
        "Hint: 'isPatrician' only stores true values (open-world boolean). "
        "FILTER(?v = false) returns 0 rows. "
        "Use: FILTER NOT EXISTS { ?p <http://example.org/isPatrician> true }"
    ]
    result = diagnose_empty_result(sparql, None, sd, PREFIXES, semantic_hints=semantic_hints)
    assert any("open-world" in h.lower() and "likely the cause" in h.lower() for h in result.hints)


def test_heuristic_no_escalation_without_prior_warning():
    """No escalation if pre-execution didn't warn about open-world."""
    schemas = {
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
        "SELECT ?p WHERE { ?p a ex:Person ; ex:hasName ?n . FILTER(?n = \"Nobody\") }"
    )
    result = diagnose_empty_result(sparql, None, sd, PREFIXES, semantic_hints=[])
    assert not any("open-world" in h.lower() for h in result.hints)


# Task 4 tests
def test_heuristic_contradictory_types():
    """Detect when a variable is bound to two incompatible rdf:type classes."""
    schemas = {
        "Person": {
            "uri": "ex:Person",
            "properties": [{"pred": "ex:hasName", "range": "xsd:string"}],
        },
        "PostAssertion": {
            "uri": "ex:PostAssertion",
            "properties": [{"pred": "ex:hasOffice", "range": "xsd:string"}],
        },
    }
    sd = build_schema_dict(schemas, PREFIXES)
    sparql = (
        "PREFIX ex: <http://example.org/>\n"
        "SELECT ?x WHERE { ?x a ex:Person . ?x a ex:PostAssertion }"
    )
    result = diagnose_empty_result(sparql, None, sd, PREFIXES)
    assert any("contradictory" in h.lower() or "both" in h.lower() for h in result.hints)


def test_heuristic_no_contradiction_single_type():
    schemas = {
        "Person": {
            "uri": "ex:Person",
            "properties": [{"pred": "ex:hasName", "range": "xsd:string"}],
        },
    }
    sd = build_schema_dict(schemas, PREFIXES)
    sparql = (
        "PREFIX ex: <http://example.org/>\n"
        "SELECT ?x WHERE { ?x a ex:Person ; ex:hasName ?n }"
    )
    result = diagnose_empty_result(sparql, None, sd, PREFIXES)
    assert not any("contradictory" in h.lower() or "both" in h.lower() for h in result.hints)


# Task 5 tests
def test_heuristic_date_range_positive_on_bc_field():
    """Detect FILTER with positive integer on a field documented as 'Negative = BC'."""
    schemas = {
        "Person": {
            "uri": "ex:Person",
            "properties": [
                {
                    "pred": "ex:hasEraFrom",
                    "range": "xsd:integer",
                    "comment": "Era start. Negative = BC.",
                },
            ],
        },
    }
    sd = build_schema_dict(schemas, PREFIXES)
    sparql = (
        "PREFIX ex: <http://example.org/>\n"
        "SELECT ?p WHERE { ?p a ex:Person ; ex:hasEraFrom ?era . FILTER(?era > 100) }"
    )
    result = diagnose_empty_result(sparql, None, sd, PREFIXES)
    assert any("negative" in h.lower() and "bc" in h.lower() for h in result.hints)


def test_heuristic_date_range_negative_no_warning():
    """No warning when using negative integers on a BC date field."""
    schemas = {
        "Person": {
            "uri": "ex:Person",
            "properties": [
                {
                    "pred": "ex:hasEraFrom",
                    "range": "xsd:integer",
                    "comment": "Era start. Negative = BC.",
                },
            ],
        },
    }
    sd = build_schema_dict(schemas, PREFIXES)
    sparql = (
        "PREFIX ex: <http://example.org/>\n"
        "SELECT ?p WHERE { ?p a ex:Person ; ex:hasEraFrom ?era . FILTER(?era < -100) }"
    )
    result = diagnose_empty_result(sparql, None, sd, PREFIXES)
    assert not any("negative" in h.lower() and "bc" in h.lower() for h in result.hints)


# Task 6 tests
def test_heuristic_gyear_unpadded():
    """Detect unpadded year in FILTER on xsd:gYear predicate."""
    schemas = {
        "TypeSeries": {
            "uri": "ex:TypeSeries",
            "properties": [
                {"pred": "ex:hasStartDate", "range": "xsd:gYear", "comment": "Earliest date"},
            ],
        },
    }
    sd = build_schema_dict(schemas, PREFIXES)
    sparql = (
        "PREFIX ex: <http://example.org/>\n"
        'SELECT ?t WHERE { ?t a ex:TypeSeries ; ex:hasStartDate ?d . FILTER(?d < "-44") }'
    )
    result = diagnose_empty_result(sparql, None, sd, PREFIXES)
    assert any("padded" in h.lower() or "gYear" in h.lower() for h in result.hints)


def test_heuristic_gyear_properly_padded():
    """No warning when year is properly padded."""
    schemas = {
        "TypeSeries": {
            "uri": "ex:TypeSeries",
            "properties": [
                {"pred": "ex:hasStartDate", "range": "xsd:gYear", "comment": "Earliest date"},
            ],
        },
    }
    sd = build_schema_dict(schemas, PREFIXES)
    sparql = (
        "PREFIX ex: <http://example.org/>\n"
        'SELECT ?t WHERE { ?t a ex:TypeSeries ; ex:hasStartDate ?d . FILTER(?d < "-0044"^^xsd:gYear) }'
    )
    result = diagnose_empty_result(sparql, None, sd, PREFIXES)
    assert not any("padded" in h.lower() for h in result.hints)


def test_heuristic_xsd_date_bare_year():
    """Detect bare year comparison on xsd:date predicate (needs full ISO 8601)."""
    schemas = {
        "Event": {
            "uri": "ex:Event",
            "properties": [
                {"pred": "ex:hasDate", "range": "xsd:date", "comment": "Event date"},
            ],
        },
    }
    sd = build_schema_dict(schemas, PREFIXES)
    sparql = (
        "PREFIX ex: <http://example.org/>\n"
        'SELECT ?e WHERE { ?e a ex:Event ; ex:hasDate ?d . FILTER(?d < "-44") }'
    )
    result = diagnose_empty_result(sparql, None, sd, PREFIXES)
    assert any("padded" in h.lower() or "date" in h.lower() for h in result.hints)


def test_heuristic_xsd_date_properly_formatted():
    """No warning when xsd:date is full ISO 8601."""
    schemas = {
        "Event": {
            "uri": "ex:Event",
            "properties": [
                {"pred": "ex:hasDate", "range": "xsd:date", "comment": "Event date"},
            ],
        },
    }
    sd = build_schema_dict(schemas, PREFIXES)
    sparql = (
        "PREFIX ex: <http://example.org/>\n"
        'SELECT ?e WHERE { ?e a ex:Event ; ex:hasDate ?d . FILTER(?d < "-0044-03-15"^^xsd:date) }'
    )
    result = diagnose_empty_result(sparql, None, sd, PREFIXES)
    assert not any("padded" in h.lower() for h in result.hints)


def test_heuristic_xsd_datetime_bare_year():
    """Detect bare year comparison on xsd:dateTime predicate."""
    schemas = {
        "Event": {
            "uri": "ex:Event",
            "properties": [
                {"pred": "ex:hasTimestamp", "range": "xsd:dateTime", "comment": "Event timestamp"},
            ],
        },
    }
    sd = build_schema_dict(schemas, PREFIXES)
    sparql = (
        "PREFIX ex: <http://example.org/>\n"
        'SELECT ?e WHERE { ?e a ex:Event ; ex:hasTimestamp ?d . FILTER(?d < "-44") }'
    )
    result = diagnose_empty_result(sparql, None, sd, PREFIXES)
    assert any("padded" in h.lower() or "dateTime" in h for h in result.hints)


def test_heuristic_xsd_datetime_properly_formatted():
    """No warning when xsd:dateTime is full ISO 8601."""
    schemas = {
        "Event": {
            "uri": "ex:Event",
            "properties": [
                {"pred": "ex:hasTimestamp", "range": "xsd:dateTime", "comment": "Event timestamp"},
            ],
        },
    }
    sd = build_schema_dict(schemas, PREFIXES)
    sparql = (
        "PREFIX ex: <http://example.org/>\n"
        'SELECT ?e WHERE { ?e a ex:Event ; ex:hasTimestamp ?d . FILTER(?d < "-0044-03-15T00:00:00"^^xsd:dateTime) }'
    )
    result = diagnose_empty_result(sparql, None, sd, PREFIXES)
    assert not any("padded" in h.lower() for h in result.hints)


# Task 13 tests
def test_heuristic_string_vs_uri_mismatch():
    """Detect FILTER comparing a URI-range variable to a string literal."""
    schemas = {
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
        'SELECT ?pa WHERE { ?pa a ex:PostAssertion ; ex:hasOffice ?o . FILTER(?o = "consul") }'
    )
    result = diagnose_empty_result(sparql, None, sd, PREFIXES)
    assert any("uri" in h.lower() and "string" in h.lower() for h in result.hints)


def test_heuristic_no_mismatch_string_range():
    """No warning when comparing string-range variable to string literal."""
    schemas = {
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
        'SELECT ?p WHERE { ?p a ex:Person ; ex:hasName ?n . FILTER(?n = "Cicero") }'
    )
    result = diagnose_empty_result(sparql, None, sd, PREFIXES)
    assert not any("uri" in h.lower() and "string" in h.lower() for h in result.hints)


# Task 7 tests — base pattern ASK probe
def test_probe_base_pattern_matches(tmp_path):
    """When base pattern matches but filters exclude all, report filter problem."""
    store_path = tmp_path / "store"
    store = create_store(store_path)
    ttl = tmp_path / "data.ttl"
    ttl.write_text(SAMPLE_TURTLE)
    load_rdf(store, ttl)
    sd = build_schema_dict(SCHEMAS, PREFIXES)
    sparql = (
        "PREFIX ex: <http://example.org/>\n"
        "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n"
        'SELECT ?w WHERE { ?w a ex:Widget ; rdfs:label ?l . FILTER(?l = "Nonexistent") }'
    )
    result = diagnose_empty_result(sparql, store, sd, PREFIXES)
    assert result.probe_results.get("base_pattern_matches") is True
    assert any("filter" in h.lower() for h in result.hints)


def test_probe_base_pattern_no_match(tmp_path):
    """When base pattern itself doesn't match, report pattern problem."""
    store_path = tmp_path / "store"
    store = create_store(store_path)
    ttl = tmp_path / "data.ttl"
    ttl.write_text(SAMPLE_TURTLE)
    load_rdf(store, ttl)
    sd = build_schema_dict(SCHEMAS, PREFIXES)
    sparql = (
        "PREFIX ex: <http://example.org/>\n"
        "SELECT ?w WHERE { ?w a ex:Gadget }"
    )
    result = diagnose_empty_result(sparql, store, sd, PREFIXES)
    assert result.probe_results.get("base_pattern_matches") is False
    assert any("base graph pattern" in h.lower() or "no entities match" in h.lower() for h in result.hints)


def test_strip_filters_nested_parens(tmp_path):
    """_strip_filters_algebra handles nested parentheses in FILTER."""
    store_path = tmp_path / "store"
    store = create_store(store_path)
    ttl = tmp_path / "data.ttl"
    ttl.write_text(SAMPLE_TURTLE)
    load_rdf(store, ttl)
    sd = build_schema_dict(SCHEMAS, PREFIXES)
    sparql = (
        "PREFIX ex: <http://example.org/>\n"
        "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n"
        "SELECT ?w WHERE { ?w a ex:Widget ; rdfs:label ?l . "
        'FILTER(?l = "X" && (?l != "Y" || ?l != "Z")) }'
    )
    result = diagnose_empty_result(sparql, store, sd, PREFIXES)
    assert result.probe_results.get("base_pattern_matches") is True


def test_strip_filters_with_optional(tmp_path):
    """Base pattern ASK should not require OPTIONAL patterns."""
    store_path = tmp_path / "store"
    store = create_store(store_path)
    ttl = tmp_path / "data.ttl"
    ttl.write_text(SAMPLE_TURTLE)
    load_rdf(store, ttl)
    sd = build_schema_dict(SCHEMAS, PREFIXES)
    sparql = (
        "PREFIX ex: <http://example.org/>\n"
        "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n"
        "SELECT ?w ?c WHERE { ?w a ex:Widget . "
        "OPTIONAL { ?w ex:hasColor ?c } "
        'FILTER(?c = "red") }'
    )
    result = diagnose_empty_result(sparql, store, sd, PREFIXES)
    assert result.probe_results.get("base_pattern_matches") is True
    assert any("filter" in h.lower() for h in result.hints)


# Task 8 test — filter isolation
def test_probe_identifies_restrictive_filter(tmp_path):
    """When stripping a specific filter produces results, identify it."""
    store_path = tmp_path / "store"
    store = create_store(store_path)
    ttl = tmp_path / "data.ttl"
    ttl.write_text(SAMPLE_TURTLE)
    load_rdf(store, ttl)
    sd = build_schema_dict(SCHEMAS, PREFIXES)
    sparql = (
        "PREFIX ex: <http://example.org/>\n"
        "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n"
        'SELECT ?w WHERE { ?w a ex:Widget ; rdfs:label ?l . FILTER(?l = "Nonexistent") }'
    )
    result = diagnose_empty_result(sparql, store, sd, PREFIXES)
    assert any("Nonexistent" in h or "filter" in h.lower() for h in result.hints)
    assert any(k.startswith("filter_") for k in result.probe_results)


# Task 9 test — join decomposition
def test_probe_join_decomposition(tmp_path):
    """When base pattern fails, identify which triple pattern has no matches."""
    store_path = tmp_path / "store"
    store = create_store(store_path)
    ttl = tmp_path / "data.ttl"
    ttl.write_text(SAMPLE_TURTLE)
    load_rdf(store, ttl)
    sd = build_schema_dict(SCHEMAS, PREFIXES)
    sparql = (
        "PREFIX ex: <http://example.org/>\n"
        "SELECT ?w ?c WHERE { ?w a ex:Widget ; ex:hasColor ?c }"
    )
    result = diagnose_empty_result(sparql, store, sd, PREFIXES)
    assert result.probe_results.get("base_pattern_matches") is False
    assert any("hasColor" in h for h in result.hints)


def test_probe_budget_exhaustion(tmp_path):
    """With budget_ms=0, no probes should run."""
    store_path = tmp_path / "store"
    store = create_store(store_path)
    ttl = tmp_path / "data.ttl"
    ttl.write_text(SAMPLE_TURTLE)
    load_rdf(store, ttl)
    sd = build_schema_dict(SCHEMAS, PREFIXES)
    sparql = (
        "PREFIX ex: <http://example.org/>\n"
        "SELECT ?w WHERE { ?w a ex:Gadget }"
    )
    result = diagnose_empty_result(sparql, store, sd, PREFIXES, budget_ms=0)
    assert result.probe_results == {}


def test_validate_and_execute_empty_result_diagnostics(tmp_path):
    """validate_and_execute should include diagnostics when result is empty."""
    store_path = tmp_path / "store"
    store = create_store(store_path)
    ttl = tmp_path / "data.ttl"
    ttl.write_text(SAMPLE_TURTLE)
    load_rdf(store, ttl)
    sd = build_schema_dict(SCHEMAS, PREFIXES)
    result = validate_and_execute(
        "PREFIX ex: <http://example.org/>\n"
        "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n"
        'SELECT ?w WHERE { ?w a ex:Widget ; rdfs:label ?l . FILTER(?l = "Nonexistent") }',
        store, sd, PREFIXES,
    )
    assert result.success is True
    assert result.rows == []
    assert any("Diagnostic:" in e for e in result.errors)


def test_log_zero_result_writes_jsonl(tmp_path, monkeypatch):
    """log_zero_result should append a JSON line to the diagnostics file."""
    monkeypatch.setenv("LINKED_PAST_DATA_DIR", str(tmp_path))
    from linked_past.core.validate import log_zero_result
    log_zero_result(
        dataset="dprr",
        sparql="SELECT ?x WHERE { ?x a <http://example.org/Nothing> }",
        diagnostics=DiagnosticResult(
            hints=["Diagnostic: no matches"],
            probe_results={"base_pattern_matches": False},
        ),
        semantic_hints=["Hint: unknown class"],
        duration_ms=42,
    )
    log_file = tmp_path / "diagnostics" / "zero_results.jsonl"
    assert log_file.exists()
    lines = log_file.read_text().strip().split("\n")
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["dataset"] == "dprr"
    assert entry["duration_ms"] == 42
    assert "timestamp" in entry
    assert entry["diagnostics"] == ["Diagnostic: no matches"]
    assert entry["probe_results"] == {"base_pattern_matches": False}


def test_log_zero_result_appends(tmp_path, monkeypatch):
    """Multiple calls should append, not overwrite."""
    monkeypatch.setenv("LINKED_PAST_DATA_DIR", str(tmp_path))
    from linked_past.core.validate import log_zero_result
    diag = DiagnosticResult(hints=[], probe_results={})
    log_zero_result("dprr", "SELECT 1", diag, [], 10)
    log_zero_result("dprr", "SELECT 2", diag, [], 20)
    log_file = tmp_path / "diagnostics" / "zero_results.jsonl"
    lines = log_file.read_text().strip().split("\n")
    assert len(lines) == 2


def test_validate_and_execute_logs_zero_result(tmp_path, monkeypatch):
    """validate_and_execute should log to JSONL when result is empty."""
    data_dir = tmp_path / "data"
    monkeypatch.setenv("LINKED_PAST_DATA_DIR", str(data_dir))
    store_path = tmp_path / "store"
    store = create_store(store_path)
    ttl = tmp_path / "data.ttl"
    ttl.write_text(SAMPLE_TURTLE)
    load_rdf(store, ttl)
    sd = build_schema_dict(SCHEMAS, PREFIXES)
    result = validate_and_execute(
        "PREFIX ex: <http://example.org/>\nSELECT ?w WHERE { ?w a ex:Gadget }",
        store, sd, PREFIXES, dataset="test",
    )
    assert result.rows == []
    log_file = data_dir / "diagnostics" / "zero_results.jsonl"
    assert log_file.exists()
    entry = json.loads(log_file.read_text().strip())
    assert entry["dataset"] == "test"


def test_validate_and_execute_no_log_when_results(tmp_path, monkeypatch):
    """validate_and_execute should NOT log when results are returned."""
    data_dir = tmp_path / "data"
    monkeypatch.setenv("LINKED_PAST_DATA_DIR", str(data_dir))
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
    assert len(result.rows) > 0
    log_file = data_dir / "diagnostics" / "zero_results.jsonl"
    assert not log_file.exists()


# --- Composable checker unit tests ---


def test_check_contradictory_types():
    schema_dict = {
        "http://example.org/Person": {"_meta": {}},
        "http://example.org/Office": {"_meta": {}},
    }
    sparql = (
        "PREFIX ex: <http://example.org/>\n"
        "SELECT ?x WHERE { ?x a ex:Person . ?x a ex:Office }"
    )
    _, var_types, _ = _parse_triples_and_types(sparql)
    hints = _check_contradictory_types(var_types, schema_dict)
    assert any("typed as both" in h for h in hints)


def test_check_bc_date_sign():
    schema_dict = {
        "http://example.org/Person": {
            "http://example.org/hasEra": {
                "comment": "Negative integers for BC dates",
                "ranges": [],
            },
        },
    }
    sparql = (
        "PREFIX ex: <http://example.org/>\n"
        "SELECT ?p WHERE { ?p a ex:Person ; ex:hasEra ?e . FILTER(?e > 100) }"
    )
    _, _, var_preds = _parse_triples_and_types(sparql)
    hints = _check_bc_date_sign(sparql, var_preds, schema_dict)
    assert any("negative" in h.lower() or "BC" in h for h in hints)


def test_check_boolean_escalation():
    hints = _check_boolean_escalation(["open-world boolean warning: ..."])
    assert any("open-world boolean" in h.lower() for h in hints)

    hints = _check_boolean_escalation([])
    assert hints == []

    hints = _check_boolean_escalation(None)
    assert hints == []
