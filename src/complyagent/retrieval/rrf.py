"""Reciprocal Rank Fusion (RRF) - combines BM25 (sparse) and dense embedding
rankings into one unified ranking.

We use WEIGHTED RRF, not textbook RRF (Cormack et al., which sums 1/(rank+k)
unweighted across lists). This is a deliberate choice to honor the
retrieval.bm25_weight / retrieval.dense_weight config values, which wouldn't mean
anything under unweighted RRF. BM25 scores (unbounded, corpus-statistics-dependent)
and dense cosine similarities (bounded 0-1) are NOT on comparable scales, which is
exactly why we fuse by RANK POSITION rather than combining raw scores directly -
rank position is the one thing both methods produce in a directly comparable form.
"""
from __future__ import annotations

RRF_CONSTANT = 60  # standard smoothing constant from RRF literature; prevents
                     # rank-1 results from dominating too extremely


def weighted_rrf_fuse(
    bm25_results: list[tuple[str, float]],
    dense_results: list[tuple[str, float]],
    bm25_weight: float,
    dense_weight: float,
    constant: int = RRF_CONSTANT,
) -> list[tuple[str, float]]:
    """Fuse two ranked result lists into one, by weighted reciprocal rank.

    bm25_results / dense_results: lists of (chunk_id, score) already sorted best
    -> worst by their respective methods. The actual score values are ignored -
    only RANK POSITION (1-indexed) is used, since BM25 and dense scores aren't on
    comparable scales.

    Returns a list of (chunk_id, fused_score) sorted best -> worst. A chunk that
    appears in only one input list still gets included, with only that list's
    weighted contribution (the other term is simply absent, not zero-penalized).
    """
    fused_scores: dict[str, float] = {}

    for rank, (chunk_id, _score) in enumerate(bm25_results, start=1):
        fused_scores[chunk_id] = fused_scores.get(chunk_id, 0.0) + bm25_weight * (1.0 / (rank + constant))

    for rank, (chunk_id, _score) in enumerate(dense_results, start=1):
        fused_scores[chunk_id] = fused_scores.get(chunk_id, 0.0) + dense_weight * (1.0 / (rank + constant))

    ranked = sorted(fused_scores.items(), key=lambda pair: pair[1], reverse=True)
    return ranked