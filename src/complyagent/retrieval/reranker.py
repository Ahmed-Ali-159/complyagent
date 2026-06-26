"""Cross-encoder reranking - the final precision stage of retrieval.

Takes the RRF-fused candidates (typically initial_k=20) and rescales them using a
cross-encoder, which jointly attends over (query, document) pairs rather than
comparing precomputed vectors. More accurate than embedding similarity alone, but
slower per-pair - which is exactly why we only apply it to the already-narrowed
top-k candidates, not the full corpus.

Uses the same build_embedding_text() (article title prepended) as BM25 and the
dense embedder, for the same reason: the title is genuinely informative context,
and there's no reason to withhold it from the most accurate stage of the pipeline.
"""
from __future__ import annotations

from sentence_transformers import CrossEncoder

from complyagent.retrieval.embeddings import build_embedding_text

_reranker: CrossEncoder | None = None


def get_reranker_model(model_name: str) -> CrossEncoder:
    global _reranker
    if _reranker is None:
        _reranker = CrossEncoder(model_name)
    return _reranker


def rerank(
    query: str,
    candidate_chunks: list[dict],
    model_name: str,
    top_k: int,
) -> list[tuple[str, float]]:
    """Rerank candidate chunks against the query using a cross-encoder.

    candidate_chunks: list of chunk dicts (or RegulationChunk instances) - the
    RRF-fused top-k candidates, already resolved to their full content (not just
    IDs), since the cross-encoder needs the actual text to score each pair.

    Returns up to top_k (chunk_id, reranker_score) pairs, sorted best -> worst.
    """
    if not candidate_chunks:
        return []

    model = get_reranker_model(model_name)

    pairs = [(query, build_embedding_text(c)) for c in candidate_chunks]
    scores = model.predict(pairs)

    chunk_ids = [
        c.chunk_id if hasattr(c, "chunk_id") else c["chunk_id"]
        for c in candidate_chunks
    ]

    ranked = sorted(zip(chunk_ids, scores), key=lambda pair: pair[1], reverse=True)
    return ranked[:top_k]