"""ChromaDB persistent store with a local embedding model.

Embeddings: Chroma's default embedding function (all-MiniLM-L6-v2, ONNX runtime, runs locally; the model is
downloaded once on first use). Distance: cosine.
"""

import chromadb
from chromadb.utils import embedding_functions

from config import CHROMA_DIR, COLLECTION

EMBEDDING_MODEL = "all-MiniLM-L6-v2 (Chroma DefaultEmbeddingFunction, ONNX)"

_client = None


def client() -> chromadb.ClientAPI:
    global _client
    if _client is None:
        CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return _client


def get_collection():
    return client().get_or_create_collection(
        COLLECTION,
        embedding_function=embedding_functions.DefaultEmbeddingFunction(),
        metadata={"hnsw:space": "cosine"},
    )


def reset_collection() -> None:
    try:
        client().delete_collection(COLLECTION)
    except Exception:  # collection did not exist yet
        pass
