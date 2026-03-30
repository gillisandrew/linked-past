# tests/test_pleiades_plugin.py
from linked_past.datasets.pleiades.plugin import PleiadesPlugin


def test_pleiades_plugin_attributes():
    plugin = PleiadesPlugin()
    assert plugin.name == "pleiades"
    assert "Pleiades" in plugin.display_name
    assert plugin.license == "CC BY 3.0"
    assert plugin.url == "https://pleiades.stoa.org"


def test_pleiades_plugin_prefixes():
    plugin = PleiadesPlugin()
    prefixes = plugin.get_prefixes()
    assert "pleiades" in prefixes
    assert prefixes["pleiades"] == "https://pleiades.stoa.org/places/vocab#"


def test_pleiades_plugin_schema():
    plugin = PleiadesPlugin()
    schema = plugin.get_schema()
    assert "Place" in schema
    assert "Location" in schema


def test_pleiades_plugin_validate_valid():
    plugin = PleiadesPlugin()
    result = plugin.validate(
        "PREFIX pleiades: <https://pleiades.stoa.org/places/vocab#>\n"
        "SELECT ?p WHERE { ?p a pleiades:Place }",
    )
    assert result.valid is True


def test_pleiades_plugin_validate_invalid():
    plugin = PleiadesPlugin()
    result = plugin.validate(
        "PREFIX pleiades: <https://pleiades.stoa.org/places/vocab#>\n"
        "SELECT ?p WHERE { ?p a pleiades:FakeClass }",
    )
    assert result.valid is False
    assert any("Unknown class" in e for e in result.errors)


def test_pleiades_plugin_get_relevant_context():
    plugin = PleiadesPlugin()
    ctx = plugin.get_relevant_context(
        "PREFIX pleiades: <https://pleiades.stoa.org/places/vocab#>\n"
        "PREFIX geo: <http://www.w3.org/2003/01/geo/wgs84_pos#>\n"
        "SELECT ?p WHERE { ?p a pleiades:Place ; pleiades:hasLocation ?loc . ?loc geo:lat ?lat }",
    )
    assert isinstance(ctx, str)
    assert len(ctx) > 0


def test_pleiades_plugin_load(tmp_path):
    from linked_past.core.store import create_store

    plugin = PleiadesPlugin()
    ttl = tmp_path / "pleiades.ttl"
    ttl.write_text(
        '@prefix pleiades: <https://pleiades.stoa.org/places/vocab#> .\n'
        '@prefix dcterms: <http://purl.org/dc/terms/> .\n'
        '@prefix geo: <http://www.w3.org/2003/01/geo/wgs84_pos#> .\n'
        '\n'
        '<https://pleiades.stoa.org/places/423025> a pleiades:Place ;\n'
        '    dcterms:title "Roma" ;\n'
        '    pleiades:hasLocation <https://pleiades.stoa.org/places/423025/loc1> .\n'
        '\n'
        '<https://pleiades.stoa.org/places/423025/loc1> a pleiades:Location ;\n'
        '    geo:lat "41.891775"^^<http://www.w3.org/2001/XMLSchema#float> ;\n'
        '    geo:long "12.486137"^^<http://www.w3.org/2001/XMLSchema#float> .\n'
    )
    store = create_store(tmp_path / "store")
    count = plugin.load(store, ttl)
    assert count > 0


def test_pleiades_plugin_oci_attributes():
    plugin = PleiadesPlugin()
    assert plugin.oci_dataset == "pleiades"
    assert plugin.oci_version == "latest"


def test_pleiades_plugin_version_info(tmp_path):
    plugin = PleiadesPlugin()
    info = plugin.get_version_info(tmp_path)
    assert info is not None
    assert info.rdf_format == "turtle"
