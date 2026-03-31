"""Tests for ontology-aware schema extraction."""

from __future__ import annotations

import textwrap

import pytest
import yaml
from linked_past_store.ontology import (
    extract_from_data,
    extract_from_ontology,
    extract_schema,
    generate_schemas_yaml,
    generate_shex_shapes,
)
from pyoxigraph import RdfFormat, Store

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
    "http://example.org/onto#": "vocab:",
    "http://www.w3.org/2001/XMLSchema#": "xsd:",
}


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


# --- OWL extraction tests ---


def test_owl_class_extraction(owl_file):
    schema = extract_from_ontology(owl_file)
    assert "Person" in schema.classes
    assert "ThingWithName" in schema.classes
    assert len(schema.classes) == 2


def test_owl_class_labels_and_comments(owl_file):
    schema = extract_from_ontology(owl_file)
    person = schema.classes["Person"]
    assert person.label == "Person"
    assert person.comment == "A historical person."
    assert person.uri == "http://example.org/onto#Person"
    thing = schema.classes["ThingWithName"]
    assert thing.label == "Thing With Name"
    assert thing.comment == "An entity that has a name."


def test_owl_class_hierarchy(owl_file):
    schema = extract_from_ontology(owl_file)
    person = schema.classes["Person"]
    assert person.parent == "http://example.org/onto#ThingWithName"
    thing = schema.classes["ThingWithName"]
    assert thing.parent == ""


def test_property_extraction_direct(owl_file):
    schema = extract_from_ontology(owl_file)
    person = schema.classes["Person"]
    pred_uris = {p.predicate for p in person.properties}
    assert "http://example.org/onto#hasAge" in pred_uris
    assert "http://example.org/onto#hasFriend" in pred_uris


def test_property_range_and_comment(owl_file):
    schema = extract_from_ontology(owl_file)
    thing = schema.classes["ThingWithName"]
    has_name = next(p for p in thing.properties if p.predicate == "http://example.org/onto#hasName")
    assert has_name.range == "http://www.w3.org/2001/XMLSchema#string"
    assert has_name.comment == "The name of the entity."


def test_inherited_properties(owl_file):
    """Person (subClassOf ThingWithName) should inherit hasName."""
    schema = extract_from_ontology(owl_file)
    person = schema.classes["Person"]
    pred_uris = {p.predicate for p in person.properties}
    assert "http://example.org/onto#hasName" in pred_uris


# --- Empirical extraction tests ---


def test_empirical_extraction_classes(data_file):
    schema = extract_schema(data_path=data_file)
    assert "Person" in schema.classes
    assert "Office" in schema.classes


def test_empirical_extraction_properties(data_file):
    schema = extract_schema(data_path=data_file)
    pred_uris = {p.predicate for p in schema.classes["Person"].properties}
    assert "http://example.org/hasName" in pred_uris
    assert "http://example.org/hasAge" in pred_uris


def test_empirical_extraction_via_store():
    store = Store()
    store.load(SAMPLE_DATA.encode(), format=RdfFormat.TURTLE)
    schema = extract_from_data(store)
    assert "Person" in schema.classes
    pred_uris = {p.predicate for p in schema.classes["Person"].properties}
    assert "http://example.org/hasName" in pred_uris


# --- Dispatcher tests ---


def test_extract_schema_prefers_ontology(owl_file, data_file):
    """When both paths provided, ontology should be used."""
    schema = extract_schema(data_path=data_file, ontology_path=owl_file)
    # Ontology has ThingWithName; data does not
    assert "ThingWithName" in schema.classes


def test_extract_schema_falls_back_to_data(data_file):
    schema = extract_schema(data_path=data_file, ontology_path=None)
    assert "Person" in schema.classes
    assert "ThingWithName" not in schema.classes


def test_extract_schema_no_paths_raises():
    with pytest.raises(ValueError, match="At least one"):
        extract_schema()


# --- YAML output tests ---


def test_to_schemas_yaml_returns_string(owl_file):
    schema = extract_from_ontology(owl_file)
    result = schema.to_schemas_yaml(PREFIX_MAP)
    assert isinstance(result, str)


def test_yaml_output_structure(owl_file):
    schema = extract_from_ontology(owl_file)
    content = schema.to_schemas_yaml(PREFIX_MAP)
    data = yaml.safe_load(content)
    assert "classes" in data
    assert "Person" in data["classes"]
    assert "ThingWithName" in data["classes"]

    person = data["classes"]["Person"]
    assert person["label"] == "Person"
    assert person["comment"] == "A historical person."
    assert person["uri"] == "vocab:Person"
    assert isinstance(person["properties"], list)


def test_yaml_output_property_format(owl_file):
    schema = extract_from_ontology(owl_file)
    content = schema.to_schemas_yaml(PREFIX_MAP)
    data = yaml.safe_load(content)

    thing = data["classes"]["ThingWithName"]
    props = thing["properties"]
    has_name = next(p for p in props if p["pred"] == "vocab:hasName")
    assert has_name["range"] == "xsd:string"
    assert has_name["comment"] == "The name of the entity."


def test_generate_schemas_yaml_writes_file(owl_file, tmp_path):
    schema = extract_from_ontology(owl_file)
    out = tmp_path / "schemas.yaml"
    generate_schemas_yaml(schema, out, PREFIX_MAP)
    assert out.exists()
    data = yaml.safe_load(out.read_text())
    assert "classes" in data
    assert "Person" in data["classes"]


SAMPLE_DATA_WITH_META = textwrap.dedent("""\
    @prefix ex: <http://example.org/> .
    @prefix owl: <http://www.w3.org/2002/07/owl#> .
    @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

    ex:person1 a ex:Person ;
        ex:hasName "Caesar" .

    ex:Person a owl:Class ;
        rdfs:label "Person" .
""")


def test_empirical_extraction_filters_metaclasses():
    store = Store()
    store.load(SAMPLE_DATA_WITH_META.encode(), format=RdfFormat.TURTLE)
    schema = extract_from_data(store, filter_meta=True)
    assert "Person" in schema.classes
    assert "Class" not in schema.classes
    for name, cls in schema.classes.items():
        assert not cls.uri.startswith("http://www.w3.org/"), f"Meta class {name} should be filtered"


# --- ShEx shape generation tests ---


def test_generate_shex_shapes_basic():
    schemas = {
        "Person": {
            "label": "Person",
            "comment": "A historical person.",
            "uri": "vocab:Person",
            "properties": [
                {"pred": "vocab:hasName", "range": "xsd:string", "comment": "Full name."},
                {"pred": "vocab:hasOffice", "range": "vocab:Office", "comment": "Office held."},
            ],
        },
        "Office": {
            "label": "Office",
            "comment": "A political office.",
            "uri": "vocab:Office",
            "properties": [
                {"pred": "rdfs:label", "range": "xsd:string", "comment": "Office label."},
            ],
        },
    }
    tips = [
        {"title": "Use COUNT(DISTINCT)", "body": "Always count distinct persons.", "classes": ["Person"]},
    ]
    prefix_map = {"vocab": "http://example.org/"}

    shapes = generate_shex_shapes(schemas, tips, prefix_map)

    assert "Person" in shapes
    assert "Office" in shapes

    person_shape = shapes["Person"]
    assert "vocab:Person {" in person_shape
    assert "vocab:hasName xsd:string" in person_shape
    assert "vocab:hasOffice [ vocab:Office ]" in person_shape
    assert "Full name." in person_shape
    assert "# TIP:" in person_shape
    assert "COUNT(DISTINCT)" in person_shape

    office_shape = shapes["Office"]
    assert "vocab:Office {" in office_shape
    assert "# TIP:" not in office_shape


def test_generate_shex_shapes_no_tips():
    schemas = {
        "Thing": {
            "label": "Thing",
            "uri": "ex:Thing",
            "properties": [
                {"pred": "ex:name", "range": "xsd:string"},
            ],
        },
    }

    shapes = generate_shex_shapes(schemas, [], {})

    assert "Thing" in shapes
    assert "ex:Thing {" in shapes["Thing"]
    assert "ex:name xsd:string" in shapes["Thing"]


def test_generate_shex_shapes_range_types():
    schemas = {
        "Item": {
            "label": "Item",
            "uri": "ex:Item",
            "properties": [
                {"pred": "ex:label", "range": "xsd:string"},
                {"pred": "ex:related", "range": "ex:Other"},
                {"pred": "ex:count", "range": "xsd:integer"},
                {"pred": "ex:noRange"},
            ],
        },
    }

    shapes = generate_shex_shapes(schemas, [], {})
    shape = shapes["Item"]

    assert "ex:label xsd:string" in shape
    assert "ex:related [ ex:Other ]" in shape
    assert "ex:count xsd:integer" in shape
    assert "ex:noRange IRI" in shape
