"""Populate a persistent ChromaDB collection from data/processed/chunks.json.

Computes embeddings ourselves (via embed_texts) and hands Chroma raw vectors,
rather than using Chroma's built-in embedding function - gives us independent
testability and control over exactly what text gets embedded (see
build_embedding_text in embeddings.py).

Run from repo root:
    uv run python scripts/build_vector_store.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import chromadb

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from complyagent.config import settings
from complyagent.retrieval.embeddings import build_embedding_text, embed_texts

CHUNKS_PATH = REPO_ROOT / "data" / "processed" / "chunks.json"


def clean_metadata(chunk: dict) -> dict:
    """Chroma rejects None values in metadata - omit any key whose value is None
    rather than encoding a placeholder. Absence of a key correctly reflects that
    the field doesn't apply to this chunk (e.g. recitals have no `paragraph`)."""
    keys = [
        "chunk_id", "source_type", "article_number", "recital_number",
        "article_title", "paragraph", "point", "chapter",
    ]
    return {k: chunk[k] for k in keys if chunk.get(k) is not None}


def main() -> int:
    print(f"Loading chunks from {CHUNKS_PATH} ...")
    chunks = json.loads(CHUNKS_PATH.read_text(encoding="utf-8"))
    print(f"  {len(chunks)} chunks loaded.")

    print("Building embedding texts ...")
    embedding_texts = [build_embedding_text(c) for c in chunks]

    print(f"Computing embeddings with {settings.retrieval.embedding_model} (this may take a while on first run) ...")
    vectors = embed_texts(embedding_texts, model_name=settings.retrieval.embedding_model)
    print(f"  Computed {len(vectors)} vectors of dimension {len(vectors[0])}.")

    print(f"Connecting to persistent Chroma store at {settings.paths.chroma_persist_dir} ...")
    client = chromadb.PersistentClient(path=settings.paths.chroma_persist_dir)

    collection_name = settings.retrieval.collection_name
    existing = [c.name for c in client.list_collections()]
    if collection_name in existing:
        print(f"  Collection '{collection_name}' already exists - deleting for a clean rebuild.")
        client.delete_collection(collection_name)

    collection = client.create_collection(collection_name)

    ids = [c["chunk_id"] for c in chunks]
    documents = [c["text"] for c in chunks]
    metadatas = [clean_metadata(c) for c in chunks]

    print(f"Adding {len(ids)} chunks to collection '{collection_name}' ...")
    collection.add(ids=ids, embeddings=vectors, documents=documents, metadatas=metadatas)

    count = collection.count()
    print(f"\nDone. Collection '{collection_name}' now contains {count} chunks.")

    sample = collection.get(ids=["GDPR-Art-5-1-a"], include=["documents", "metadatas"])
    if sample["ids"]:
        print("\nSanity check (GDPR-Art-5-1-a):")
        print(f"  document: {sample['documents'][0][:80]}...")
        print(f"  metadata: {sample['metadatas'][0]}")
    else:
        print("\nWARNING: sanity-check chunk_id 'GDPR-Art-5-1-a' not found in collection.")

    return 0


if __name__ == "__main__":
    sys.exit(main())