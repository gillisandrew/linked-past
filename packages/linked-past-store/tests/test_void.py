"""Tests for VoID description generation."""

from __future__ import annotations

import textwrap

import pytest
from linked_past_store.void import VoidDescription, generate_void
from pyoxigraph import RdfFormat, Store

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

DATASET_ID = "http://example.org/dataset"


@pytest.fixture()
def data_file(tmp_path):
    f = tmp_path / "data.ttl"
    f.write_text(SAMPLE_DATA)
    return f


def test_generate_void_triple_count(data_file):
    void_desc = generate_void(data_file, DATASET_ID, "Test Dataset")
    # 3 rdf:type + ex:hasName*2 + ex:hasAge*2 + ex:hasTitle = 8 triples
    assert void_desc.triples == 8


def test_generate_void_entity_count(data_file):
    void_desc = generate_void(data_file, DATASET_ID, "Test Dataset")
    # 3 typed subjects: person1, person2, office1
    assert void_desc.entities == 3


def test_generate_void_class_count(data_file):
    void_desc = generate_void(data_file, DATASET_ID, "Test Dataset")
    # 2 distinct classes: ex:Person, ex:Office
    assert void_desc.classes == 2


def test_generate_void_property_count(data_file):
    void_desc = generate_void(data_file, DATASET_ID, "Test Dataset")
    # rdf:type, ex:hasName, ex:hasAge, ex:hasTitle = 4 distinct predicates
    assert void_desc.properties == 4


def test_generate_void_example_resource_is_typed_subject(data_file):
    void_desc = generate_void(data_file, DATASET_ID, "Test Dataset")
    assert void_desc.example_resource.startswith("http://example.org/")
    # Should be one of the typed subjects
    assert void_desc.example_resource in {
        "http://example.org/person1",
        "http://example.org/person2",
        "http://example.org/office1",
    }


def test_generate_void_uri_space(data_file):
    void_desc = generate_void(data_file, DATASET_ID, "Test Dataset")
    # All typed subjects start with http://example.org/
    assert void_desc.uri_space == "http://example.org/"


def test_to_turtle_is_valid_rdf(data_file):
    void_desc = generate_void(
        data_file,
        DATASET_ID,
        "Test Dataset",
        license_uri="http://creativecommons.org/licenses/by/4.0/",
        publisher="Test Publisher",
    )
    turtle = void_desc.to_turtle()
    assert turtle
    # Parse with pyoxigraph to verify it's valid Turtle
    store = Store()
    store.load(turtle.encode(), format=RdfFormat.TURTLE)
    assert len(store) > 0


def test_to_turtle_contains_dataset_id(data_file):
    void_desc = generate_void(data_file, DATASET_ID, "My Dataset")
    turtle = void_desc.to_turtle()
    assert DATASET_ID in turtle
    assert "void:Dataset" in turtle
    assert "My Dataset" in turtle


def test_to_turtle_contains_counts(data_file):
    void_desc = generate_void(data_file, DATASET_ID, "Test Dataset")
    turtle = void_desc.to_turtle()
    assert "void:triples" in turtle
    assert "void:entities" in turtle
    assert "void:classes" in turtle
    assert "void:properties" in turtle


def test_to_turtle_optional_fields(data_file):
    void_desc = generate_void(
        data_file,
        DATASET_ID,
        "Test Dataset",
        license_uri="http://creativecommons.org/licenses/by/4.0/",
        source_uri="http://example.org/source",
        citation="Smith 2024",
        publisher="Test Org",
        description="A test dataset.",
    )
    turtle = void_desc.to_turtle()
    assert "dcterms:license" in turtle
    assert "dcterms:source" in turtle
    assert "bibliographicCitation" in turtle
    assert "Smith 2024" in turtle
    assert "dcterms:publisher" in turtle
    assert "Test Org" in turtle
    assert "A test dataset." in turtle
    # Verify it still parses cleanly
    store = Store()
    store.load(turtle.encode(), format=RdfFormat.TURTLE)
    assert len(store) > 0


def test_file_output(data_file, tmp_path):
    out = tmp_path / "void.ttl"
    void_desc = generate_void(data_file, DATASET_ID, "Test Dataset", output_path=out)
    assert out.exists()
    content = out.read_text()
    assert "void:Dataset" in content
    assert void_desc.triples == 8


def test_void_description_dataclass():
    """VoidDescription can be instantiated directly."""
    vd = VoidDescription(dataset_id="http://example.org/d", title="My Dataset")
    assert vd.triples == 0
    assert vd.linksets == []


def test_distinct_subjects_objects(data_file):
    void_desc = generate_void(data_file, DATASET_ID, "Test Dataset")
    # 3 typed subjects + predicates themselves are subjects in some sense,
    # but distinct subjects = all unique ?s across all triples
    assert void_desc.distinct_subjects > 0
    assert void_desc.distinct_objects > 0


def test_class_partitions(data_file):
    void_desc = generate_void(data_file, DATASET_ID, "Test Dataset")
    assert len(void_desc.class_partitions) == 2

    by_uri = {cp.class_uri: cp for cp in void_desc.class_partitions}
    assert "http://example.org/Person" in by_uri
    assert "http://example.org/Office" in by_uri
    assert by_uri["http://example.org/Person"].entities == 2
    assert by_uri["http://example.org/Office"].entities == 1


def test_property_partitions(data_file):
    void_desc = generate_void(data_file, DATASET_ID, "Test Dataset")
    # 4 predicates: rdf:type, ex:hasName, ex:hasAge, ex:hasTitle
    assert len(void_desc.property_partitions) == 4

    by_uri = {pp.property_uri: pp for pp in void_desc.property_partitions}
    rdf_type = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
    assert rdf_type in by_uri
    assert by_uri[rdf_type].triples == 3
    assert by_uri[rdf_type].distinct_subjects == 3

    assert "http://example.org/hasName" in by_uri
    assert by_uri["http://example.org/hasName"].triples == 2
    assert by_uri["http://example.org/hasName"].distinct_objects == 2  # "Julius Caesar", "Pompey"


def test_to_turtle_contains_partitions(data_file):
    void_desc = generate_void(data_file, DATASET_ID, "Test Dataset")
    turtle = void_desc.to_turtle()
    assert "void:classPartition" in turtle
    assert "void:propertyPartition" in turtle
    assert "void:distinctSubjects" in turtle
    assert "void:distinctObjects" in turtle
    # Still valid Turtle
    store = Store()
    store.load(turtle.encode(), format=RdfFormat.TURTLE)
    assert len(store) > 0


def test_to_turtle_with_linksets():
    vd = VoidDescription(
        dataset_id="http://example.org/d",
        title="Test",
        triples=100,
        linksets=[
            {
                "target": "http://other.org/dataset",
                "predicate": "http://www.w3.org/2004/02/skos/core#exactMatch",
                "triples": 10,
            }
        ],
    )
    turtle = vd.to_turtle()
    assert "void:Linkset" in turtle
    assert "void:subset" in turtle
    assert "other.org" in turtle
    # Verify it parses
    store = Store()
    store.load(turtle.encode(), format=RdfFormat.TURTLE)
    assert len(store) > 0
