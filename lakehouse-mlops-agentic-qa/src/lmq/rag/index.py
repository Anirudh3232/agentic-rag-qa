"""Build and load a ChromaDB vector index from gold chunks."""

from __future__ import annotations

from pathlib import Path

import chromadb

from lmq.rag.chunking import GoldChunk

COLLECTION_NAME = "gold_chunks"
_BATCH_SIZE = 500


def build_index(chunks: list[GoldChunk], persist_dir: Path) -> int:
    """Create (or replace) a ChromaDB collection from gold chunks.

    Returns the number of documents inserted.
    """
    persist_dir.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(persist_dir))

    # Drop existing collection so rebuilds are idempotent.
    if COLLECTION_NAME in [c.name for c in client.list_collections()]:
        client.delete_collection(COLLECTION_NAME)

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    for start in range(0, len(chunks), _BATCH_SIZE):
        batch = chunks[start : start + _BATCH_SIZE]
        collection.add(
            ids=[c.chunk_id for c in batch],
            documents=[c.text for c in batch],
            metadatas=[
                {"doc_id": c.doc_id, "chunk_index": c.chunk_index, "source_path": c.source_path}
                for c in batch
            ],
        )

    return collection.count()


def load_collection(persist_dir: Path) -> chromadb.Collection:
    if not persist_dir.is_dir():
        msg = f"Chroma persist dir not found: {persist_dir}"
        raise FileNotFoundError(msg)
    client = chromadb.PersistentClient(path=str(persist_dir))
    return client.get_collection(name=COLLECTION_NAME)
