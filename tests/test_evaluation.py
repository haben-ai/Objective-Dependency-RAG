"""Scoring tests with hand-written judgments (no API calls). Expected values are computed by hand."""

import pytest

from evaluation.judge import Judgment, apply_overrides, load_ground_truth
from evaluation.metrics import score_run, stated_in_description

GT = load_ground_truth("RE21")


def dep(name, type_="parameter", status="inferred"):
    return {"name": name, "type": type_, "relationship": "", "evidence_status": status, "evidence": None, "source_chunk_id": None}


def make_run(o1, o2, verified=()):
    objs = [
        {"objective_id": "o1", "objective_name": "volume", "direction": "minimize", "dependencies": o1},
        {"objective_id": "o2", "objective_name": "displacement", "direction": "minimize", "dependencies": o2},
    ]
    checks = [
        {"objective_id": o["objective_id"], "dependency": d["name"], "supported": (o["objective_id"], d["name"]) in verified}
        for o in objs
        for d in o["dependencies"]
    ]
    return {
        "run_id": "test", "method": "direct", "model": "m", "problem_id": "RE21", "description_variant": "incomplete",
        "corpus": None, "extraction": {"objectives": objs, "open_questions": []}, "evidence_checks": checks,
    }


def judged(items, mapping=(("o1", "f1"), ("o2", "f2"))):
    j = Judgment.model_validate({
        "objective_mapping": [{"extracted_objective_id": a, "reference_objective_id": b} for a, b in mapping],
        "items": [
            {"extracted_objective_id": o, "dependency_name": n, "entity_ids": ids, "category": cat,
             "type_correct": tc, "meaning_error": False, "explanation": ""}
            for o, n, ids, cat, tc in items
        ],
    })
    return {"judge_model": "judge", "judgment": j, "overrides_applied": [], "warnings": []}


def test_stated_entities_from_omission_log():
    assert stated_in_description("RE21", "incomplete") == {"x1", "x2", "x3", "x4", "f1", "f2"}
    assert {"L", "F", "E", "sigma"} <= stated_in_description("RE21", "complete")


def test_perfect_extraction():
    run = make_run(
        [dep("areas", "decision_variable"), dep("L"), dep("volume formula", "mathematical_expression")],
        [dep("areas", "decision_variable"), dep("F"), dep("E"), dep("L"), dep("disp formula", "mathematical_expression")],
    )
    areas = ["x1", "x2", "x3", "x4"]
    s = score_run(run, judged([
        ("o1", "areas", areas, "matches_entity", True), ("o1", "L", ["L"], "matches_entity", True),
        ("o1", "volume formula", ["expr_volume"], "matches_entity", True),
        ("o2", "areas", areas, "matches_entity", True), ("o2", "F", ["F"], "matches_entity", True),
        ("o2", "E", ["E"], "matches_entity", True), ("o2", "L", ["L"], "matches_entity", True),
        ("o2", "disp formula", ["expr_displacement"], "matches_entity", True),
    ]), GT)
    o = s["overall"]
    assert (o["precision"], o["recall"], o["f1"], o["missing"]) == (1.0, 1.0, 1.0, 0)
    assert o["required"] == 14 and o["covered"] == 14
    assert o["unsupported_rate"] == 1.0  # nothing verified in this synthetic run
    # incomplete description states only x1..x4: L, F, E and both expressions are "beyond description"
    assert o["covered_beyond_description"] == 6 and o["covered_from_description"] == 8


def test_counting_rules():
    run = make_run(
        [
            dep("areas", "decision_variable"),        # TP, credits x1-x4
            dep("area of bar 1", "decision_variable"),  # duplicate (x1 already credited)
            dep("force F"),                           # F is a known non-dependency of f1 -> over-attribution
            dep("material properties"),               # vague
            dep("length", "decision_variable"),       # TP with type error
        ],
        [
            dep("stress sigma"),                      # over-attribution for f2
            dep("FEM model", "simulation"),           # not in implementation
            dep("E"),                                 # TP
        ],
        verified={("o1", "areas")},
    )
    s = score_run(run, judged([
        ("o1", "areas", ["x1", "x2", "x3", "x4"], "matches_entity", True),
        ("o1", "area of bar 1", ["x1"], "matches_entity", True),
        ("o1", "force F", ["F"], "matches_entity", True),
        ("o1", "material properties", [], "vague", True),
        ("o1", "length", ["L"], "matches_entity", False),
        ("o2", "stress sigma", ["sigma"], "matches_entity", True),
        ("o2", "FEM model", [], "not_in_implementation", True),
        ("o2", "E", ["E"], "matches_entity", True),
    ]), GT)
    f1, f2, o = s["per_objective"]["f1"], s["per_objective"]["f2"], s["overall"]
    # f1: TP = areas, length; FP = force, material; duplicate = area of bar 1. Covered 5 of 6 (expr missing).
    assert (f1["true_positives"], f1["false_positives"], f1["duplicates"]) == (2, 2, 1)
    assert f1["precision"] == pytest.approx(0.5) and f1["recall"] == pytest.approx(5 / 6)
    assert f1["missing_ids"] == ["f1:expr_volume"]
    assert f1["type_errors"] == 1 and f1["over_attributions"] == 1 and f1["vague"] == 1
    # f2: TP = E; FP = sigma, FEM. Covered 1 of 8.
    assert (f2["true_positives"], f2["false_positives"]) == (1, 2)
    assert f2["recall"] == pytest.approx(1 / 8) and f2["not_in_implementation"] == 1 and f2["over_attributions"] == 1
    # overall micro: TP 3, FP 4 -> P = 3/7; covered 6 of 14
    assert o["precision"] == pytest.approx(3 / 7) and o["recall"] == pytest.approx(6 / 14)
    assert o["f1"] == pytest.approx(2 * (3 / 7) * (6 / 14) / (3 / 7 + 6 / 14))
    assert o["unsupported_items"] == 7 and o["unsupported_rate"] == pytest.approx(7 / 8)


def test_wrong_objective_and_unmapped_objective():
    run = make_run([dep("E")], [dep("x")])
    s = score_run(run, judged(
        [("o1", "E", ["E"], "matches_entity", True), ("o2", "x", ["x1"], "matches_entity", True)],
        mapping=(("o1", "f1"), ("o2", None)),
    ), GT)
    rows = {r["dependency"]: r for r in s["items"]}
    assert rows["E"]["reason"].startswith("over-attribution")  # E is listed as a non-dependency of f1
    assert rows["x"]["reason"] == "objective not in reference"
    assert s["per_objective"]["f2"]["recall"] == 0.0 and s["overall"]["false_positives"] == 2
    assert s["warnings"]


def test_empty_extraction_metrics_undefined_not_zero():
    s = score_run(make_run([], []), judged([]), GT)
    assert s["overall"]["precision"] is None and s["overall"]["f1"] is None and s["overall"]["recall"] == 0.0


def test_overrides_take_precedence():
    run = make_run([dep("Truss geometry")], [])
    j = judged([("o1", "Truss geometry", [], "vague", True)])["judgment"]
    j, applied = apply_overrides(run, j, [{"dependency_name": "truss  geometry", "entity_ids": ["L"], "note": "test"}])
    assert j.items[0].entity_ids == ["L"] and j.items[0].category == "matches_entity" and applied
