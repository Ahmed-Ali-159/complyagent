"""Embeddings module: turns RegulationChunk objects into embedding-ready text, and
wraps the sentence-transformers model for computing dense vectors.

Design decisions:
  - Embedding TEXT differs from the chunk's stored `text` field. We prepend the
    article's title for article chunks (genuinely semantic context that helps
    retrieval), but never the bare article number or chapter roman numeral (both
    are semantically empty labels that would only dilute the embedding signal).
  - Recital chunks have no title field, so their embedding text is just their
    raw text, unchanged.
  - We precompute embeddings ourselves (not via Chroma's built-in embedding
    function) for independent testability and control.
"""
from __future__ import annotations

from sentence_transformers import SentenceTransformer

# Lazy-loaded singleton - the model is ~440MB and slow to load; we don't want to
# reload it on every call. Loaded once on first use, reused after that.
_model: SentenceTransformer | None = None


def get_embedding_model(model_name: str) -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(model_name)
    return _model


def build_embedding_text(chunk) -> str:
    """Build the text actually fed to the embedding model for one RegulationChunk.

    Accepts either a RegulationChunk instance or a plain dict with the same keys
    (dicts are supported so this function is testable without a full schema
    dependency, and usable during the Chroma-population script either way).
    """
    if hasattr(chunk, "source_type"):
        source_type = chunk.source_type
        article_title = chunk.article_title
        text = chunk.text
    else:
        source_type = chunk["source_type"]
        article_title = chunk.get("article_title")
        text = chunk["text"]

    if source_type == "article" and article_title:
        return f"{article_title}. {text}"
    return text


def embed_texts(texts: list[str], model_name: str, batch_size: int = 32) -> list[list[float]]:
    """Embed a batch of texts, returning plain Python lists (not numpy arrays) -
    this is the format Chroma expects when we hand it precomputed vectors directly.
    """
    model = get_embedding_model(model_name)
    embeddings = model.encode(texts, batch_size=batch_size, show_progress_bar=False)
    return embeddings.tolist()