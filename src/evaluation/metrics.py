"""Deterministic scoring of one run against the ground truth, given the judge's entity mapping.

Counting rules (see matching_rules in the ground-truth file):
  * Recall    = reference dependencies covered / reference dependencies of the objective (group items credit all
                entities they cover, R3).
  * Precision = true-positive items / (true-positive + false-positive items). An item is a true positive if it
                denotes at least one not-yet-credited required entity of ITS objective (R2). Items whose entities
                were all credited already are duplicates and are excluded (R9).
  * F1        = harmonic mean (undefined if both are 0 or there are no items).
  * Unsupported claim rate = items whose evidence quote could not be found in the description or a retrieved
                passage / all items. Inferred items have no quote and therefore count as unsupported.
  * Missing   = required reference dependencies not covered.
Micro-averaged overall scores pool the counts over all objectives.
"""

import json

from config import DESCRIPTIONS
from extraction.evidence_checks import normalize


def _safe_div(a: float, b: float) -> float | None:
    return a / b if b else None


def _f1(p: float | None, r: float | None) -> float | None:
    if p is None or r is None or (p + r) == 0:
        return None if p is None or r is None else 0.0
    return 2 * p * r / (p + r)


def stated_in_description(problem_id: str, variant: str) -> set[str]:
    """Reference entity ids that the description variant states (from the omission log)."""
    log = json.loads((DESCRIPTIONS / f"{problem_id.lower()}_descriptions.json").read_text())
    return {gid for f in log["facts"] if f[variant].lower().startswith("stated") for gid in f["ground_truth_ids"]}


def score_run(run: dict, judged: dict, gt: dict) -> dict:
    judgment = judged["judgment"]
    ents = {e["id"]: e for e in gt["entities"]}
    gt_objs = {o["objective_id"]: o for o in gt["objectives"]}
    obj_map = {m.extracted_objective_id: m.reference_objective_id for m in judgment.objective_mapping}
    by_item = {(j.extracted_objective_id, normalize(j.dependency_name)): j for j in judgment.items}
    checks = {(c["objective_id"], c["dependency"]): c for c in run["evidence_checks"]}
    stated = stated_in_description(run["problem_id"], run["description_variant"])

    credited: dict[str, set[str]] = {oid: set() for oid in gt_objs}
    items: list[dict] = []
    for o in run["extraction"]["objectives"]:
        ref = obj_map.get(o["objective_id"])
        ref = ref if ref in gt_objs else None
        for d in o["dependencies"]:
            j = by_item.get((o["objective_id"], normalize(d["name"])))
            chk = checks.get((o["objective_id"], d["name"]), {})
            row = {
                "extracted_objective_id": o["objective_id"],
                "reference_objective_id": ref,
                "dependency": d["name"],
                "type": d["type"],
                "evidence_status": d["evidence_status"],
                "evidence_verified": bool(chk.get("supported")),
                "entity_ids": j.entity_ids if j else [],
                "judge_category": j.category if j else "unjudged",
                "judge_explanation": j.explanation if j else "",
                "type_error": False,
                "meaning_error": bool(j and j.meaning_error),
            }
            if j is None:
                row["outcome"], row["reason"] = "false_positive", "not judged"
            elif ref is None:
                row["outcome"], row["reason"] = "false_positive", "objective not in reference"
            else:
                required = set(gt_objs[ref]["required_dependencies"])
                not_deps = {n["id"] for n in gt_objs[ref]["not_dependencies"]}
                hits = [e for e in j.entity_ids if e in required]
                new = [e for e in hits if e not in credited[ref]]
                if new:
                    credited[ref].update(new)
                    row["outcome"], row["reason"] = "true_positive", "matches " + ", ".join(new)
                    row["credited"] = new
                    row["type_error"] = not j.type_correct
                elif hits:
                    row["outcome"], row["reason"] = "duplicate", "already credited: " + ", ".join(hits)
                elif any(e in not_deps for e in j.entity_ids):
                    row["outcome"], row["reason"] = "false_positive", "over-attribution: known non-dependency of this objective"
                elif j.entity_ids:
                    row["outcome"], row["reason"] = "false_positive", "real entity, but not needed for this objective"
                else:
                    row["outcome"] = "false_positive"
                    row["reason"] = {
                        "vague": "too vague to identify a specific quantity",
                        "not_in_implementation": "plausible, but not part of the implementation",
                    }.get(j.category, "denotes no reference entity")
            items.append(row)

    def summarise(oid_filter: set[str] | None) -> dict:
        rows = [r for r in items if oid_filter is None or r["reference_objective_id"] in oid_filter]
        refs = [oid for oid in gt_objs if oid_filter is None or oid in oid_filter]
        tp = sum(r["outcome"] == "true_positive" for r in rows)
        fp = sum(r["outcome"] == "false_positive" for r in rows)  # overall includes items of unmapped objectives
        n_required = sum(len(gt_objs[o]["required_dependencies"]) for o in refs)
        n_covered = sum(len(credited[o]) for o in refs)
        p, r = _safe_div(tp, tp + fp), _safe_div(n_covered, n_required)
        covered_ids = [(o, e) for o in refs for e in credited[o]]
        beyond = [(o, e) for o, e in covered_ids if e not in stated]
        beyond_rows = [r_ for r_ in rows if r_["outcome"] == "true_positive" and any(e not in stated for e in r_.get("credited", []))]
        return {
            "items": len(rows),
            "true_positives": tp,
            "false_positives": fp,
            "duplicates": sum(r_["outcome"] == "duplicate" for r_ in rows),
            "required": n_required,
            "covered": n_covered,
            "missing": n_required - n_covered,
            "missing_ids": [f"{o}:{e}" for o in refs for e in gt_objs[o]["required_dependencies"] if e not in credited[o]],
            "precision": p,
            "recall": r,
            "f1": _f1(p, r),
            "unsupported_items": sum(not r_["evidence_verified"] for r_ in rows),
            "unsupported_rate": _safe_div(sum(not r_["evidence_verified"] for r_ in rows), len(rows)),
            "type_errors": sum(r_["type_error"] for r_ in rows),
            "meaning_errors": sum(r_["meaning_error"] for r_ in rows),
            "over_attributions": sum(r_["reason"].startswith("over-attribution") for r_ in rows),
            "not_in_implementation": sum(r_["reason"].startswith("plausible") for r_ in rows),
            "vague": sum(r_["reason"].startswith("too vague") for r_ in rows),
            # Discovery vs extraction (spec 13.1): covered entities the description did not state
            "covered_from_description": n_covered - len(beyond),
            "covered_beyond_description": len(beyond),
            "beyond_description_with_verified_evidence": sum(r_["evidence_verified"] for r_ in beyond_rows),
        }

    unmapped = [r for r in items if r["reference_objective_id"] is None]
    overall = summarise(None)
    return {
        "run_id": run["run_id"],
        "method": run["method"],
        "model": run["model"],
        "problem_id": run["problem_id"],
        "description_variant": run["description_variant"],
        "corpus": run["corpus"],
        "judge_model": judged["judge_model"],
        "overrides_applied": judged["overrides_applied"],
        "warnings": judged["warnings"] + ([f"{len(unmapped)} items belong to objectives not mapped to the reference"] if unmapped else []),
        "objective_mapping": {m.extracted_objective_id: m.reference_objective_id for m in judgment.objective_mapping},
        "per_objective": {oid: summarise({oid}) for oid in gt_objs},
        "overall": overall,
        "items": items,
    }
