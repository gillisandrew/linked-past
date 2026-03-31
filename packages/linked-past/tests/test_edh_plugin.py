from linked_past.datasets.edh.plugin import EDHPlugin

SAMPLE_EDH_TURTLE = """\
@prefix epi: <http://edh-www.adw.uni-heidelberg.de/lod/ontology#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix nmo: <http://nomisma.org/ontology#> .
@prefix lawd: <http://lawd.info/ontology/1.0/> .

<http://edh-www.adw.uni-heidelberg.de/edh/inschrift/HD000001> a epi:Inscription ;
    skos:prefLabel "epitaph found at Roma (Latium)"@en ;
    nmo:hasStartDate "0071" ;
    nmo:hasEndDate "0130" ;
    epi:editionText "D(is) M(anibus)"@lat .
"""


def test_edh_plugin_attributes():
    plugin = EDHPlugin()
    assert plugin.name == "edh"
    assert "EDH" in plugin.display_name
    assert plugin.license == "CC BY-SA 4.0"


def test_edh_plugin_prefixes():
    plugin = EDHPlugin()
    prefixes = plugin.get_prefixes()
    assert "epi" in prefixes
    assert "edh" in prefixes
    assert "lawd" in prefixes


def test_edh_plugin_schema():
    plugin = EDHPlugin()
    schema = plugin.get_schema()
    assert "Inscription" in schema
    assert "epi:Inscription" in schema


def test_edh_plugin_validate_valid():
    plugin = EDHPlugin()
    result = plugin.validate(
        "PREFIX epi: <http://edh-www.adw.uni-heidelberg.de/lod/ontology#>\n"
        "PREFIX skos: <http://www.w3.org/2004/02/skos/core#>\n"
        "SELECT ?i ?label WHERE { ?i a epi:Inscription ; skos:prefLabel ?label }",
    )
    assert result.valid is True


def test_edh_plugin_validate_invalid():
    plugin = EDHPlugin()
    result = plugin.validate(
        "PREFIX epi: <http://edh-www.adw.uni-heidelberg.de/lod/ontology#>\n"
        "SELECT ?i WHERE { ?i a epi:Tablet }",
    )
    assert result.valid is True  # Unknown classes are non-blocking warnings


def test_edh_plugin_load(tmp_path):
    from linked_past.core.store import create_store

    plugin = EDHPlugin()
    ttl = tmp_path / "edh_inscriptions.ttl"
    ttl.write_text(SAMPLE_EDH_TURTLE)
    store = create_store(tmp_path / "store")
    count = plugin.load(store, ttl)
    assert count > 0


def test_edh_plugin_oci_attributes():
    plugin = EDHPlugin()
    assert plugin.oci_dataset == "datasets/edh"
    assert plugin.oci_version == "latest"


def test_edh_plugin_version_info(tmp_path):
    plugin = EDHPlugin()
    info = plugin.get_version_info(tmp_path)
    assert info is not None
    assert "edh" in info.source_url
