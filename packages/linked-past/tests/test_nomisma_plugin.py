# tests/test_nomisma_plugin.py
from linked_past.datasets.nomisma.plugin import NomismaPlugin


def test_nomisma_plugin_attributes():
    plugin = NomismaPlugin()
    assert plugin.name == "nomisma"
    assert "Nomisma" in plugin.display_name
    assert plugin.license == "CC BY"
    assert plugin.url == "http://nomisma.org"


def test_nomisma_plugin_prefixes():
    plugin = NomismaPlugin()
    prefixes = plugin.get_prefixes()
    assert "nmo" in prefixes
    assert prefixes["nmo"] == "http://nomisma.org/ontology#"


def test_nomisma_plugin_schema():
    plugin = NomismaPlugin()
    schema = plugin.get_schema()
    assert "Person" in schema
    assert "Mint" in schema
    assert "Denomination" in schema


def test_nomisma_plugin_validate_valid():
    plugin = NomismaPlugin()
    result = plugin.validate(
        "PREFIX foaf: <http://xmlns.com/foaf/0.1/>\n"
        "SELECT ?p WHERE { ?p a foaf:Person }",
    )
    assert result.valid is True


def test_nomisma_plugin_validate_invalid():
    plugin = NomismaPlugin()
    result = plugin.validate(
        "PREFIX nmo: <http://nomisma.org/ontology#>\n"
        "SELECT ?p WHERE { ?p a nmo:FakeClass }",
    )
    assert result.valid is True  # Unknown classes are non-blocking warnings
    assert result.valid is True  # Unknown classes are warnings, not errors


def test_nomisma_plugin_get_relevant_context():
    plugin = NomismaPlugin()
    ctx = plugin.get_relevant_context(
        "PREFIX nmo: <http://nomisma.org/ontology#>\n"
        "PREFIX skos: <http://www.w3.org/2004/02/skos/core#>\n"
        "SELECT ?m WHERE { ?m a nmo:Mint ; skos:prefLabel ?label }",
    )
    assert isinstance(ctx, str)
    assert len(ctx) > 0


def test_nomisma_plugin_load(tmp_path):
    from linked_past.core.store import create_store

    plugin = NomismaPlugin()
    ttl = tmp_path / "nomisma.ttl"
    ttl.write_text(
        '@prefix nmo: <http://nomisma.org/ontology#> .\n'
        '@prefix nm: <http://nomisma.org/id/> .\n'
        '@prefix skos: <http://www.w3.org/2004/02/skos/core#> .\n'
        '@prefix foaf: <http://xmlns.com/foaf/0.1/> .\n'
        '@prefix geo: <http://www.w3.org/2003/01/geo/wgs84_pos#> .\n'
        '@prefix org: <http://www.w3.org/ns/org#> .\n'
        '\n'
        'nm:augustus a foaf:Person, skos:Concept ;\n'
        '    skos:prefLabel "Augustus"@en ;\n'
        '    org:hasMembership [ org:role nm:roman_emperor ; org:organization nm:roman_empire ] .\n'
        '\n'
        'nm:rome a nmo:Mint, skos:Concept ;\n'
        '    skos:prefLabel "Rome"@en ;\n'
        '    geo:location [ geo:lat "41.8933"^^<http://www.w3.org/2001/XMLSchema#float> ;\n'
        '                   geo:long "12.4831"^^<http://www.w3.org/2001/XMLSchema#float> ] .\n'
        '\n'
        'nm:denarius a nmo:Denomination, skos:Concept ;\n'
        '    skos:prefLabel "Denarius"@en .\n'
    )
    store = create_store(tmp_path / "store")
    count = plugin.load(store, ttl)
    assert count > 0


def test_nomisma_plugin_oci_attributes():
    plugin = NomismaPlugin()
    assert plugin.oci_dataset == "datasets/nomisma"
    assert plugin.oci_version == "latest"


def test_nomisma_plugin_version_info(tmp_path):
    plugin = NomismaPlugin()
    info = plugin.get_version_info(tmp_path)
    assert info is not None
    assert info.rdf_format == "turtle"
