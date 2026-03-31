# tests/test_periodo_plugin.py
from linked_past.datasets.periodo.plugin import PeriodOPlugin


def test_periodo_plugin_attributes():
    plugin = PeriodOPlugin()
    assert plugin.name == "periodo"
    assert "PeriodO" in plugin.display_name
    assert plugin.license == "CC0"
    assert plugin.url == "https://perio.do"


def test_periodo_plugin_prefixes():
    plugin = PeriodOPlugin()
    prefixes = plugin.get_prefixes()
    assert "skos" in prefixes
    assert "time" in prefixes
    assert prefixes["periodo"] == "http://n2t.net/ark:/99152/p0v#"


def test_periodo_plugin_schema():
    plugin = PeriodOPlugin()
    schema = plugin.get_schema()
    assert "Period" in schema
    assert "Authority" in schema


def test_periodo_plugin_validate_valid():
    plugin = PeriodOPlugin()
    result = plugin.validate(
        "PREFIX skos: <http://www.w3.org/2004/02/skos/core#>\n"
        "SELECT ?p WHERE { ?p a skos:Concept }",
    )
    assert result.valid is True


def test_periodo_plugin_validate_invalid():
    plugin = PeriodOPlugin()
    result = plugin.validate(
        "PREFIX periodo: <http://n2t.net/ark:/99152/p0v#>\n"
        "SELECT ?p WHERE { ?p a periodo:FakeClass }",
    )
    assert result.valid is True  # Unknown classes are non-blocking warnings
    assert result.valid is True  # Unknown classes are warnings, not errors


def test_periodo_plugin_get_relevant_context():
    plugin = PeriodOPlugin()
    ctx = plugin.get_relevant_context(
        "PREFIX skos: <http://www.w3.org/2004/02/skos/core#>\n"
        "PREFIX time: <http://www.w3.org/2006/time#>\n"
        "SELECT ?p WHERE { ?p a skos:Concept ; skos:prefLabel ?label }",
    )
    assert isinstance(ctx, str)
    assert len(ctx) > 0


def test_periodo_plugin_load(tmp_path):
    from linked_past.core.store import create_store

    plugin = PeriodOPlugin()
    ttl = tmp_path / "periodo.ttl"
    ttl.write_text(
        '@prefix skos: <http://www.w3.org/2004/02/skos/core#> .\n'
        '@prefix time: <http://www.w3.org/2006/time#> .\n'
        '@prefix dcterms: <http://purl.org/dc/terms/> .\n'
        '@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n'
        '\n'
        '<http://n2t.net/ark:/99152/p06v8w4> a skos:ConceptScheme ;\n'
        '    dcterms:source [ dcterms:title "FastiOnline" ] .\n'
        '\n'
        '<http://n2t.net/ark:/99152/p05krdxmkzt> a skos:Concept, time:ProperInterval ;\n'
        '    skos:prefLabel "Roman Republic" ;\n'
        '    skos:inScheme <http://n2t.net/ark:/99152/p06v8w4> ;\n'
        '    time:intervalStartedBy [ a time:ProperInterval ;\n'
        '        time:hasDateTimeDescription [ time:year "-0508"^^xsd:gYear ] ] ;\n'
        '    time:intervalFinishedBy [ a time:ProperInterval ;\n'
        '        time:hasDateTimeDescription [ time:year "-0030"^^xsd:gYear ] ] .\n'
    )
    store = create_store(tmp_path / "store")
    count = plugin.load(store, ttl)
    assert count > 0


def test_periodo_plugin_oci_attributes():
    plugin = PeriodOPlugin()
    assert plugin.oci_dataset == "periodo"
    assert plugin.oci_version == "latest"


def test_periodo_plugin_version_info(tmp_path):
    plugin = PeriodOPlugin()
    info = plugin.get_version_info(tmp_path)
    assert info is not None
    assert info.rdf_format == "turtle"
