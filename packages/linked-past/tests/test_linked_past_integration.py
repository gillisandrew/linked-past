# tests/test_linked_past_integration.py
"""End-to-end integration test for the linked-past server with DPRR plugin."""

import json

from linked_past.core.validate import parse_and_fix_prefixes, validate_and_execute


def test_discover_lists_dprr(patched_app_context):
    datasets = patched_app_context.registry.list_datasets()
    assert "dprr" in datasets


def test_get_schema_has_classes(patched_app_context):
    plugin = patched_app_context.registry.get_plugin("dprr")
    schema = plugin.get_schema()
    assert "Person" in schema
    assert "PostAssertion" in schema
    assert "PREFIX dprr:" in schema


def test_validate_valid_query(patched_app_context):
    plugin = patched_app_context.registry.get_plugin("dprr")
    prefix_map = plugin.get_prefixes()
    sparql = (
        "PREFIX dprr: <http://romanrepublic.ac.uk/rdf/ontology#>\n"
        "SELECT ?p ?name WHERE { ?p a dprr:Person ; dprr:hasPersonName ?name }"
    )
    fixed, errors = parse_and_fix_prefixes(sparql, prefix_map)
    assert errors == []
    result = plugin.validate(fixed)
    assert result.valid is True


def test_validate_unknown_class_is_warning(patched_app_context):
    """Unknown classes are non-blocking warnings --- query still validates."""
    plugin = patched_app_context.registry.get_plugin("dprr")
    sparql = (
        "PREFIX dprr: <http://romanrepublic.ac.uk/rdf/ontology#>\n"
        "SELECT ?p WHERE { ?p a dprr:FakeClass }"
    )
    result = plugin.validate(sparql)
    assert result.valid is True  # Warning only, not an error


def test_execute_query_returns_results(patched_app_context):
    store = patched_app_context.registry.get_store("dprr")
    plugin = patched_app_context.registry.get_plugin("dprr")
    sparql = (
        "PREFIX dprr: <http://romanrepublic.ac.uk/rdf/ontology#>\n"
        "SELECT ?name WHERE { ?p a dprr:Person ; dprr:hasPersonName ?name }"
    )
    result = validate_and_execute(sparql, store, plugin.build_schema_dict(), plugin.get_prefixes())
    assert result.success is True
    assert len(result.rows) == 1
    assert "Brutus" in result.rows[0]["name"]


def test_execute_with_prefix_repair(patched_app_context):
    store = patched_app_context.registry.get_store("dprr")
    plugin = patched_app_context.registry.get_plugin("dprr")
    sparql = "SELECT ?name WHERE { ?p a dprr:Person ; dprr:hasPersonName ?name }"
    result = validate_and_execute(sparql, store, plugin.build_schema_dict(), plugin.get_prefixes())
    assert result.success is True
    assert len(result.rows) == 1


def test_registry_json_written(patched_app_context, tmp_path, monkeypatch):
    monkeypatch.setenv("LINKED_PAST_DATA_DIR", str(tmp_path))
    registry_path = tmp_path / "registry.json"
    assert registry_path.exists()
    data = json.loads(registry_path.read_text())
    assert "dprr" in data
    assert "version" in data["dprr"]
    assert data["dprr"]["triple_count"] > 0


def test_discover_datasets_topic_filter(patched_app_context):
    plugin = patched_app_context.registry.get_plugin("dprr")
    searchable = [plugin.description, plugin.display_name,
                  plugin.spatial_coverage, plugin.time_coverage]
    assert any("roman" in f.lower() for f in searchable)
    assert not any("medieval" in f.lower() for f in searchable)


def test_query_result_includes_citation(patched_app_context):
    store = patched_app_context.registry.get_store("dprr")
    plugin = patched_app_context.registry.get_plugin("dprr")
    result = validate_and_execute(
        "PREFIX dprr: <http://romanrepublic.ac.uk/rdf/ontology#>\n"
        "SELECT ?name WHERE { ?p a dprr:Person ; dprr:hasPersonName ?name }",
        store, plugin.build_schema_dict(), plugin.get_prefixes(),
    )
    assert result.success is True
    meta = patched_app_context.registry.get_metadata("dprr")
    assert "version" in meta
    assert plugin.citation != ""
