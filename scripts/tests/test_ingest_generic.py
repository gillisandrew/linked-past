"""Tests for the RDF/XML pre-processing step of scripts/ingest_generic.py."""

from scripts.ingest_generic import prepare_rdfxml


def test_doctype_goes_after_declaration_when_root_shares_the_line():
    src = '<?xml version="1.0" encoding="utf-8"?><rdf:RDF xmlns:rdf="x">\n</rdf:RDF>\n'
    out, fixes = prepare_rdfxml(src)
    expected = '<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE rdf:RDF [<!ENTITY nbsp "&#160;">]>\n<rdf:RDF'
    assert out.startswith(expected)
    assert fixes["schemeless_iris"] == 0


def test_doctype_goes_after_declaration_on_its_own_line():
    src = '<?xml version="1.0"?>\n<rdf:RDF xmlns:rdf="x">\n</rdf:RDF>\n'
    out, _ = prepare_rdfxml(src)
    assert out.split("\n")[1] == '<!DOCTYPE rdf:RDF [<!ENTITY nbsp "&#160;">]>'
    assert out.split("\n")[2].startswith("<rdf:RDF")


def test_no_declaration_still_gets_doctype():
    src = '<rdf:RDF xmlns:rdf="x">\n</rdf:RDF>\n'
    out, _ = prepare_rdfxml(src)
    assert out.startswith('<!DOCTYPE rdf:RDF [<!ENTITY nbsp "&#160;">]>\n<rdf:RDF')


def test_schemeless_resource_iris_get_http_scheme():
    src = (
        '<?xml version="1.0"?>\n<rdf:RDF>'
        '<skos:exactMatch rdf:resource="www.wikidata.org/entity/Q37632834"/>'
        '<skos:exactMatch rdf:resource="www.lgpn.ox.ac.uk/id/V2-38848"/>'
        '<skos:exactMatch rdf:resource="http://www.wikidata.org/entity/Q1"/>'
        '<skos:exactMatch rdf:resource="#fragment"/>'
        "</rdf:RDF>\n"
    )
    out, fixes = prepare_rdfxml(src)
    assert 'rdf:resource="http://www.wikidata.org/entity/Q37632834"' in out
    assert 'rdf:resource="http://www.lgpn.ox.ac.uk/id/V2-38848"' in out
    assert out.count('rdf:resource="http://www.wikidata.org/entity/Q1"') == 1
    assert 'rdf:resource="#fragment"' in out
    assert fixes["schemeless_iris"] == 2
