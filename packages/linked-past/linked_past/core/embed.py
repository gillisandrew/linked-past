"""Lazy-loaded text embedding via FastEmbed."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
VECTOR_DIM = 384

class Embedder:
    """Wraps FastEmbed TextEmbedding with lazy model loading."""

    def __init__(self) -> None:
        self._model = None

    def _load(self):
        if self._model is None:
            from fastembed import TextEmbedding

            logger.info("Loading embedding model %s...", EMBED_MODEL)
            self._model = TextEmbedding(model_name=EMBED_MODEL)
            logger.info("Embedding model loaded")

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts. Returns list of float vectors."""
        self._load()
        return [vec.tolist() if hasattr(vec, "tolist") else list(vec) for vec in self._model.embed(texts)]

    def embed_single(self, text: str) -> list[float]:
        """Embed a single text. Returns one float vector."""
        return self.embed([text])[0]
