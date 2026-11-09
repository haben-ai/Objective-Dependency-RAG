import json

from config import CHUNKS_FILE, DOCUMENTS
from ingestion.indexing import build_chunks


def test_ground_truth_never_in_corpus():
    manifest = json.loads((DOCUMENTS / "SOURCES.json").read_text())
    assert not any("ground_truth" in m["file"] for m in manifest)
    for c in build_chunks():
        assert "required_dependencies" not in c.content and "matching_rules" not in c.content


def test_re21_chunks_have_expected_structure():
    chunks = [c for c in build_chunks() if c.problem_id == "RE21"]
    types = {c.component_type for c in chunks}
    assert {"docstring_formulation", "docstring_parameters", "decision_variables", "objective_definition", "literature_problem_definition"} <= types
    objectives = {c.objective_id for c in chunks if c.component_type == "objective_definition"}
    assert objectives == {"f1", "f2"}
    f2 = next(c for c in chunks if c.objective_id == "f2")
    assert "f_2 = Objective(" in f2.content and "Sqrt" not in f2.content


def test_metadata_complete_and_ids_unique():
    chunks = build_chunks()
    assert len({c.chunk_id for c in chunks}) == len(chunks)
    for c in chunks:
        m = c.metadata()
        assert all(m[k] for k in ("problem_id", "objective_id", "component_type", "source_file", "source_section", "document_type"))


def test_index_file_matches_chunks():
    assert CHUNKS_FILE.exists(), "run: PYTHONPATH=src python -m ingestion.indexing"
    assert sum(1 for _ in CHUNKS_FILE.open()) == len(build_chunks())
