"""Integration tests using sample data."""
import tempfile
from pathlib import Path

from dprr_tool.store import get_or_create_store, load_rdf
from dprr_tool.context import load_prefixes, load_schemas
from dprr_tool.validate import build_schema_dict, validate_and_execute
from tests.test_store import SAMPLE_TURTLE


def _setup_store():
    tmpdir = tempfile.mkdtemp()
    store_path = Path(tmpdir) / "store"
    store = get_or_create_store(store_path)
    ttl_path = Path(tmpdir) / "test.ttl"
    ttl_path.write_text(SAMPLE_TURTLE)
    load_rdf(store, ttl_path)
    return store


def test_full_validation_pipeline_with_valid_query():
    store = _setup_store()
    prefixes = load_prefixes()
    sd = build_schema_dict(load_schemas(), prefixes)
    sparql = "PREFIX vocab: <http://romanrepublic.ac.uk/rdf/entity/vocab/>\nSELECT DISTINCT ?person ?name WHERE {\n    ?person a vocab:Person ;\n        vocab:hasPersonName ?name .\n}\nLIMIT 100"
    result = validate_and_execute(sparql, store, sd, prefixes)
    assert result.success
    assert len(result.rows) == 2


def test_full_validation_pipeline_with_missing_prefix():
    store = _setup_store()
    prefixes = load_prefixes()
    sd = build_schema_dict(load_schemas(), prefixes)
    sparql = "SELECT DISTINCT ?person ?name WHERE {\n    ?person a vocab:Person ;\n        vocab:hasPersonName ?name .\n}"
    result = validate_and_execute(sparql, store, sd, prefixes)
    assert result.success
    assert len(result.rows) == 2
    assert "PREFIX" in result.sparql


def test_full_validation_catches_bad_predicate():
    store = _setup_store()
    prefixes = load_prefixes()
    sd = build_schema_dict(load_schemas(), prefixes)
    sparql = "PREFIX vocab: <http://romanrepublic.ac.uk/rdf/entity/vocab/>\nSELECT ?person WHERE {\n    ?person a vocab:Person ;\n        vocab:hasOffice ?office .\n}"
    result = validate_and_execute(sparql, store, sd, prefixes)
    assert not result.success
    assert any("hasOffice" in e for e in result.errors)


def test_context_rendering_is_nonempty():
    from dprr_tool.context import render_schemas_as_shex, load_schemas
    schemas = load_schemas()
    rendered = render_schemas_as_shex(schemas)
    assert len(rendered) > 500
    assert "vocab:Person" in rendered
    assert "vocab:PostAssertion" in rendered
