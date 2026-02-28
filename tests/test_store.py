import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from dprr_mcp.store import ensure_initialized, execute_query, get_or_create_store, is_initialized, load_rdf

SAMPLE_TURTLE = """\
@prefix vocab: <http://romanrepublic.ac.uk/rdf/entity/vocab/> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

<http://romanrepublic.ac.uk/rdf/entity/Person/1> a vocab:Person ;
    vocab:hasPersonName "IUNI0001 L. Iunius Brutus" ;
    vocab:hasDprrID "IUNI0001" ;
    vocab:hasID "1" ;
    vocab:hasNomen "Iunius" ;
    vocab:hasCognomen "Brutus" ;
    vocab:isSex <http://romanrepublic.ac.uk/rdf/entity/Sex/Male> ;
    vocab:hasEraFrom "-509"^^xsd:integer ;
    vocab:hasEraTo "-509"^^xsd:integer .

<http://romanrepublic.ac.uk/rdf/entity/Person/2> a vocab:Person ;
    vocab:hasPersonName "TARQ0001 L. Tarquinius Collatinus" ;
    vocab:hasDprrID "TARQ0001" ;
    vocab:hasID "2" ;
    vocab:hasNomen "Tarquinius" ;
    vocab:hasCognomen "Collatinus" ;
    vocab:isSex <http://romanrepublic.ac.uk/rdf/entity/Sex/Male> .

<http://romanrepublic.ac.uk/rdf/entity/PostAssertion/1> a vocab:PostAssertion ;
    vocab:isAboutPerson <http://romanrepublic.ac.uk/rdf/entity/Person/1> ;
    vocab:hasOffice <http://romanrepublic.ac.uk/rdf/entity/Office/3> ;
    vocab:hasDateStart "-509"^^xsd:integer ;
    vocab:hasDateEnd "-509"^^xsd:integer .

<http://romanrepublic.ac.uk/rdf/entity/PostAssertion/2> a vocab:PostAssertion ;
    vocab:isAboutPerson <http://romanrepublic.ac.uk/rdf/entity/Person/2> ;
    vocab:hasOffice <http://romanrepublic.ac.uk/rdf/entity/Office/3> ;
    vocab:hasDateStart "-509"^^xsd:integer ;
    vocab:hasDateEnd "-509"^^xsd:integer .

<http://romanrepublic.ac.uk/rdf/entity/Office/3> a vocab:Office ;
    rdfs:label "Office: consul" .

<http://romanrepublic.ac.uk/rdf/entity/Sex/Male> a vocab:Sex ;
    rdfs:label "Sex: Male" .
"""


def test_get_or_create_store():
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "store"
        store = get_or_create_store(store_path)
        assert store is not None


def test_load_rdf_returns_triple_count():
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "store"
        store = get_or_create_store(store_path)
        ttl_path = Path(tmpdir) / "test.ttl"
        ttl_path.write_text(SAMPLE_TURTLE)
        count = load_rdf(store, ttl_path)
        assert count > 0


def test_execute_query_returns_results():
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "store"
        store = get_or_create_store(store_path)
        ttl_path = Path(tmpdir) / "test.ttl"
        ttl_path.write_text(SAMPLE_TURTLE)
        load_rdf(store, ttl_path)

        results = execute_query(
            store,
            """
            PREFIX vocab: <http://romanrepublic.ac.uk/rdf/entity/vocab/>
            SELECT ?person ?name WHERE {
                ?person a vocab:Person ;
                    vocab:hasPersonName ?name .
            }
            ORDER BY ?name
            """,
        )
        assert len(results) == 2
        assert results[0]["name"] == "IUNI0001 L. Iunius Brutus"
        assert results[1]["name"] == "TARQ0001 L. Tarquinius Collatinus"


def test_execute_query_empty_results():
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "store"
        store = get_or_create_store(store_path)
        ttl_path = Path(tmpdir) / "test.ttl"
        ttl_path.write_text(SAMPLE_TURTLE)
        load_rdf(store, ttl_path)

        results = execute_query(
            store,
            """
            PREFIX vocab: <http://romanrepublic.ac.uk/rdf/entity/vocab/>
            SELECT ?person WHERE {
                ?person a vocab:Person ;
                    vocab:hasNomen "Nonexistent" .
            }
            """,
        )
        assert results == []


def test_is_initialized():
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "store"
        assert not is_initialized(store_path)
        store = get_or_create_store(store_path)
        ttl_path = Path(tmpdir) / "test.ttl"
        ttl_path.write_text(SAMPLE_TURTLE)
        load_rdf(store, ttl_path)
        assert is_initialized(store_path)


def test_execute_query_non_select_raises():
    """Non-SELECT queries (ASK, CONSTRUCT) raise ValueError."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "store"
        store = get_or_create_store(store_path)
        ttl_path = Path(tmpdir) / "test.ttl"
        ttl_path.write_text(SAMPLE_TURTLE)
        load_rdf(store, ttl_path)

        with pytest.raises(ValueError, match="Only SELECT queries are supported"):
            execute_query(
                store,
                "ASK { ?s ?p ?o }",
            )


def test_get_data_dir_default():
    """Falls back to ~/.local/share/dprr-mcp when no envvars set."""
    from dprr_mcp.store import get_data_dir

    with patch.dict(os.environ, {}, clear=True):
        os.environ.pop("DPRR_DATA_DIR", None)
        os.environ.pop("XDG_DATA_HOME", None)
        result = get_data_dir()
        assert result == Path.home() / ".local" / "share" / "dprr-mcp"


def test_get_data_dir_xdg_data_home():
    """Respects XDG_DATA_HOME when set."""
    from dprr_mcp.store import get_data_dir

    with patch.dict(os.environ, {"XDG_DATA_HOME": "/tmp/xdg"}, clear=True):
        result = get_data_dir()
        assert result == Path("/tmp/xdg/dprr-mcp")


def test_get_data_dir_dprr_data_dir_overrides_xdg():
    """DPRR_DATA_DIR takes precedence over XDG_DATA_HOME."""
    from dprr_mcp.store import get_data_dir

    with patch.dict(os.environ, {"DPRR_DATA_DIR": "/tmp/custom", "XDG_DATA_HOME": "/tmp/xdg"}, clear=True):
        result = get_data_dir()
        assert result == Path("/tmp/custom")


def test_ensure_initialized_uses_data_dir(tmp_path):
    """ensure_initialized uses get_data_dir() to find store and rdf file."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    rdf_file = data_dir / "dprr.ttl"
    rdf_file.write_text(SAMPLE_TURTLE)

    with patch.dict(os.environ, {"DPRR_DATA_DIR": str(data_dir)}, clear=True):
        store = ensure_initialized()
        results = execute_query(store, "SELECT (COUNT(*) AS ?c) WHERE { ?s ?p ?o }")
        assert int(results[0]["c"]) > 0


def test_ensure_initialized_fetches_when_no_ttl(tmp_path):
    """ensure_initialized calls fetch_data when dprr.ttl is missing."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    # No dprr.ttl exists — fetch_data should be called

    def fake_fetch(data_dir, **kwargs):
        (data_dir / "dprr.ttl").write_text(SAMPLE_TURTLE)
        return data_dir / "dprr.ttl"

    with patch.dict(os.environ, {"DPRR_DATA_DIR": str(data_dir)}, clear=True):
        with patch("dprr_mcp.fetch.fetch_data", side_effect=fake_fetch) as mock_fetch:
            store = ensure_initialized()
            mock_fetch.assert_called_once_with(data_dir)
            results = execute_query(store, "SELECT (COUNT(*) AS ?c) WHERE { ?s ?p ?o }")
            assert int(results[0]["c"]) > 0


def test_ensure_initialized_fetch_failure_raises(tmp_path):
    """ensure_initialized raises RuntimeError when fetch fails."""
    data_dir = tmp_path / "empty"
    data_dir.mkdir()

    with patch.dict(os.environ, {"DPRR_DATA_DIR": str(data_dir)}, clear=True):
        with patch("dprr_mcp.fetch.fetch_data", side_effect=RuntimeError("download failed")):
            with pytest.raises(RuntimeError, match="download failed"):
                ensure_initialized()
