"""Tests for ontology-aware schema extraction."""

from __future__ import annotations

import textwrap

import pytest
from linked_past_store.ontology import (
    extract_from_data,
    extract_from_ontology,
    extract_schema,
    generate_schemas_yaml,
)
from pyoxigraph import Store

SAMPLE_OWL = textwrap.dedent("""\
    @prefix owl: <http://www.w3.org/2002/07/owl#> .
    @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
    @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
    @prefix : <http://example.org/onto#> .

    :Person a owl:Class ;
        rdfs:label "Person" ;
        rdfs:comment "A historical person." ;
        rdfs:subClassOf :ThingWithName .

    :ThingWithName a owl:Class ;
        rdfs:label "Thing With Name" ;
        rdfs:comment "An entity that has a name." .

    :hasName a owl:DatatypeProperty ;
        rdfs:domain :ThingWithName ;
        rdfs:range xsd:string ;
        rdfs:comment "The name of the entity." .

    :hasAge a owl:DatatypeProperty ;
        rdfs:domain :Person ;
        rdfs:range xsd:integer ;
        rdfs:comment "Age of the person." .

    :hasFriend a owl:ObjectProperty ;
        rdfs:domain :Person ;
        rdfs:range :Person ;
        rdfs:comment "A friend relationship." .
""")

SAMPLE_DATA = textwrap.dedent("""\
    @prefix ex: <http://example.org/> .
    @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

    ex:person1 a ex:Person ;
        ex:hasName "Julius Caesar" ;
        ex:hasAge 55 .

    ex:person2 a ex:Person ;
        ex:hasName "Pompey" ;
        ex:hasAge 58 .

    ex:office1 a ex:Office ;
        ex:hasTitle "Consul" .
""")

PREFIX_MAP = {
    "http://example.org/onto#": ":",
    "http://www.w3.org/2001/XMLSchema#": "xsd:",
}

PERSON_URI = "http://example.org/onto#Person"
THING_URI = "http://example.org/onto#ThingWithName"
HAS_NAME_URI = "http://example.org/onto#hasName"
HAS_AGE_URI = "http://example.org/onto#hasAge"
HAS_FRIEND_URI = "http://example.org/onto#hasFriend"


@pytest.fixture()
def owl_file(tmp_path):
    f = tmp_path / "onto.ttl"
    f.write_text(SAMPLE_OWL)
    return f


@pytest.fixture()
def data_file(tmp_path):
    f = tmp_path / "data.ttl"
    f.write_text(SAMPLE_DATA)
    return f


def test_owl_class_extraction(owl_file):
    schema = extract_from_ontology(owl_file)
    assert PERSON_URI in schema.classes
    assert THING_URI in schema.classes
    assert len(schema.classes) == 2


def test_owl_class_labels_and_comments(owl_file):
    schema = extract_from_ontology(owl_file)
    person = schema.classes[PERSON_URI]
    assert person.label == "Person"
    assert person.comment == "A historical person."
    thing = schema.classes[THING_URI]
    assert thing.label == "Thing With Name"
    assert thing.comment == "An entity that has a name."


def test_owl_class_hierarchy(owl_file):
    schema = extract_from_ontology(owl_file)
    person = schema.classes[PERSON_URI]
    assert person.parent == THING_URI
    thing = schema.classes[THING_URI]
    assert thing.parent == ""


def test_property_extraction_direct(owl_file):
    schema = extract_from_ontology(owl_file)
    person = schema.classes[PERSON_URI]
    pred_uris = {p.predicate for p in person.properties}
    # Direct properties on Person
    assert HAS_AGE_URI in pred_uris
    assert HAS_FRIEND_URI in pred_uris


def test_property_range_and_comment(owl_file):
    schema = extract_from_ontology(owl_file)
    thing = schema.classes[THING_URI]
    has_name = next(p for p in thing.properties if p.predicate == HAS_NAME_URI)
    assert has_name.range == "http://www.w3.org/2001/XMLSchema#string"
    assert has_name.comment == "The name of the entity."


def test_inherited_properties(owl_file):
    """Person (subClassOf ThingWithName) should inherit hasName."""
    schema = extract_from_ontology(owl_file)
    person = schema.classes[PERSON_URI]
    pred_uris = {p.predicate for p in person.properties}
    assert HAS_NAME_URI in pred_uris, "Person should inherit hasName from ThingWithName"


def test_empirical_extraction_classes(data_file):
    schema = extract_schema(data_path=data_file)
    ex_person = "http://example.org/Person"
    ex_office = "http://example.org/Office"
    assert ex_person in schema.classes
    assert ex_office in schema.classes


def test_empirical_extraction_properties(data_file):
    schema = extract_schema(data_path=data_file)
    ex_person = "http://example.org/Person"
    pred_uris = {p.predicate for p in schema.classes[ex_person].properties}
    assert "http://example.org/hasName" in pred_uris
    assert "http://example.org/hasAge" in pred_uris


def test_empirical_extraction_via_store():
    store = Store()
    store.load(SAMPLE_DATA.encode(), format="text/turtle")
    schema = extract_from_data(store)
    ex_person = "http://example.org/Person"
    assert ex_person in schema.classes
    pred_uris = {p.predicate for p in schema.classes[ex_person].properties}
    assert "http://example.org/hasName" in pred_uris


def test_extract_schema_prefers_ontology(owl_file, data_file):
    """When both paths provided, ontology should be used."""
    schema = extract_schema(data_path=data_file, ontology_path=owl_file)
    # Ontology has http://example.org/onto#Person, data has http://example.org/Person
    assert PERSON_URI in schema.classes
    assert "http://example.org/Person" not in schema.classes


def test_extract_schema_falls_back_to_data(data_file):
    schema = extract_schema(data_path=data_file, ontology_path=None)
    assert "http://example.org/Person" in schema.classes


def test_extract_schema_no_paths_raises():
    with pytest.raises(ValueError, match="At least one"):
        extract_schema()


def test_yaml_output_prefix_shortening(owl_file):
    schema = extract_from_ontology(owl_file)
    yaml_dict = schema.to_schemas_yaml(PREFIX_MAP)
    # Shortened URIs should appear as keys
    assert ":Person" in yaml_dict
    assert ":ThingWithName" in yaml_dict
    person_entry = yaml_dict[":Person"]
    assert person_entry["parent"] == ":ThingWithName"


def test_yaml_output_property_range_shortened(owl_file):
    schema = extract_from_ontology(owl_file)
    yaml_dict = schema.to_schemas_yaml(PREFIX_MAP)
    thing_entry = yaml_dict[":ThingWithName"]
    props = thing_entry["properties"]
    assert ":hasName" in props
    assert props[":hasName"]["range"] == "xsd:string"


def test_generate_schemas_yaml_writes_file(owl_file, tmp_path):
    import yaml

    schema = extract_from_ontology(owl_file)
    out = tmp_path / "schemas.yaml"
    generate_schemas_yaml(schema, out, PREFIX_MAP)
    assert out.exists()
    data = yaml.safe_load(out.read_text())
    assert ":Person" in data
