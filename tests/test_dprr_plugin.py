# tests/test_dprr_plugin.py
from linked_past.datasets.dprr.plugin import DPRRPlugin


def test_dprr_plugin_attributes():
    plugin = DPRRPlugin()
    assert plugin.name == "dprr"
    assert "Roman Republic" in plugin.display_name
    assert plugin.license == "CC BY-NC 4.0"
    assert plugin.url == "https://romanrepublic.ac.uk"


def test_dprr_plugin_prefixes():
    plugin = DPRRPlugin()
    prefixes = plugin.get_prefixes()
    assert "vocab" in prefixes
    assert prefixes["vocab"] == "http://romanrepublic.ac.uk/rdf/ontology#"


def test_dprr_plugin_schema():
    plugin = DPRRPlugin()
    schema = plugin.get_schema()
    assert "Person" in schema
    assert "PostAssertion" in schema


def test_dprr_plugin_validate_valid():
    plugin = DPRRPlugin()
    result = plugin.validate(
        "PREFIX vocab: <http://romanrepublic.ac.uk/rdf/ontology#>\n"
        "SELECT ?p WHERE { ?p a vocab:Person }",
    )
    assert result.valid is True


def test_dprr_plugin_validate_invalid():
    plugin = DPRRPlugin()
    result = plugin.validate(
        "PREFIX vocab: <http://romanrepublic.ac.uk/rdf/ontology#>\n"
        "SELECT ?p WHERE { ?p a vocab:FakeClass }",
    )
    assert result.valid is False
    assert any("Unknown class" in e for e in result.errors)


def test_dprr_plugin_get_relevant_context():
    plugin = DPRRPlugin()
    ctx = plugin.get_relevant_context(
        "PREFIX vocab: <http://romanrepublic.ac.uk/rdf/ontology#>\n"
        "SELECT ?p WHERE { ?p a vocab:Person ; vocab:hasPersonName ?n }",
    )
    assert isinstance(ctx, str)
    assert len(ctx) > 0


def test_dprr_plugin_load(tmp_path):
    from linked_past.core.store import create_store

    plugin = DPRRPlugin()
    ttl = tmp_path / "dprr.ttl"
    ttl.write_text(
        '@prefix vocab: <http://romanrepublic.ac.uk/rdf/ontology#> .\n'
        '<http://romanrepublic.ac.uk/rdf/entity/Person/1> a vocab:Person .\n'
    )
    store = create_store(tmp_path / "store")
    count = plugin.load(store, ttl)
    assert count > 0


def test_dprr_plugin_version_info(tmp_path):
    plugin = DPRRPlugin()
    info = plugin.get_version_info(tmp_path)
    assert info is not None
    assert info.rdf_format == "turtle"
