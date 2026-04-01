"""Tests for the entity REST endpoint."""

from linked_past.core.viewer_api import _extract_name


def test_extract_name_from_label():
    props = [{"pred": "http://www.w3.org/2000/01/rdf-schema#label", "obj": "Roma"}]
    assert _extract_name("https://pleiades.stoa.org/places/423025", props) == "Roma"


def test_extract_name_from_person_name():
    props = [
        {"pred": "http://romanrepublic.ac.uk/rdf/ontology#hasPersonName", "obj": "Gaius Julius Caesar"},
        {"pred": "http://romanrepublic.ac.uk/rdf/ontology#hasNomen", "obj": "Julius"},
    ]
    assert _extract_name("http://romanrepublic.ac.uk/rdf/entity/Person/1957", props) == "Gaius Julius Caesar"


def test_extract_name_fallback_to_uri():
    props = [{"pred": "http://example.org/somePred", "obj": "some value"}]
    assert _extract_name("http://example.org/things/Widget42", props) == "Widget42"
