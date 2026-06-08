"""Tests for hybrid example search in validate_sparql."""

from unittest.mock import MagicMock, patch

from linked_past.core.server import _get_example_context


def test_get_example_context_uses_hybrid_search():
    """When search index is available, uses hybrid_search for examples."""
    search_index = MagicMock()
    vector_index = MagicMock()
    embedder = MagicMock()
    embedder.embed_single.return_value = [0.1] * 384

    with patch("linked_past.core.server.hybrid_search") as mock_hs:
        mock_hs.return_value = [
            {"dataset": "dprr", "doc_type": "example", "text": "List all consuls\nSELECT ?p WHERE { ?p a dprr:Person }"},
        ]
        result = _get_example_context(
            sparql="SELECT ?p WHERE { ?p a dprr:Person }",
            dataset="dprr",
            search_index=search_index,
            vector_index=vector_index,
            embedder=embedder,
        )

    assert "List all consuls" in result
    mock_hs.assert_called_once()
    call_kwargs = mock_hs.call_args
    assert call_kwargs.kwargs["dataset"] == "dprr"
    assert call_kwargs.kwargs["doc_type"] == "example"
    assert call_kwargs.kwargs["k"] == 3


def test_get_example_context_returns_empty_when_no_results():
    """When hybrid search finds nothing, returns empty string."""
    search_index = MagicMock()
    embedder = MagicMock()
    embedder.embed_single.return_value = [0.1] * 384

    with patch("linked_past.core.server.hybrid_search") as mock_hs:
        mock_hs.return_value = []
        result = _get_example_context(
            sparql="SELECT ?x WHERE { ?x ?p ?o }",
            dataset="dprr",
            search_index=search_index,
            vector_index=None,
            embedder=embedder,
        )

    assert result == ""


def test_get_example_context_returns_empty_when_no_search_index():
    """When search index is None, returns empty string."""
    result = _get_example_context(
        sparql="SELECT ?x WHERE { ?x ?p ?o }",
        dataset="dprr",
        search_index=None,
        vector_index=None,
        embedder=None,
    )
    assert result == ""
