"""The public retrieval API: retrieve(query, k) -> list[RegulationChunk].

Pipeline: BM25 top-N + dense top-N -> weighted RRF fusion -> cross-encoder rerank
-> top-k. Chunk content (for reranking input and the final return value) is
resolved from an in-memory {chunk_id: RegulationChunk} lookup built once from
chunks.json at module load, rather than re-querying Chroma for content we can
just hold in memory - Chroma is used purely for its vector index here, not as
the source of truth for chunk content.
"""
from __future__ import annotations

import json
from pathlib import Path

import chromadb

from complyagent.config import settings
from complyagent.retrieval.bm25_retriever import BM25Retriever, build_bm25_retriever
from complyagent.retrieval.embeddings import embed_texts
from complyagent.retrieval.reranker import rerank
from complyagent.retrieval.rrf import chroma_results_to_ranked_list, weighted_rrf_fuse
from complyagent.schemas import RegulationChunk

CHUNKS_PATH = Path(settings.paths.processed_dir) / "chunks.json"

_chunks_by_id: dict[str, RegulationChunk] | None = None
_bm25_retriever: BM25Retriever | None = None
_chroma_collection = None


def _ensure_initialized() -> None:
    global _chunks_by_id, _bm25_retriever, _chroma_collection

    if _chunks_by_id is None or _bm25_retriever is None:
        raw_chunks = json.loads(CHUNKS_PATH.read_text(encoding="utf-8"))
        if _chunks_by_id is None:
            _chunks_by_id = {c["chunk_id"]: RegulationChunk(**c) for c in raw_chunks}
        if _bm25_retriever is None:
            _bm25_retriever = build_bm25_retriever(raw_chunks)

    if _chroma_collection is None:
        client = chromadb.PersistentClient(path=settings.paths.chroma_persist_dir)
        _chroma_collection = client.get_collection(settings.retrieval.collection_name)


def retrieve(query: str, k: int | None = None) -> list[RegulationChunk]:
    """Hybrid retrieval over the GDPR corpus: BM25 + dense + RRF fusion + rerank.

    Returns up to k RegulationChunk objects, ranked best -> worst. Defaults to
    settings.retrieval.final_k if k is not given.
    """
    _ensure_initialized()
    assert _chunks_by_id is not None and _bm25_retriever is not None and _chroma_collection is not None

    initial_k = settings.retrieval.initial_k
    final_k = k if k is not None else settings.retrieval.final_k

    bm25_results = _bm25_retriever.search(query, k=initial_k)

    query_vector = embed_texts([query], model_name=settings.retrieval.embedding_model)[0]
    chroma_raw = _chroma_collection.query(query_embeddings=[query_vector], n_results=initial_k)
    dense_results = chroma_results_to_ranked_list(chroma_raw)

    fused = weighted_rrf_fuse(
        bm25_results,
        dense_results,
        bm25_weight=settings.retrieval.bm25_weight,
        dense_weight=settings.retrieval.dense_weight,
    )

    fused_top = fused[:initial_k]
    candidate_chunks = [
        _chunks_by_id[chunk_id] for chunk_id, _score in fused_top if chunk_id in _chunks_by_id
    ]

    reranked = rerank(
        query,
        candidate_chunks,
        model_name=settings.retrieval.reranker_model,
        top_k=final_k,
    )

    return [_chunks_by_id[chunk_id] for chunk_id, _score in reranked if chunk_id in _chunks_by_id]

def get_chunk_by_id(chunk_id: str) -> RegulationChunk | None:
    """Look up a single RegulationChunk by its ID.

    Returns None if the chunk_id is not in the corpus. Triggers lazy
    initialization of the in-memory chunk store on first call.
    """
    _ensure_initialized()
    assert _chunks_by_id is not None
    return _chunks_by_id.get(chunk_id)