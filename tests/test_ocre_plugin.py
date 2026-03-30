from linked_past.datasets.ocre.plugin import OCREPlugin

SAMPLE_OCRE_TURTLE = """\
@prefix nmo: <http://nomisma.org/ontology#> .
@prefix nm: <http://nomisma.org/id/> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix void: <http://rdfs.org/ns/void#> .

<http://numismatics.org/ocre/id/ric.1(2).aug.1A> a nmo:TypeSeriesItem, skos:Concept ;
    skos:prefLabel "RIC I (Second Edition) Augustus 1A" ;
    nmo:hasAuthority nm:augustus ;
    nmo:hasDenomination nm:aureus ;
    nmo:hasMint nm:rome ;
    nmo:hasMaterial nm:av ;
    nmo:hasStartDate "-0018"^^xsd:gYear ;
    dcterms:source nm:ric ;
    void:inDataset <http://numismatics.org/ocre/> .
"""


def test_ocre_plugin_attributes():
    plugin = OCREPlugin()
    assert plugin.name == "ocre"
    assert "OCRE" in plugin.display_name
    assert plugin.license == "ODbL 1.0"


def test_ocre_plugin_prefixes():
    plugin = OCREPlugin()
    prefixes = plugin.get_prefixes()
    assert "nmo" in prefixes
    assert "ocre" in prefixes


def test_ocre_plugin_schema():
    plugin = OCREPlugin()
    schema = plugin.get_schema()
    assert "CoinType" in schema
    assert "TypeSeriesItem" in schema


def test_ocre_plugin_validate_valid():
    plugin = OCREPlugin()
    result = plugin.validate(
        "PREFIX nmo: <http://nomisma.org/ontology#>\n"
        "PREFIX skos: <http://www.w3.org/2004/02/skos/core#>\n"
        "SELECT ?t ?label WHERE { ?t a nmo:TypeSeriesItem ; skos:prefLabel ?label }",
    )
    assert result.valid is True


def test_ocre_plugin_validate_invalid():
    plugin = OCREPlugin()
    result = plugin.validate(
        "PREFIX nmo: <http://nomisma.org/ontology#>\n"
        "SELECT ?t WHERE { ?t a nmo:Coin }",
    )
    assert result.valid is False


def test_ocre_plugin_load(tmp_path):
    from linked_past.core.store import create_store

    plugin = OCREPlugin()
    ttl = tmp_path / "ocre.ttl"
    ttl.write_text(SAMPLE_OCRE_TURTLE)
    store = create_store(tmp_path / "store")
    count = plugin.load(store, ttl)
    assert count > 0


def test_ocre_plugin_oci_attributes():
    plugin = OCREPlugin()
    assert plugin.oci_dataset == "ocre"


def test_ocre_plugin_version_info(tmp_path):
    plugin = OCREPlugin()
    info = plugin.get_version_info(tmp_path)
    assert info is not None
    assert "numismatics.org" in info.source_url
