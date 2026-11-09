import pytest

from config import SHARED_SCOPES
from retrieval.retriever import retrieve, retrieve_many

QUERIES = [
    "Identify the mathematical parameters and input requirements needed to evaluate the joint displacement objective in RE21.",
    "What is needed to compute the total structural volume of the four bar truss?",
    "Material properties, applied force and bar length of the four-bar truss",
]


@pytest.mark.parametrize("query", QUERIES)
def test_problem_filter_excludes_other_problems(query):
    for p in retrieve(query, "RE21", k=8):
        assert p.metadata["problem_id"] in ("RE21", *SHARED_SCOPES)


@pytest.mark.parametrize("query", QUERIES)
def test_top_result_is_re21_specific_in_full_corpus(query):
    top = retrieve(query, "RE21", k=1)[0]
    assert top.metadata["problem_id"] == "RE21"


def test_corpus_configs_respected():
    assert all(p.metadata["document_type"] != "source_code" for p in retrieve(QUERIES[0], "RE21", k=10, corpus="no_source_code"))
    assert all(p.metadata["document_type"] == "documentation" for p in retrieve(QUERIES[0], "RE21", k=10, corpus="documentation_only"))


def test_displacement_query_finds_f2_definition():
    ids = [p.chunk_id for p in retrieve(QUERIES[0], "RE21", k=5)]
    assert any("objective_definition" in i and "re21" in i for i in ids)


def test_retrieve_many_prioritises_problem_specific_and_deduplicates():
    res = retrieve_many(QUERIES, "RE21", k=6, max_specific=6, max_shared=2)
    assert len({p.chunk_id for p in res}) == len(res)
    specific = [p for p in res if p.metadata["problem_id"] == "RE21"]
    shared = [p for p in res if p.metadata["problem_id"] != "RE21"]
    assert res == specific + shared  # problem-specific passages come first
    assert len(specific) == 6 and len(shared) <= 2
    for group in (specific, shared):
        assert [p.score for p in group] == sorted((p.score for p in group), reverse=True)
