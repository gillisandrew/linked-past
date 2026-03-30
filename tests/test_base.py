# tests/test_base.py
import pytest
from linked_past.datasets.base import DatasetPlugin, VersionInfo, ValidationResult


def test_dataset_plugin_is_abstract():
    """Cannot instantiate DatasetPlugin directly — has abstract methods
    including fetch, get_prefixes, get_schema, build_schema_dict, validate, get_version_info."""
    with pytest.raises(TypeError):
        DatasetPlugin()


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
