"""Tests for the embedding helper. Does NOT load the actual model — tests the interface only."""

from unittest.mock import MagicMock, patch

from linked_past.core.embed import Embedder, EMBED_MODEL, VECTOR_DIM


def test_embedder_lazy_init():
    """Model is not loaded until embed() is called."""
    embedder = Embedder()
    assert embedder._model is None


def test_embed_calls_model():
    """embed() delegates to the FastEmbed model and returns list of lists."""
    embedder = Embedder()
    fake_vectors = [[0.1] * VECTOR_DIM, [0.2] * VECTOR_DIM]

    with patch("fastembed.TextEmbedding") as mock_cls:
        mock_model = MagicMock()
        mock_model.embed.return_value = iter(fake_vectors)
        mock_cls.return_value = mock_model

        result = embedder.embed(["hello", "world"])

    assert len(result) == 2
    assert len(result[0]) == VECTOR_DIM
    mock_cls.assert_called_once_with(model_name=EMBED_MODEL)


def test_embed_single():
    """embed_single() returns a single vector."""
    embedder = Embedder()
    fake_vector = [0.1] * VECTOR_DIM

    with patch("fastembed.TextEmbedding") as mock_cls:
        mock_model = MagicMock()
        mock_model.embed.return_value = iter([fake_vector])
        mock_cls.return_value = mock_model

        result = embedder.embed_single("hello")

    assert len(result) == VECTOR_DIM
