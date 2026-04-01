# tests/test_base.py
from pathlib import Path

import pytest
from linked_past.datasets.base import DatasetPlugin, ValidationResult, VersionInfo


def test_dataset_plugin_requires_context_dir():
    """Bare DatasetPlugin() raises because there is no context/ dir next to base.py."""
    with pytest.raises(FileNotFoundError, match="Context directory not found"):
        DatasetPlugin()


class MinimalPlugin(DatasetPlugin):
    """A minimal subclass that points at DPRR's context dir for testing."""

    name = "minimal"
    display_name = "Minimal Test Plugin"
    description = "Test plugin."
    citation = "Test"
    license = "CC0"
    url = "https://example.com"
    time_coverage = "Test"
    spatial_coverage = "Test"

    @classmethod
    def _context_dir(cls) -> Path:
        return Path(__file__).parent.parent / "linked_past" / "datasets" / "dprr" / "context"


def test_minimal_plugin_init():
    plugin = MinimalPlugin()
    assert plugin.name == "minimal"
    assert isinstance(plugin._prefixes, dict)
    assert len(plugin._prefixes) > 0


def test_minimal_plugin_get_prefixes():
    plugin = MinimalPlugin()
    prefixes = plugin.get_prefixes()
    assert "vocab" in prefixes


def test_minimal_plugin_build_schema_dict():
    plugin = MinimalPlugin()
    schema_dict = plugin.build_schema_dict()
    assert isinstance(schema_dict, dict)
    assert len(schema_dict) > 0


def test_minimal_plugin_get_schema():
    plugin = MinimalPlugin()
    schema = plugin.get_schema()
    assert "Prefixes" in schema
    assert "Classes" in schema


def test_minimal_plugin_validate():
    plugin = MinimalPlugin()
    result = plugin.validate(
        "PREFIX vocab: <http://romanrepublic.ac.uk/rdf/ontology#>\n"
        "SELECT ?p WHERE { ?p a vocab:Person }"
    )
    assert result.valid is True
    assert isinstance(result, ValidationResult)


def test_minimal_plugin_get_relevant_context():
    plugin = MinimalPlugin()
    ctx = plugin.get_relevant_context(
        "PREFIX vocab: <http://romanrepublic.ac.uk/rdf/ontology#>\n"
        "SELECT ?p WHERE { ?p a vocab:Person ; vocab:hasPersonName ?n }"
    )
    assert isinstance(ctx, str)


def test_minimal_plugin_get_version_info(tmp_path):
    plugin = MinimalPlugin()
    info = plugin.get_version_info(tmp_path)
    assert info is not None
    assert info.version == "latest"
    assert info.source_url == "https://example.com"
    assert info.rdf_format == "turtle"


def test_version_info_dataclass():
    info = VersionInfo(
        version="1.0.0",
        source_url="https://example.com/data.ttl",
        fetched_at="2026-03-30T14:00:00Z",
        triple_count=1000,
        rdf_format="turtle",
    )
    assert info.version == "1.0.0"
    assert info.triple_count == 1000


def test_validation_result_dataclass():
    result = ValidationResult(
        valid=True,
        sparql="SELECT ?s WHERE { ?s ?p ?o }",
        errors=[],
        suggestions=[],
    )
    assert result.valid is True
    assert result.errors == []


def test_validation_result_with_errors():
    result = ValidationResult(
        valid=False,
        sparql="SELECT ?s WHERE { ?s ?p ?o }",
        errors=["Unknown class 'Foo'"],
        suggestions=["Did you mean 'Person'?"],
    )
    assert result.valid is False
    assert len(result.errors) == 1
