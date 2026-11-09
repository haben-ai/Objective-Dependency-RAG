"""Shared paths and settings."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DOCUMENTS = DATA / "documents"
PROCESSED = DATA / "processed"
CHROMA_DIR = PROCESSED / "chroma"
CHUNKS_FILE = PROCESSED / "chunks.jsonl"
DESCRIPTIONS = DATA / "descriptions"
GROUND_TRUTH = DATA / "ground_truth"
RESULTS = ROOT / "results"

COLLECTION = "moo_dependency_corpus"

# Problem scopes used by metadata filtering. Chunks that describe several problems or the framework
# itself are tagged with one of these instead of a single problem id.
SHARED_SCOPES = ("RE_SUITE", "GENERAL")

# Corpus configurations (which document types the retriever may return). Used to measure how much of a
# RAG gain comes from retrieving the formulation itself.
CORPUS_CONFIGS = {
    "full": ["source_code", "literature", "documentation"],
    "no_source_code": ["literature", "documentation"],
    "documentation_only": ["documentation"],
}

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
