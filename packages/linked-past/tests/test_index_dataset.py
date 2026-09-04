"""Tests for _index_dataset's use of the plugin enrichment hook."""

from linked_past.core.search import SearchIndex
from linked_past.core.server import _index_dataset
from pyoxigraph import Store


class StubPlugin:
    display_name = "Stub"
    description = "A stub dataset"

    def extra_search_entries(self, store, registry):
        return [("entity_label", "RRC 366/1 — C. Annius\thttp://example.org/coin/366")]


class ExplodingPlugin(StubPlugin):
    def extra_search_entries(self, store, registry):
        raise RuntimeError("boom")


def test_index_dataset_includes_plugin_extra_entries():
    search = SearchIndex()
    _index_dataset(search, "stub", StubPlugin(), Store(), registry=None)

    results = search.search("Annius", dataset="stub", doc_type="entity_label")

    assert any("coin/366" in r["text"] for r in results)
    search.close()


def test_index_dataset_survives_hook_failure():
    search = SearchIndex()
    _index_dataset(search, "stub", ExplodingPlugin(), Store(), registry=None)

    results = search.search("stub dataset", dataset="stub", doc_type="dataset")

    assert len(results) == 1
    search.close()
