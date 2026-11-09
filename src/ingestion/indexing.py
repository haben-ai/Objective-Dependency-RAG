"""Build the ChromaDB index from the source documents.

Usage:  python -m ingestion.indexing   (with src/ on PYTHONPATH)
"""

import json

from config import CHUNKS_FILE, PROCESSED
from ingestion.document_loader import load_documents
from ingestion.document_processor import Chunk, chunk_document
from retrieval.vector_store import get_collection, reset_collection


def build_chunks() -> list[Chunk]:
    chunks = [c for doc in load_documents() for c in chunk_document(doc)]
    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids)), "duplicate chunk ids"
    return chunks


def build_index() -> int:
    chunks = build_chunks()
    PROCESSED.mkdir(parents=True, exist_ok=True)
    with CHUNKS_FILE.open("w") as f:
        for c in chunks:
            f.write(json.dumps({"content": c.content, **c.metadata()}) + "\n")
    reset_collection()
    col = get_collection()
    batch = 64
    for i in range(0, len(chunks), batch):
        part = chunks[i : i + batch]
        col.add(ids=[c.chunk_id for c in part], documents=[c.content for c in part], metadatas=[c.metadata() for c in part])
    return len(chunks)


if __name__ == "__main__":
    n = build_index()
    print(f"indexed {n} chunks -> {CHUNKS_FILE}")
