"""Semantic retrieval with metadata filtering by problem scope and corpus configuration."""

from dataclasses import dataclass

from config import CORPUS_CONFIGS, SHARED_SCOPES
from retrieval.vector_store import get_collection


@dataclass
class RetrievedPassage:
    chunk_id: str
    content: str
    score: float  # cosine similarity (1 - cosine distance)
    metadata: dict
    query: str
    filter_description: str

    @property
    def why(self) -> str:
        m = self.metadata
        return (
            f"Matched query '{self.query}' (similarity {self.score:.3f}); "
            f"allowed by filter [{self.filter_description}]; "
            f"{m['component_type']} from {m['source_file']} / {m['source_section']}"
        )


def _where(problem_id: str, corpus: str, include_shared: bool, scopes: list[str] | None = None) -> dict:
    if scopes is None:
        scopes = [problem_id, *SHARED_SCOPES] if include_shared else [problem_id]
    return {
        "$and": [
            {"problem_id": {"$in": scopes}},
            {"document_type": {"$in": CORPUS_CONFIGS[corpus]}},
        ]
    }


def retrieve(
    query: str,
    problem_id: str,
    k: int = 5,
    corpus: str = "full",
    include_shared: bool = True,
    scopes: list[str] | None = None,
) -> list[RetrievedPassage]:
    where = _where(problem_id, corpus, include_shared, scopes)
    desc = f"problem_id in {where['$and'][0]['problem_id']['$in']}; document_type in {CORPUS_CONFIGS[corpus]}"
    res = get_collection().query(query_texts=[query], n_results=k, where=where)
    return [
        RetrievedPassage(
            chunk_id=cid,
            content=doc,
            score=1.0 - dist,
            metadata=meta,
            query=query,
            filter_description=desc,
        )
        for cid, doc, dist, meta in zip(
            res["ids"][0], res["documents"][0], res["distances"][0], res["metadatas"][0], strict=True
        )
    ]


def _merge(passages: list[RetrievedPassage]) -> list[RetrievedPassage]:
    best: dict[str, RetrievedPassage] = {}
    for p in passages:
        if p.chunk_id not in best or p.score > best[p.chunk_id].score:
            best[p.chunk_id] = p
    return sorted(best.values(), key=lambda p: -p.score)


def retrieve_many(
    queries: list[str],
    problem_id: str,
    k: int = 5,
    corpus: str = "full",
    max_specific: int = 6,
    max_shared: int = 2,
) -> list[RetrievedPassage]:
    """Run several queries; problem-specific passages are prioritised over shared (suite/framework) docs.

    Each chunk is kept once at its best score. Returns up to `max_specific` passages tagged with `problem_id`
    followed by up to `max_shared` passages from shared scopes, each group sorted by score.
    """
    specific = _merge([p for q in queries for p in retrieve(q, problem_id, k=k, corpus=corpus, scopes=[problem_id])])
    shared = _merge([p for q in queries for p in retrieve(q, problem_id, k=k, corpus=corpus, scopes=list(SHARED_SCOPES))])
    return specific[:max_specific] + shared[:max_shared]
