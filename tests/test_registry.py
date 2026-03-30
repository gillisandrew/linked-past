# tests/test_registry.py
import json
from pathlib import Path

import pytest

from linked_past.core.registry import DatasetRegistry
from linked_past.datasets.base import DatasetPlugin, ValidationResult, VersionInfo


class FakePlugin(DatasetPlugin):
    name = "fake"
    display_name = "Fake Dataset"
    description = "A fake dataset for testing."
    citation = "Fake et al., 2026"
    license = "CC0"
    url = "https://example.com"
    time_coverage = "2000-2026"
    spatial_coverage = "Everywhere"

    def __init__(self, context_dir=None):
        self._context_dir = context_dir

    def fetch(self, data_dir):
        ttl = data_dir / "fake.ttl"
        ttl.write_text(
            '@prefix ex: <http://example.org/> .\n'
            '@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n'
            'ex:Thing1 a ex:Widget ; rdfs:label "Thing" .\n'
        )
        return ttl

    def get_prefixes(self):
        return {"ex": "http://example.org/", "rdfs": "http://www.w3.org/2000/01/rdf-schema#"}

    def get_schema(self):
        return "## Fake Schema\n- Widget"

    def build_schema_dict(self):
        return {}

    def validate(self, sparql):
        return ValidationResult(valid=True, sparql=sparql)

    def get_version_info(self, data_dir):
        return VersionInfo(
            version="1.0.0",
            source_url="https://example.com/data.ttl",
            fetched_at="2026-03-30T00:00:00Z",
            triple_count=3,
            rdf_format="turtle",
        )


def test_registry_register_and_list(tmp_path):
    reg = DatasetRegistry(data_dir=tmp_path)
    plugin = FakePlugin()
    reg.register(plugin)
    assert "fake" in reg.list_datasets()


def test_registry_get_plugin(tmp_path):
    reg = DatasetRegistry(data_dir=tmp_path)
    plugin = FakePlugin()
    reg.register(plugin)
    assert reg.get_plugin("fake") is plugin


def test_registry_get_unknown_raises(tmp_path):
    reg = DatasetRegistry(data_dir=tmp_path)
    with pytest.raises(KeyError, match="fake"):
        reg.get_plugin("fake")


def test_registry_initialize_dataset(tmp_path):
    reg = DatasetRegistry(data_dir=tmp_path)
    plugin = FakePlugin()
    reg.register(plugin)
    reg.initialize_dataset("fake")
    store = reg.get_store("fake")
    assert store is not None
    results = store.query("SELECT (COUNT(*) AS ?c) WHERE { ?s ?p ?o }")
    for row in results:
        assert int(row[0].value) > 0


def test_registry_saves_registry_json(tmp_path):
    reg = DatasetRegistry(data_dir=tmp_path)
    plugin = FakePlugin()
    reg.register(plugin)
    reg.initialize_dataset("fake")
    registry_file = tmp_path / "registry.json"
    assert registry_file.exists()
    data = json.loads(registry_file.read_text())
    assert "fake" in data
    assert data["fake"]["version"] == "1.0.0"


def test_registry_skips_if_already_initialized(tmp_path):
    reg = DatasetRegistry(data_dir=tmp_path)
    plugin = FakePlugin()
    reg.register(plugin)
    reg.initialize_dataset("fake")
    original_fetch = plugin.fetch
    call_count = 0
    def counting_fetch(data_dir):
        nonlocal call_count
        call_count += 1
        return original_fetch(data_dir)
    plugin.fetch = counting_fetch
    reg.initialize_dataset("fake")
    assert call_count == 0
    store = reg.get_store("fake")
    assert store is not None


def test_registry_stores_actual_triple_count(tmp_path):
    reg = DatasetRegistry(data_dir=tmp_path)
    plugin = FakePlugin()
    reg.register(plugin)
    reg.initialize_dataset("fake")
    meta = reg.get_metadata("fake")
    assert meta["triple_count"] > 0
