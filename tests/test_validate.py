import tempfile
from pathlib import Path

from dprr_tool.validate import (
    parse_and_fix_prefixes,
    build_schema_dict,
    validate_semantics,
    validate_and_execute,
    ValidationResult,
)
from dprr_tool.context import load_prefixes, load_schemas
from dprr_tool.store import get_or_create_store, load_rdf
from tests.test_store import SAMPLE_TURTLE

PREFIXES = load_prefixes()


def _make_schema_dict():
    return build_schema_dict(load_schemas(), PREFIXES)


# --- Tier 1: Syntax + prefix repair ---

def test_parse_valid_query():
    sparql = "PREFIX vocab: <http://romanrepublic.ac.uk/rdf/entity/vocab/>\nSELECT ?person ?name WHERE {\n    ?person a vocab:Person ;\n        vocab:hasPersonName ?name .\n}"
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
    sparql = "# Find all persons\nPREFIX vocab: <http://romanrepublic.ac.uk/rdf/entity/vocab/>\nSELECT ?name WHERE {\n    ?person a vocab:Person ;\n        vocab:hasPersonName ?name .\n}"
    fixed, errors = parse_and_fix_prefixes(sparql, PREFIXES)
    assert errors == []
    assert "# Find all persons" in fixed

# --- Tier 2: Semantic validation ---

def test_build_schema_dict():
    sd = _make_schema_dict()
    person_uri = "http://romanrepublic.ac.uk/rdf/entity/vocab/Person"
    assert person_uri in sd
    nomen_uri = "http://romanrepublic.ac.uk/rdf/entity/vocab/hasNomen"
    assert nomen_uri in sd[person_uri]

def test_validate_semantics_valid_query():
    sd = _make_schema_dict()
    sparql = "PREFIX vocab: <http://romanrepublic.ac.uk/rdf/entity/vocab/>\nSELECT ?person ?name WHERE {\n    ?person a vocab:Person ;\n        vocab:hasPersonName ?name ;\n        vocab:hasNomen \"Cornelius\" .\n}"
    errors = validate_semantics(sparql, sd)
    assert errors == []

def test_validate_semantics_invalid_predicate():
    sd = _make_schema_dict()
    sparql = "PREFIX vocab: <http://romanrepublic.ac.uk/rdf/entity/vocab/>\nSELECT ?person WHERE {\n    ?person a vocab:Person ;\n        vocab:hasOffice ?office .\n}"
    errors = validate_semantics(sparql, sd)
    assert len(errors) > 0
    assert "hasOffice" in errors[0]

def test_validate_semantics_invalid_class():
    sd = _make_schema_dict()
    sparql = "PREFIX vocab: <http://romanrepublic.ac.uk/rdf/entity/vocab/>\nSELECT ?x WHERE {\n    ?x a vocab:NonexistentClass .\n}"
    errors = validate_semantics(sparql, sd)
    assert len(errors) > 0
    assert "NonexistentClass" in errors[0]

# --- Tier 3: validate_and_execute ---

def _make_test_store():
    tmpdir = tempfile.mkdtemp()
    store_path = Path(tmpdir) / "store"
    store = get_or_create_store(store_path)
    ttl_path = Path(tmpdir) / "test.ttl"
    ttl_path.write_text(SAMPLE_TURTLE)
    load_rdf(store, ttl_path)
    return store

def test_validate_and_execute_success():
    store = _make_test_store()
    sd = _make_schema_dict()
    sparql = "PREFIX vocab: <http://romanrepublic.ac.uk/rdf/entity/vocab/>\nSELECT ?person ?name WHERE {\n    ?person a vocab:Person ;\n        vocab:hasPersonName ?name .\n}"
    result = validate_and_execute(sparql, store, sd, PREFIXES)
    assert result.success
    assert len(result.rows) == 2
    assert result.errors == []

def test_validate_and_execute_fixes_prefix():
    store = _make_test_store()
    sd = _make_schema_dict()
    sparql = "SELECT ?person ?name WHERE {\n    ?person a vocab:Person ;\n        vocab:hasPersonName ?name .\n}"
    result = validate_and_execute(sparql, store, sd, PREFIXES)
    assert result.success
    assert "PREFIX vocab:" in result.sparql
    assert len(result.rows) == 2

def test_validate_and_execute_returns_semantic_errors():
    store = _make_test_store()
    sd = _make_schema_dict()
    sparql = "PREFIX vocab: <http://romanrepublic.ac.uk/rdf/entity/vocab/>\nSELECT ?person WHERE {\n    ?person a vocab:Person ;\n        vocab:hasOffice ?office .\n}"
    result = validate_and_execute(sparql, store, sd, PREFIXES)
    assert not result.success
    assert len(result.errors) > 0
    assert "hasOffice" in result.errors[0]

def test_validation_result_fields():
    result = ValidationResult(success=True, sparql="SELECT ...", rows=[{"a": "1"}], errors=[])
    assert result.success
    assert result.sparql == "SELECT ..."
    assert result.rows == [{"a": "1"}]
