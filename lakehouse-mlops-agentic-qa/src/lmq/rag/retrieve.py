"""Query the vector index and return ranked results."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from lmq.rag.index import load_collection


class RetrievedChunk(BaseModel):
    chunk_id: str
    doc_id: str
    source_path: str
    chunk_index: int
    text: str
    distance: float


def retrieve(question: str, persist_dir: Path, top_k: int = 3) -> list[RetrievedChunk]:
    collection = load_collection(persist_dir)
    results = collection.query(query_texts=[question], n_results=min(top_k, collection.count()))

    chunks: list[RetrievedChunk] = []
    ids = results["ids"][0] if results["ids"] else []
    docs = results["documents"][0] if results["documents"] else []
    metas = results["metadatas"][0] if results["metadatas"] else []
    dists = results["distances"][0] if results["distances"] else []

    for cid, doc, meta, dist in zip(ids, docs, metas, dists):
        chunks.append(
            RetrievedChunk(
                chunk_id=str(cid),
                doc_id=str(meta.get("doc_id", "")),
                source_path=str(meta.get("source_path", "")),
                chunk_index=int(str(meta.get("chunk_index", 0))),
                text=str(doc),
                distance=float(dist),
            )
        )
    return chunks
