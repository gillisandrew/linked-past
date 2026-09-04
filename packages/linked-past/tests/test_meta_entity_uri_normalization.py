"""A ``#this`` Pleiades link and a bare one must cluster as the same place."""

from linked_past.core.linkage import LinkageGraph
from linked_past.core.meta_entities import MetaEntityIndex

ATHENS = "https://pleiades.stoa.org/places/579885"


def _yaml(source_dataset: str, source: str, target: str) -> dict:
    return {
        "metadata": {
            "source_dataset": source_dataset,
            "target_dataset": "pleiades",
            "relationship": "skos:closeMatch",
            "confidence": "confirmed",
            "method": "manual_alignment",
            "basis": "test",
            "author": "test",
            "date": "2026-09-05",
        },
        "links": [{"source": source, "target": target}],
    }


def test_this_and_bare_pleiades_links_share_a_cluster():
    graph = LinkageGraph()
    graph.load_data(_yaml("dprr", "http://romanrepublic.ac.uk/rdf/entity/Province/1", ATHENS + "#this"))
    graph.load_data(_yaml("kerameikos", "https://kerameikos.org/id/athens", ATHENS))

    clusters = MetaEntityIndex()._seed_from_linkage(graph)

    assert len(clusters) == 1, clusters
    cluster = next(iter(clusters.values()))
    assert cluster["pleiades"] == {ATHENS}
    assert "dprr" in cluster and "kerameikos" in cluster
