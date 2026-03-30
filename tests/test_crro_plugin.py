from linked_past.datasets.crro.plugin import CRROPlugin

SAMPLE_CRRO_TURTLE = """\
@prefix nmo: <http://nomisma.org/ontology#> .
@prefix nm: <http://nomisma.org/id/> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix void: <http://rdfs.org/ns/void#> .

<http://numismatics.org/crro/id/rrc-44.5> a nmo:TypeSeriesItem, skos:Concept ;
    skos:prefLabel "RRC 44/5" ;
    nmo:hasAuthority nm:rome_pre-denarius ;
    nmo:hasDenomination nm:denarius ;
    nmo:hasMint nm:rome ;
    nmo:hasMaterial nm:ar ;
    nmo:hasStartDate "-0210"^^xsd:gYear ;
    nmo:hasEndDate "-0210"^^xsd:gYear ;
    dcterms:source nm:rrc ;
    void:inDataset <http://numismatics.org/crro/> .
"""


def test_crro_plugin_attributes():
    plugin = CRROPlugin()
    assert plugin.name == "crro"
    assert "CRRO" in plugin.display_name
    assert plugin.license == "ODbL 1.0"


def test_crro_plugin_prefixes():
    plugin = CRROPlugin()
    prefixes = plugin.get_prefixes()
    assert "nmo" in prefixes
    assert "crro" in prefixes


def test_crro_plugin_schema():
    plugin = CRROPlugin()
    schema = plugin.get_schema()
    assert "CoinType" in schema
    assert "TypeSeriesItem" in schema


def test_crro_plugin_validate_valid():
    plugin = CRROPlugin()
    result = plugin.validate(
        "PREFIX nmo: <http://nomisma.org/ontology#>\n"
        "PREFIX skos: <http://www.w3.org/2004/02/skos/core#>\n"
        "SELECT ?t ?label WHERE { ?t a nmo:TypeSeriesItem ; skos:prefLabel ?label }",
    )
    assert result.valid is True


def test_crro_plugin_validate_invalid():
    plugin = CRROPlugin()
    result = plugin.validate(
        "PREFIX nmo: <http://nomisma.org/ontology#>\n"
        "SELECT ?t WHERE { ?t a nmo:Coin }",
    )
    assert result.valid is True  # Unknown classes are non-blocking warnings


def test_crro_plugin_load(tmp_path):
    from linked_past.core.store import create_store

    plugin = CRROPlugin()
    ttl = tmp_path / "crro.ttl"
    ttl.write_text(SAMPLE_CRRO_TURTLE)
    store = create_store(tmp_path / "store")
    count = plugin.load(store, ttl)
    assert count > 0


def test_crro_plugin_oci_attributes():
    plugin = CRROPlugin()
    assert plugin.oci_dataset == "crro"


def test_crro_plugin_version_info(tmp_path):
    plugin = CRROPlugin()
    info = plugin.get_version_info(tmp_path)
    assert info is not None
    assert "numismatics.org" in info.source_url
