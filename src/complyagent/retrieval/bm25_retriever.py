"""BM25 (sparse/keyword) retrieval over the GDPR chunk corpus.

The index is rebuilt in memory on startup/first use, never persisted to disk -
building it from 882 short chunks is fast enough (milliseconds) that persistence
would add complexity (serialization, staleness-vs-chunks.json tracking) for no
real benefit at this corpus size.

Indexes the same text as the dense embedder (build_embedding_text: article title
prepended for article chunks) so BM25 also benefits from the extra keyword
surface the title provides, e.g. a query mentioning "principles" can literally
match the word "Principles" in Article 5's title even if it doesn't appear in
the chunk's own body text.
"""
from __future__ import annotations

import re

from rank_bm25 import BM25Okapi

from complyagent.retrieval.embeddings import build_embedding_text

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    """Lowercase, extract alphanumeric tokens. No stemming/lemmatization - GDPR
    text isn't morphologically complex enough to need it, and keeping tokenization
    simple keeps BM25's behavior predictable and easy to debug."""
    return _TOKEN_PATTERN.findall(text.lower())


class BM25Retriever:
    """Wraps BM25Okapi with chunk_id tracking, so results come back as
    (chunk_id, score) pairs rather than bare positional indices."""

    def __init__(self, chunks: list[dict]):
        self.chunk_ids = [c["chunk_id"] for c in chunks]
        tokenized_corpus = [tokenize(build_embedding_text(c)) for c in chunks]
        self._bm25 = BM25Okapi(tokenized_corpus)

    def search(self, query: str, k: int) -> list[tuple[str, float]]:
        """Return up to k (chunk_id, score) pairs, ranked by BM25 score descending.
        Chunks with a score of 0 (no keyword overlap at all) are excluded - a zero
        score isn't a meaningful ranking signal and would just be noise in fusion."""
        tokenized_query = tokenize(query)
        scores = self._bm25.get_scores(tokenized_query)

        ranked = sorted(
            zip(self.chunk_ids, scores), key=lambda pair: pair[1], reverse=True
        )
        nonzero_ranked = [(cid, score) for cid, score in ranked if score > 0]
        return nonzero_ranked[:k]


def build_bm25_retriever(chunks: list[dict]) -> BM25Retriever:
    return BM25Retriever(chunks)