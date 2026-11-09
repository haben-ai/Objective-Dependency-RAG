"""Extraction pipeline tests with a scripted stand-in LLM (no API calls)."""

import pytest

from extraction.evidence_checks import quote_in
from extraction.extractors import run_direct, run_rag, run_rag_verify
from extraction.llm_client import LLMCall
from extraction.schema import ExtractionResult, ObjectiveList, VerificationResult

DESC = "A truss has four bars. The engineer can choose the cross-sectional area of each of the four bars. Minimize volume and minimize displacement."


class ScriptedLLM:
    model = "scripted-test-llm"

    def __init__(self, responses: dict):
        self.responses = responses
        self.prompts: dict[str, str] = {}

    def generate(self, purpose, system, prompt, schema):
        self.prompts[purpose] = prompt
        obj = self.responses[purpose](prompt) if callable(self.responses[purpose]) else self.responses[purpose]
        parsed = schema.model_validate(obj)
        return parsed, LLMCall(purpose, self.model, system, prompt, parsed.model_dump_json(), 0.0, 1)


def dep(name, status, evidence=None, src=None, type_="parameter"):
    return {"name": name, "type": type_, "relationship": "r", "evidence_status": status, "evidence": evidence, "source_chunk_id": src}


def extraction(deps_o1, deps_o2=()):
    return {
        "objectives": [
            {"objective_id": "o1", "objective_name": "volume", "direction": "minimize", "dependencies": list(deps_o1)},
            {"objective_id": "o2", "objective_name": "displacement", "direction": "minimize", "dependencies": list(deps_o2)},
        ],
        "open_questions": [],
    }


def test_quote_matching():
    assert quote_in("the cross-sectional area of each", DESC)
    assert quote_in("The  engineer can choose\nthe cross-sectional area", DESC)
    assert not quote_in("modulus of elasticity", DESC)
    assert not quote_in("bars", DESC)  # too short to count as evidence


def test_direct_never_claims_retrieval():
    llm = ScriptedLLM({"extraction": extraction([dep("Length", "retrieved", "L = 200", "fake::chunk")])})
    rec = run_direct(llm, "RE21", "incomplete", DESC)
    d = rec["extraction"]["objectives"][0]["dependencies"][0]
    assert d["evidence_status"] == "inferred" and d["source_chunk_id"] is None
    assert rec["retrieval"] is None
    assert "RETRIEVED PASSAGES" not in llm.prompts["extraction"]


@pytest.fixture(scope="module")
def rag_run():
    def extract(prompt):
        assert "re21::docstring_formulation" in prompt  # passages were retrieved and shown
        return extraction(
            [
                dep("Cross-sectional areas x1-x4", "explicit", "the cross-sectional area of each of the four bars", type_="decision_variable"),
                dep("Length L", "retrieved", "The parameters are defined as $F = 10$ $kN$", "desdeo_re_problem.py::re21::docstring_formulation"),
                dep("Allowable stress", "retrieved", "made up quote that is nowhere", "desdeo_re_problem.py::re21::docstring_formulation"),
                dep("Force F", "retrieved", "f (float, optional): Force (kN). Defaults to 10.0.", "not_retrieved::id"),
            ],
            [dep("Young modulus E", "inferred")],
        )

    llm = ScriptedLLM({"objective_listing": ObjectiveList(objectives=["volume", "displacement"]).model_dump(), "extraction": extract})
    return run_rag(llm, "RE21", "incomplete", DESC, corpus="full")


def test_rag_records_retrieval_and_drops_invalid_citations(rag_run):
    assert rag_run["retrieval"]["passages"] and len(rag_run["retrieval"]["queries"]) == 3
    assert all(p["metadata"]["problem_id"] in ("RE21", "RE_SUITE", "GENERAL") for p in rag_run["retrieval"]["passages"])
    force = rag_run["extraction"]["objectives"][0]["dependencies"][3]
    assert force["source_chunk_id"] is None  # cited a passage that was never retrieved
    checks = {c["dependency"]: c for c in rag_run["evidence_checks"]}
    assert checks["Cross-sectional areas x1-x4"]["quote_in_description"]
    assert checks["Length L"]["quote_in_cited_passage"]
    assert not checks["Allowable stress"]["supported"]


def test_verification_assigns_status_and_removes_contradicted(rag_run):
    verdicts = VerificationResult.model_validate(
        {
            "verdicts": [
                {"objective_id": "o1", "dependency_name": "Cross-sectional areas x1-x4", "verdict": "supported", "supporting_chunk_id": "description", "supporting_quote": "the cross-sectional area of each of the four bars", "explanation": ""},
                {"objective_id": "o1", "dependency_name": "Length L", "verdict": "supported", "supporting_chunk_id": "tanabe_ishibuchi_supplementary_S1.txt::S.1.1.", "supporting_quote": "L = 200 cm, σ = 10 kN/cm2", "explanation": ""},
                {"objective_id": "o1", "dependency_name": "Allowable stress", "verdict": "contradicted", "supporting_chunk_id": "desdeo_re_problem.py::re21::docstring_formulation", "supporting_quote": "where $x_1, x_4 \\in [a, 3a]$", "explanation": "sigma only enters the bounds"},
                {"objective_id": "o1", "dependency_name": "Force F", "verdict": "contradicted", "supporting_chunk_id": "description", "supporting_quote": "this quote is fabricated", "explanation": ""},
            ]
        }
    ).model_dump()
    llm = ScriptedLLM({"verification": verdicts})
    rec = run_rag_verify(llm, "RE21", "incomplete", DESC, rag_run=rag_run)
    table = {(r["objective_id"], r["dependency"]): r for r in rec["verification"]["table"]}
    assert table[("o1", "Cross-sectional areas x1-x4")]["final_status"] == "explicit"
    assert table[("o1", "Length L")]["final_status"] == "retrieved"
    assert table[("o1", "Length L")]["objective_link_established"]
    length = next(d for d in rec["extraction"]["objectives"][0]["dependencies"] if d["name"] == "Length L")
    assert length["evidence"] == "The parameters are defined as $F = 10$ $kN$"  # verified original quote is kept
    assert table[("o1", "Length L")]["link_evidence"] == "L = 200 cm, σ = 10 kN/cm2"
    assert table[("o1", "Allowable stress")]["final_status"] == "removed"
    assert table[("o1", "Force F")]["final_status"] == "inferred"  # contradiction quote unverifiable -> kept, unsupported
    assert "could not be found" in table[("o1", "Force F")]["note"]
    assert table[("o2", "Young modulus E")]["verdict"] is None
    names = [d["name"] for d in rec["extraction"]["objectives"][0]["dependencies"]]
    assert "Allowable stress" not in names
    assert rec["based_on_run"] == rag_run["run_id"]
    assert ExtractionResult.model_validate(rec["extraction"])
