"""Map extracted dependencies to ground-truth entities (the only step that uses an LLM in evaluation).

The judge only decides WHICH reference entity an extracted item denotes. Whether that is correct for the
objective, and all metrics, are computed deterministically in dependency_matcher.py / metrics.py.

Safeguards (ground-truth rule R10):
  * the judge model must differ from the model that produced the run;
  * every judgment is cached in results/judgments/<run_id>.json so it can be inspected and re-used;
  * manual corrections in data/annotations/match_overrides.json take precedence over the judge.
"""

import json
import os
from typing import Literal

from pydantic import BaseModel, Field

from config import DATA, GROUND_TRUTH, RESULTS
from extraction.evidence_checks import normalize
from extraction.llm_client import LLM, GeminiLLM, log

JUDGE_MODEL = os.environ.get("JUDGE_MODEL", "gemini-3.5-flash")
JUDGMENTS = RESULTS / "judgments"
OVERRIDES = DATA / "annotations" / "match_overrides.json"

Category = Literal["matches_entity", "vague", "not_in_implementation", "incorrect"]


class ObjectiveMapping(BaseModel):
    extracted_objective_id: str
    reference_objective_id: str | None = Field(description="Reference objective id, or null if it corresponds to none.")


class ItemJudgment(BaseModel):
    extracted_objective_id: str
    dependency_name: str = Field(description="Copied exactly from the extraction.")
    entity_ids: list[str] = Field(description="Reference entity ids this item denotes (several only for an explicit group). Empty if none.")
    category: Category
    type_correct: bool = Field(description="Whether the extracted type equals the matched entity's type. True if no match.")
    meaning_error: bool = Field(description="True if it identifies the entity but states a wrong physical meaning.")
    explanation: str


class Judgment(BaseModel):
    objective_mapping: list[ObjectiveMapping]
    items: list[ItemJudgment]


JUDGE_SYSTEM = """You are an annotator mapping an LLM's extracted objective dependencies onto a reference list of
entities for a multiobjective optimization problem. You do NOT decide whether an item is a correct dependency
of its objective; you only decide which reference entity (if any) each extracted item DENOTES.

1. Map every extracted objective to the reference objective with the same meaning (or null).
2. For every extracted dependency item, list the reference entity ids it denotes:
   - Same underlying quantity, not just similar wording. "stress" is not the elastic modulus; "length" is L only
     if it denotes the bar/member length.
   - An item that explicitly covers several entities (e.g. "cross-sectional areas of the four bars") lists all of
     them. An item covering only some lists only those.
   - An item describing how the objective is computed from its inputs (a formula, an equation, a sum of terms)
     denotes the reference expression entity for that quantity (volume expression / displacement expression).
     Different coefficients do not matter for the mapping.
   - A generic, category-level item that does not identify a specific quantity ("material properties",
     "geometry", "boundary conditions") denotes nothing: category "vague". If such an item names several things
     of which some are specific reference quantities, list only those it names specifically.
   - A plausible engineering component that the reference does not contain (e.g. a finite element model,
     density, node coordinates) denotes nothing: category "not_in_implementation".
   - Anything else that denotes no reference entity: category "incorrect".
   - When entity_ids is non-empty, category is "matches_entity".
3. type_correct: compare the extracted type with the reference entity type.
4. meaning_error: true when the item clearly points at a reference entity but describes it with a wrong
   physical meaning (e.g. calling the cross-sectional areas "bar lengths").
Return one item judgment for EVERY extracted dependency, copying objective ids and names exactly."""


def _reference_view(gt: dict) -> str:
    ents = [
        {k: e[k] for k in ("id", "type", "name", "aliases") if k in e} | ({"expression": e["expression_implementation"]} if "expression_implementation" in e else {})
        for e in gt["entities"]
    ]
    objs = [{"id": o["objective_id"], "meaning": o["meaning"], "direction": o["direction"]} for o in gt["objectives"]]
    return json.dumps({"reference_objectives": objs, "reference_entities": ents}, indent=1, ensure_ascii=False)


def _extraction_view(run: dict) -> str:
    view = [
        {
            "objective_id": o["objective_id"],
            "objective_name": o["objective_name"],
            "direction": o["direction"],
            "dependencies": [{k: d[k] for k in ("name", "symbol", "type", "relationship") if k in d} for d in o["dependencies"]],
        }
        for o in run["extraction"]["objectives"]
    ]
    return json.dumps(view, indent=1, ensure_ascii=False)


def load_ground_truth(problem_id: str) -> dict:
    return json.loads((GROUND_TRUTH / f"{problem_id.lower()}_ground_truth.json").read_text())


def load_overrides() -> list[dict]:
    return json.loads(OVERRIDES.read_text())["overrides"] if OVERRIDES.exists() else []


def apply_overrides(run: dict, judgment: Judgment, overrides: list[dict]) -> tuple[Judgment, list[str]]:
    """Overrides match on (dependency name, extracted objective name), for one run_id or for all runs ('*')."""
    names = {o["objective_id"]: normalize(o["objective_name"]) for o in run["extraction"]["objectives"]}
    applied = []
    for item in judgment.items:
        for ov in overrides:
            if ov.get("run_id", "*") not in ("*", run["run_id"]):
                continue
            if normalize(ov["dependency_name"]) != normalize(item.dependency_name):
                continue
            if "objective_name" in ov and normalize(ov["objective_name"]) != names.get(item.extracted_objective_id):
                continue
            item.entity_ids = ov["entity_ids"]
            item.category = ov.get("category", "matches_entity" if ov["entity_ids"] else "incorrect")
            item.explanation = f"MANUAL OVERRIDE: {ov.get('note', '')}"
            applied.append(f"{item.extracted_objective_id} / {item.dependency_name}")
    return judgment, applied


def judge_run(run: dict, llm: LLM | None = None, refresh: bool = False) -> dict:
    """Return the (cached) judgment record for a run: {"judge_model", "judgment", "overrides_applied", "warnings"}."""
    JUDGMENTS.mkdir(parents=True, exist_ok=True)
    path = JUDGMENTS / f"{run['run_id']}.json"
    gt = load_ground_truth(run["problem_id"])
    if path.exists() and not refresh:
        rec = json.loads(path.read_text())
        judgment = Judgment.model_validate(rec["raw_judgment"])
    else:
        llm = llm or GeminiLLM(model=JUDGE_MODEL)
        if llm.model == run["model"]:
            raise ValueError(f"Judge model must differ from the evaluated model ({run['model']}). Set JUDGE_MODEL.")
        log(f"judging {run['run_id']} with {llm.model}")
        prompt = f"REFERENCE:\n{_reference_view(gt)}\n\nEXTRACTION TO MAP:\n{_extraction_view(run)}"
        judgment, call = llm.generate("judge", JUDGE_SYSTEM, prompt, Judgment)
        rec = {"run_id": run["run_id"], "judge_model": llm.model, "raw_judgment": judgment.model_dump(), "llm_call": vars(call)}
        path.write_text(json.dumps(rec, indent=2, ensure_ascii=False, default=str))

    judgment, applied = apply_overrides(run, Judgment.model_validate(rec["raw_judgment"]), load_overrides())

    warnings = []
    valid_ids = {e["id"] for e in gt["entities"]}
    for item in judgment.items:
        bad = [e for e in item.entity_ids if e not in valid_ids]
        if bad:
            warnings.append(f"judge used unknown entity ids {bad} for '{item.dependency_name}' (ignored)")
            item.entity_ids = [e for e in item.entity_ids if e in valid_ids]
    return {"judge_model": rec["judge_model"], "judgment": judgment, "overrides_applied": applied, "warnings": warnings}
