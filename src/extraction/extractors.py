"""The three extraction approaches.

A  direct    : description only.
B  rag       : description + passages retrieved from the corpus (same core prompt as A).
C  rag_verify: B's extraction, then an LLM evidence review + deterministic quote checks that assign the final
               evidence status and remove dependencies that the evidence contradicts.

C re-uses B's extraction (when given) so that the difference between B and C isolates the effect of
verification.
"""

import uuid
from datetime import datetime, timezone

from extraction import prompts
from extraction.evidence_checks import check_dependency, normalize, quote_in
from extraction.llm_client import LLM
from extraction.schema import Dependency, ExtractionResult, ObjectiveList, VerificationResult
from retrieval.retriever import RetrievedPassage, retrieve_many

PASSAGES_PER_QUERY = 6
MAX_PASSAGES = 8

INFORMATION_ACCESS = {
    "direct": "Problem description only.",
    "rag": "Problem description + passages retrieved from the corpus (filtered to the selected problem and shared docs).",
    "rag_verify": "Same as rag; the verifier sees the same description and passages. Ground truth is never visible.",
}


def _record(method: str, problem_id: str, variant: str, description: str, llm: LLM, corpus: str | None) -> dict:
    return {
        "run_id": f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}_{method}_{variant}_{uuid.uuid4().hex[:6]}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "problem_id": problem_id,
        "method": method,
        "description_variant": variant,
        "description": description,
        "model": llm.model,
        "corpus": corpus,
        "information_access": INFORMATION_ACCESS[method],
        "llm_calls": [],
    }


def _passages_dict(passages: list[RetrievedPassage]) -> dict[str, str]:
    return {p.chunk_id: p.content for p in passages}


def _evidence_report(result: ExtractionResult, description: str, passages: dict[str, str]) -> list[dict]:
    return [
        {"objective_id": o.objective_id, "dependency": d.name, "claimed_status": d.evidence_status, **check_dependency(d, description, passages)}
        for o in result.objectives
        for d in o.dependencies
    ]


def _passage_record(p: RetrievedPassage) -> dict:
    return {"chunk_id": p.chunk_id, "score": round(p.score, 4), "why": p.why, "metadata": p.metadata, "content": p.content}


# ------------------------------------------------------------------------------------------- A: direct


def run_direct(llm: LLM, problem_id: str, variant: str, description: str) -> dict:
    rec = _record("direct", problem_id, variant, description, llm, corpus=None)
    system, prompt = prompts.direct_prompt(description)
    result, call = llm.generate("extraction", system, prompt, ExtractionResult)
    # The baseline has no documents: any 'retrieved' claim is invalid by construction.
    for o in result.objectives:
        for d in o.dependencies:
            if d.evidence_status == "retrieved" or d.source_chunk_id:
                d.evidence_status, d.source_chunk_id = "inferred", None
    rec["llm_calls"].append(vars(call))
    rec["retrieval"] = None
    rec["extraction"] = result.model_dump()
    rec["evidence_checks"] = _evidence_report(result, description, {})
    return rec


# ------------------------------------------------------------------------------------------- B: RAG


def build_queries(objective_names: list[str], description: str) -> list[str]:
    first_sentence = description.strip().split(".")[0]
    queries = [f"Problem definition, parameters and constants: {first_sentence}"]
    queries += [
        f"Decision variables, parameters and formula needed to evaluate the objective: {name}" for name in objective_names
    ]
    return queries


def run_rag(llm: LLM, problem_id: str, variant: str, description: str, corpus: str = "full") -> dict:
    rec = _record("rag", problem_id, variant, description, llm, corpus=corpus)
    objs, call = llm.generate("objective_listing", prompts.OBJECTIVES_SYSTEM, prompts.format_description(description), ObjectiveList)
    rec["llm_calls"].append(vars(call))

    queries = build_queries(objs.objectives, description)
    passages = retrieve_many(queries, problem_id, k=PASSAGES_PER_QUERY, corpus=corpus, max_specific=6, max_shared=MAX_PASSAGES - 6)

    system, prompt = prompts.rag_prompt(description, passages)
    result, call = llm.generate("extraction", system, prompt, ExtractionResult)
    rec["llm_calls"].append(vars(call))

    pdict = _passages_dict(passages)
    for o in result.objectives:  # a cited passage that was never retrieved is not a valid source
        for d in o.dependencies:
            if d.source_chunk_id and d.source_chunk_id not in pdict:
                d.source_chunk_id = None
    rec["retrieval"] = {"queries": queries, "passages": [_passage_record(p) for p in passages]}
    rec["extraction"] = result.model_dump()
    rec["evidence_checks"] = _evidence_report(result, description, pdict)
    return rec


# ------------------------------------------------------------------------------------------- C: RAG + verification


def _key(objective_id: str, name: str) -> tuple[str, str]:
    return objective_id, normalize(name)


def run_rag_verify(
    llm: LLM, problem_id: str, variant: str, description: str, corpus: str = "full", rag_run: dict | None = None
) -> dict:
    if rag_run is None:
        rag_run = run_rag(llm, problem_id, variant, description, corpus)
    rec = _record("rag_verify", problem_id, variant, description, llm, corpus=corpus)
    rec["based_on_run"] = rag_run["run_id"]
    rec["llm_calls"] = list(rag_run["llm_calls"])
    rec["retrieval"] = rag_run["retrieval"]

    extraction = ExtractionResult.model_validate(rag_run["extraction"])
    passages = {p["chunk_id"]: p["content"] for p in rag_run["retrieval"]["passages"]}

    system, prompt = prompts.verify_prompt(
        description,
        [RetrievedPassage(p["chunk_id"], p["content"], p["score"], p["metadata"], "", "") for p in rag_run["retrieval"]["passages"]],
        extraction.model_dump_json(indent=1),
    )
    review, call = llm.generate("verification", system, prompt, VerificationResult)
    rec["llm_calls"].append(vars(call))
    verdicts = {_key(v.objective_id, v.dependency_name): v for v in review.verdicts}

    def verdict_quote_ok(v) -> bool:
        src = description if v.supporting_chunk_id == "description" else passages.get(v.supporting_chunk_id or "", "")
        return quote_in(v.supporting_quote, src)

    table, removed = [], []
    for o in extraction.objectives:
        kept: list[Dependency] = []
        for d in o.dependencies:
            det = check_dependency(d, description, passages)
            v = verdicts.get(_key(o.objective_id, d.name))
            v_ok = bool(v and verdict_quote_ok(v))
            original = d.evidence_status
            note = ""
            if v and v.verdict == "contradicted" and v_ok:
                removed.append({"objective_id": o.objective_id, "dependency": d.model_dump(), "reason": v.explanation, "quote": v.supporting_quote, "source": v.supporting_chunk_id})
                table.append({"objective_id": o.objective_id, "dependency": d.name, "original_status": original, "final_status": "removed", "verdict": "contradicted", "verified_quote": True, "note": v.explanation})
                continue
            # The extractor's own quote is kept whenever it can be verified (it shows the component exists);
            # the verifier's quote is recorded separately as evidence that the component is used by THIS objective.
            link_ok = bool(v and v.verdict == "supported" and v_ok)
            if det["quote_in_description"]:
                d.evidence_status, d.source_chunk_id = "explicit", None
            elif det["quote_found_in"]:
                d.evidence_status, d.source_chunk_id = "retrieved", det["quote_found_in"]
            elif link_ok and v.supporting_chunk_id == "description":
                d.evidence_status, d.evidence, d.source_chunk_id = "explicit", v.supporting_quote, None
            elif link_ok:
                d.evidence_status, d.evidence, d.source_chunk_id = "retrieved", v.supporting_quote, v.supporting_chunk_id
            elif original == "unknown":
                pass
            else:
                d.evidence_status, d.evidence, d.source_chunk_id = "inferred", None, None
                note = "no verifiable evidence"
            if v and v.verdict == "contradicted" and not v_ok:
                note = "verifier claimed contradiction but its quote could not be found; kept"
            if v is None:
                note = (note + "; " if note else "") + "verifier returned no verdict"
            elif d.evidence_status in ("explicit", "retrieved") and not link_ok:
                note = (note + "; " if note else "") + "component exists in evidence, but its use for this objective is not established"
            table.append({
                "objective_id": o.objective_id,
                "dependency": d.name,
                "original_status": original,
                "final_status": d.evidence_status,
                "verdict": v.verdict if v else None,
                "verified_quote": v_ok,
                "objective_link_established": link_ok,
                "link_evidence": v.supporting_quote if link_ok else None,
                "link_source": v.supporting_chunk_id if link_ok else None,
                "note": note,
            })
            kept.append(d)
        o.dependencies = kept

    rec["verification"] = {"table": table, "removed": removed, "raw_verdicts": review.model_dump()}
    rec["extraction"] = extraction.model_dump()
    rec["evidence_checks"] = _evidence_report(extraction, description, passages)
    return rec
