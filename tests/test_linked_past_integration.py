# tests/test_linked_past_integration.py
"""End-to-end integration test for the linked-past server with DPRR plugin."""

import json

import pytest

from linked_past.core.server import build_app_context
from linked_past.core.validate import parse_and_fix_prefixes, validate_and_execute

SAMPLE_TURTLE = """\
@prefix vocab: <http://romanrepublic.ac.uk/rdf/ontology#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

<http://romanrepublic.ac.uk/rdf/entity/Person/1> a vocab:Person ;
    vocab:hasPersonName "IUNI0001 L. Iunius Brutus" ;
    vocab:hasDprrID "IUNI0001" ;
    vocab:hasNomen "Iunius" ;
    vocab:hasCognomen "Brutus" ;
    vocab:isSex <http://romanrepublic.ac.uk/rdf/entity/Sex/Male> ;
    vocab:hasEraFrom "-509"^^xsd:integer .

<http://romanrepublic.ac.uk/rdf/entity/PostAssertion/1> a vocab:PostAssertion ;
    vocab:isAboutPerson <http://romanrepublic.ac.uk/rdf/entity/Person/1> ;
    vocab:hasOffice <http://romanrepublic.ac.uk/rdf/entity/Office/3> ;
    vocab:hasDateStart "-509"^^xsd:integer .

<http://romanrepublic.ac.uk/rdf/entity/Office/3> a vocab:Office ;
    rdfs:label "Office: consul" .

<http://romanrepublic.ac.uk/rdf/entity/Sex/Male> a vocab:Sex ;
    rdfs:label "Sex: Male" .
"""


@pytest.fixture
def integration_ctx(tmp_path, monkeypatch):
    monkeypatch.setenv("LINKED_PAST_DATA_DIR", str(tmp_path))
    dprr_dir = tmp_path / "dprr"
    dprr_dir.mkdir()
    ttl_path = dprr_dir / "dprr.ttl"
    ttl_path.write_text(SAMPLE_TURTLE)
    # Patch fetch so it returns the local file instead of downloading
    monkeypatch.setattr(
        "linked_past.datasets.dprr.plugin.DPRRPlugin.fetch",
        lambda self, data_dir: data_dir / "dprr.ttl",
    )
    # Create minimal TTL files and patch fetch for other plugins
    for dataset in ("pleiades", "periodo", "nomisma"):
        ds_dir = tmp_path / dataset
        ds_dir.mkdir()
        ttl_path = ds_dir / f"{dataset}.ttl"
        ttl_path.write_text("@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n")
    monkeypatch.setattr(
        "linked_past.datasets.pleiades.plugin.PleiadesPlugin.fetch",
        lambda self, data_dir: data_dir / "pleiades.ttl",
    )
    monkeypatch.setattr(
        "linked_past.datasets.periodo.plugin.PeriodOPlugin.fetch",
        lambda self, data_dir: data_dir / "periodo.ttl",
    )
    monkeypatch.setattr(
        "linked_past.datasets.nomisma.plugin.NomismaPlugin.fetch",
        lambda self, data_dir: data_dir / "nomisma.ttl",
    )
    return build_app_context()


def test_discover_lists_dprr(integration_ctx):
    datasets = integration_ctx.registry.list_datasets()
    assert "dprr" in datasets


def test_get_schema_has_classes(integration_ctx):
    plugin = integration_ctx.registry.get_plugin("dprr")
    schema = plugin.get_schema()
    assert "Person" in schema
    assert "PostAssertion" in schema
    assert "PREFIX vocab:" in schema


def test_validate_valid_query(integration_ctx):
    plugin = integration_ctx.registry.get_plugin("dprr")
    prefix_map = plugin.get_prefixes()
    sparql = (
        "PREFIX vocab: <http://romanrepublic.ac.uk/rdf/ontology#>\n"
        "SELECT ?p ?name WHERE { ?p a vocab:Person ; vocab:hasPersonName ?name }"
    )
    fixed, errors = parse_and_fix_prefixes(sparql, prefix_map)
    assert errors == []
    result = plugin.validate(fixed)
    assert result.valid is True


def test_validate_invalid_class(integration_ctx):
    plugin = integration_ctx.registry.get_plugin("dprr")
    sparql = (
        "PREFIX vocab: <http://romanrepublic.ac.uk/rdf/ontology#>\n"
        "SELECT ?p WHERE { ?p a vocab:FakeClass }"
    )
    result = plugin.validate(sparql)
    assert result.valid is False


def test_execute_query_returns_results(integration_ctx):
    store = integration_ctx.registry.get_store("dprr")
    plugin = integration_ctx.registry.get_plugin("dprr")
    sparql = (
        "PREFIX vocab: <http://romanrepublic.ac.uk/rdf/ontology#>\n"
        "SELECT ?name WHERE { ?p a vocab:Person ; vocab:hasPersonName ?name }"
    )
    result = validate_and_execute(sparql, store, plugin.build_schema_dict(), plugin.get_prefixes())
    assert result.success is True
    assert len(result.rows) == 1
    assert "Brutus" in result.rows[0]["name"]


def test_execute_with_prefix_repair(integration_ctx):
    store = integration_ctx.registry.get_store("dprr")
    plugin = integration_ctx.registry.get_plugin("dprr")
    sparql = "SELECT ?name WHERE { ?p a vocab:Person ; vocab:hasPersonName ?name }"
    result = validate_and_execute(sparql, store, plugin.build_schema_dict(), plugin.get_prefixes())
    assert result.success is True
    assert len(result.rows) == 1


def test_registry_json_written(integration_ctx, tmp_path, monkeypatch):
    monkeypatch.setenv("LINKED_PAST_DATA_DIR", str(tmp_path))
    registry_path = tmp_path / "registry.json"
    assert registry_path.exists()
    data = json.loads(registry_path.read_text())
    assert "dprr" in data
    assert "version" in data["dprr"]
    assert data["dprr"]["triple_count"] > 0


def test_discover_datasets_topic_filter(integration_ctx):
    plugin = integration_ctx.registry.get_plugin("dprr")
    searchable = [plugin.description, plugin.display_name,
                  plugin.spatial_coverage, plugin.time_coverage]
    assert any("roman" in f.lower() for f in searchable)
    assert not any("medieval" in f.lower() for f in searchable)


def test_query_result_includes_citation(integration_ctx):
    store = integration_ctx.registry.get_store("dprr")
    plugin = integration_ctx.registry.get_plugin("dprr")
    result = validate_and_execute(
        "PREFIX vocab: <http://romanrepublic.ac.uk/rdf/ontology#>\n"
        "SELECT ?name WHERE { ?p a vocab:Person ; vocab:hasPersonName ?name }",
        store, plugin.build_schema_dict(), plugin.get_prefixes(),
    )
    assert result.success is True
    meta = integration_ctx.registry.get_metadata("dprr")
    assert "version" in meta
    assert plugin.citation != ""
