import pytest

from dprr_mcp.context import load_prefixes, load_schemas
from dprr_mcp.store import get_or_create_store, load_rdf
from dprr_mcp.validate import (
    ValidationResult,
    _local_name,
    _suggest,
    build_schema_dict,
    parse_and_fix_prefixes,
    validate_and_execute,
    validate_semantics,
)
from tests.test_store import SAMPLE_TURTLE

PREFIXES = load_prefixes()


def _make_schema_dict():
    return build_schema_dict(load_schemas(), PREFIXES)


# --- _local_name helper ---

def test_local_name_hash_uri():
    """Hash URIs extract the fragment, not path + fragment."""
    assert _local_name("http://www.w3.org/2000/01/rdf-schema#label") == "label"
    assert _local_name("http://www.w3.org/1999/02/22-rdf-syntax-ns#type") == "type"


def test_local_name_slash_uri():
    """Slash URIs extract the last path segment."""
    assert _local_name("http://romanrepublic.ac.uk/rdf/ontology#Person") == "Person"
    assert _local_name("http://romanrepublic.ac.uk/rdf/ontology#hasOffice") == "hasOffice"


# --- Tier 1: Syntax + prefix repair ---

def test_parse_valid_query():
    sparql = "PREFIX vocab: <http://romanrepublic.ac.uk/rdf/ontology#>\nSELECT ?person ?name WHERE {\n    ?person a vocab:Person ;\n        vocab:hasPersonName ?name .\n}"
    fixed, errors = parse_and_fix_prefixes(sparql, PREFIXES)
    assert errors == []
    assert fixed == sparql

def test_parse_fixes_missing_prefix():
    sparql = "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\nSELECT ?person ?name WHERE {\n    ?person a vocab:Person ;\n        vocab:hasPersonName ?name .\n}"
    fixed, errors = parse_and_fix_prefixes(sparql, PREFIXES)
    assert errors == []
    assert "PREFIX vocab:" in fixed

def test_parse_fixes_multiple_missing_prefixes():
    sparql = "SELECT ?person ?name WHERE {\n    ?person a vocab:Person ;\n        rdfs:label ?name .\n}"
    fixed, errors = parse_and_fix_prefixes(sparql, PREFIXES)
    assert errors == []
    assert "PREFIX vocab:" in fixed
    assert "PREFIX rdfs:" in fixed



def test_parse_returns_syntax_error():
    sparql = "SELCT ?person WHERE { ?person ?p ?o }"
    fixed, errors = parse_and_fix_prefixes(sparql, PREFIXES)
    assert len(errors) > 0

def test_parse_preserves_comments():
    sparql = "# Find all persons\nPREFIX vocab: <http://romanrepublic.ac.uk/rdf/ontology#>\nSELECT ?name WHERE {\n    ?person a vocab:Person ;\n        vocab:hasPersonName ?name .\n}"
    fixed, errors = parse_and_fix_prefixes(sparql, PREFIXES)
    assert errors == []
    assert "# Find all persons" in fixed

# --- Tier 2: Semantic validation ---

def test_build_schema_dict():
    sd = _make_schema_dict()
    person_uri = "http://romanrepublic.ac.uk/rdf/ontology#Person"
    assert person_uri in sd
    nomen_uri = "http://romanrepublic.ac.uk/rdf/ontology#hasNomen"
    assert nomen_uri in sd[person_uri]

def test_validate_semantics_valid_query():
    sd = _make_schema_dict()
    sparql = "PREFIX vocab: <http://romanrepublic.ac.uk/rdf/ontology#>\nSELECT ?person ?name WHERE {\n    ?person a vocab:Person ;\n        vocab:hasPersonName ?name ;\n        vocab:hasNomen \"Cornelius\" .\n}"
    errors = validate_semantics(sparql, sd)
    assert errors == []

def test_validate_semantics_invalid_predicate():
    sd = _make_schema_dict()
    sparql = "PREFIX vocab: <http://romanrepublic.ac.uk/rdf/ontology#>\nSELECT ?person WHERE {\n    ?person a vocab:Person ;\n        vocab:hasOffice ?office .\n}"
    errors = validate_semantics(sparql, sd)
    assert len(errors) > 0
    assert "hasOffice" in errors[0]

def test_validate_semantics_invalid_class():
    sd = _make_schema_dict()
    sparql = "PREFIX vocab: <http://romanrepublic.ac.uk/rdf/ontology#>\nSELECT ?x WHERE {\n    ?x a vocab:NonexistentClass .\n}"
    errors = validate_semantics(sparql, sd)
    assert len(errors) > 0
    assert "NonexistentClass" in errors[0]

# --- Tier 3: validate_and_execute ---

@pytest.fixture
def test_store(tmp_path):
    store_path = tmp_path / "store"
    store = get_or_create_store(store_path)
    ttl_path = tmp_path / "test.ttl"
    ttl_path.write_text(SAMPLE_TURTLE)
    load_rdf(store, ttl_path)
    return store

def test_validate_and_execute_success(test_store):
    sd = _make_schema_dict()
    sparql = "PREFIX vocab: <http://romanrepublic.ac.uk/rdf/ontology#>\nSELECT ?person ?name WHERE {\n    ?person a vocab:Person ;\n        vocab:hasPersonName ?name .\n}"
    result = validate_and_execute(sparql, test_store, sd, PREFIXES)
    assert result.success
    assert len(result.rows) == 2
    assert result.errors == []

def test_validate_and_execute_fixes_prefix(test_store):
    sd = _make_schema_dict()
    sparql = "SELECT ?person ?name WHERE {\n    ?person a vocab:Person ;\n        vocab:hasPersonName ?name .\n}"
    result = validate_and_execute(sparql, test_store, sd, PREFIXES)
    assert result.success
    assert "PREFIX vocab:" in result.sparql
    assert len(result.rows) == 2

def test_validate_and_execute_returns_semantic_errors(test_store):
    sd = _make_schema_dict()
    sparql = "PREFIX vocab: <http://romanrepublic.ac.uk/rdf/ontology#>\nSELECT ?person WHERE {\n    ?person a vocab:Person ;\n        vocab:hasOffice ?office .\n}"
    result = validate_and_execute(sparql, test_store, sd, PREFIXES)
    assert not result.success
    assert len(result.errors) > 0
    assert "hasOffice" in result.errors[0]

def test_validation_result_fields():
    result = ValidationResult(success=True, sparql="SELECT ...", rows=[{"a": "1"}], errors=[])
    assert result.success
    assert result.sparql == "SELECT ..."
    assert result.rows == [{"a": "1"}]


# --- Fuzzy-match suggestions ---

def test_suggest_close_typo():
    """A close typo produces 'Did you mean' suggestions."""
    result = _suggest("Persn", ["Person", "PostAssertion", "StatusAssertion"])
    assert "Did you mean" in result
    assert "Person" in result


def test_suggest_no_match():
    """A completely wrong name produces no suggestion."""
    result = _suggest("Xyzzy", ["Person", "PostAssertion", "StatusAssertion"])
    assert result == ""


def test_validate_semantics_unknown_class_suggests():
    """Unknown class error includes fuzzy-match suggestion for close typos."""
    sd = _make_schema_dict()
    sparql = "PREFIX vocab: <http://romanrepublic.ac.uk/rdf/ontology#>\nSELECT ?x WHERE {\n    ?x a vocab:Persn .\n}"
    errors = validate_semantics(sparql, sd)
    assert len(errors) > 0
    assert "Did you mean" in errors[0]
    assert "Person" in errors[0]


def test_validate_semantics_unknown_class_no_suggestion():
    """Unknown class error omits suggestion when no close match exists."""
    sd = _make_schema_dict()
    sparql = "PREFIX vocab: <http://romanrepublic.ac.uk/rdf/ontology#>\nSELECT ?x WHERE {\n    ?x a vocab:Xyzzy .\n}"
    errors = validate_semantics(sparql, sd)
    assert len(errors) > 0
    assert "Did you mean" not in errors[0]


def test_validate_semantics_unknown_predicate_suggests():
    """Unknown predicate error includes fuzzy-match suggestion for close typos."""
    sd = _make_schema_dict()
    sparql = "PREFIX vocab: <http://romanrepublic.ac.uk/rdf/ontology#>\nSELECT ?x ?name WHERE {\n    ?x a vocab:Person ;\n        vocab:hasPersonNam ?name .\n}"
    errors = validate_semantics(sparql, sd)
    assert len(errors) > 0
    assert "Did you mean" in errors[0]
    assert "hasPersonName" in errors[0]
