"""Tests for the linkage graph store."""

import pytest
from linked_past.core.linkage import LinkageGraph

SAMPLE_LINKAGE = {
    "metadata": {
        "source_dataset": "dprr",
        "target_dataset": "pleiades",
        "relationship": "owl:sameAs",
        "confidence": "confirmed",
        "method": "manual_alignment",
        "basis": "Barrington Atlas",
        "author": "test-author",
        "date": "2026-03-30",
    },
    "links": [
        {
            "source": "http://romanrepublic.ac.uk/rdf/entity/Province/Sicilia",
            "target": "https://pleiades.stoa.org/places/462492#this",
            "note": "Map 47",
        },
        {
            "source": "http://romanrepublic.ac.uk/rdf/entity/Province/Africa",
            "target": "https://pleiades.stoa.org/places/775#this",
            "note": "Map 33",
        },
    ],
}

SAMPLE_TEMPORAL = {
    "metadata": {
        "source_dataset": "dprr",
        "target_dataset": "periodo",
        "relationship": "dcterms:temporal",
        "confidence": "confirmed",
        "method": "manual_alignment",
        "basis": "Standard periodization",
        "author": "test-author",
        "date": "2026-03-30",
    },
    "links": [
        {
            "source": "http://romanrepublic.ac.uk/rdf/entity/Era/Republic",
            "target": "http://n2t.net/ark:/99152/p05krdxmkzt",
            "note": "Roman Republic period",
        },
    ],
}


@pytest.fixture
def graph():
    g = LinkageGraph()
    g.load_data(SAMPLE_LINKAGE)
    return g


def test_load(graph):
    # 2 links * (1 link triple + 7 provenance triples) = 16
    assert graph.triple_count() > 0


def test_find_links_forward(graph):
    results = graph.find_links("http://romanrepublic.ac.uk/rdf/entity/Province/Sicilia")
    assert len(results) == 1
    r = results[0]
    assert r["target"] == "https://pleiades.stoa.org/places/462492#this"
    assert r["direction"] == "forward"
    assert r["confidence"] == "confirmed"


def test_find_links_reverse(graph):
    results = graph.find_links("https://pleiades.stoa.org/places/462492#this")
    assert len(results) == 1
    r = results[0]
    assert r["target"] == "http://romanrepublic.ac.uk/rdf/entity/Province/Sicilia"
    assert r["direction"] == "reverse"


def test_find_links_empty(graph):
    results = graph.find_links("http://example.com/nonexistent")
    assert results == []


def test_get_provenance(graph):
    prov = graph.get_provenance(
        "http://romanrepublic.ac.uk/rdf/entity/Province/Sicilia",
        "https://pleiades.stoa.org/places/462492#this",
    )
    assert prov is not None
    assert prov["author"] == "test-author"
    assert prov["basis"] == "Barrington Atlas"
    assert prov["confidence"] == "confirmed"
    assert prov["method"] == "manual_alignment"
    assert prov["note"] == "Map 47"


def test_get_provenance_missing(graph):
    prov = graph.get_provenance(
        "http://example.com/a",
        "http://example.com/b",
    )
    assert prov is None


def test_load_multiple_files():
    g = LinkageGraph()
    g.load_data(SAMPLE_LINKAGE)
    g.load_data(SAMPLE_TEMPORAL)
    # Forward links from a DPRR province should still work
    results = graph_find_sicilia(g)
    assert len(results) == 1
    # Temporal link should also be findable
    results = g.find_links("http://romanrepublic.ac.uk/rdf/entity/Era/Republic")
    assert len(results) == 1
    assert results[0]["direction"] == "forward"


def graph_find_sicilia(g):
    return g.find_links("http://romanrepublic.ac.uk/rdf/entity/Province/Sicilia")


SAMPLE_MIXED_CONFIDENCE = {
    "metadata": {
        "source_dataset": "dprr",
        "target_dataset": "nomisma",
        "relationship": "skos:closeMatch",
        "confidence": "confirmed",
        "method": "manual_alignment",
        "basis": "RRC cross-referencing",
        "author": "linked-past project",
        "date": "2026-03-30",
    },
    "links": [
        {
            "source": "http://romanrepublic.ac.uk/rdf/entity/Person/1957",
            "target": "http://nomisma.org/id/julius_caesar",
            "note": "RRC 468; confirmed via MRR",
        },
        {
            "source": "http://romanrepublic.ac.uk/rdf/entity/Person/2253",
            "target": "http://nomisma.org/id/cn_magnvs_imp_rrc",
            "confidence": "probable",
            "note": "Name + date match only",
        },
    ],
}


def test_per_link_confidence(tmp_path):
    graph = LinkageGraph(tmp_path / "store")
    graph.load_data(SAMPLE_MIXED_CONFIDENCE)
    links_caesar = graph.find_links("http://romanrepublic.ac.uk/rdf/entity/Person/1957")
    assert len(links_caesar) == 1
    assert links_caesar[0]["confidence"] == "confirmed"
    links_pompey = graph.find_links("http://romanrepublic.ac.uk/rdf/entity/Person/2253")
    assert len(links_pompey) == 1
    assert links_pompey[0]["confidence"] == "probable"
