"""Verify the RE21 ground truth against the installed DESDEO implementation by execution.

For every objective:
  * each listed decision-variable / parameter dependency must change the objective when perturbed;
  * each listed non-dependency must leave the objective unchanged;
  * no unlisted variable or parameter may affect the objective.
"""

import json
import warnings
from pathlib import Path

import numpy as np
import pytest

warnings.filterwarnings("ignore", category=UserWarning)  # DESDEO warns about missing optimizers

from desdeo.problem import PolarsEvaluator  # noqa: E402
from desdeo.problem.testproblems import re21  # noqa: E402

GT_PATH = Path(__file__).resolve().parents[1] / "data" / "ground_truth" / "re21_ground_truth.json"
GT = json.loads(GT_PATH.read_text())
ENTITIES = {e["id"]: e for e in GT["entities"]}
DEFAULTS = {"f": 10.0, "sigma": 10.0, "e": 2.0e5, "l": 200.0}
X0 = np.array([1.3, 2.1, 1.8, 2.7])  # interior point, all bounds satisfied


def evaluate(x: np.ndarray, **params: float) -> dict[str, float]:
    problem = re21(**{**DEFAULTS, **params})
    res = PolarsEvaluator(problem).evaluate({f"x_{i + 1}": [float(x[i])] for i in range(4)})
    return {"f1": res["f_1"][0], "f2": res["f_2"][0]}


def affects(entity_id: str, obj: str) -> bool:
    base = evaluate(X0)[obj]
    ent = ENTITIES[entity_id]
    if ent["type"] == "decision_variable":
        x = X0.copy()
        x[int(entity_id[1]) - 1] += 0.1
        new = evaluate(x)[obj]
    else:
        arg = ent["desdeo_argument"]
        new = evaluate(X0, **{arg: DEFAULTS[arg] * 1.5})[obj]
    return not np.isclose(new, base, rtol=1e-12, atol=0)


INPUT_IDS = [i for i, e in ENTITIES.items() if e["type"] in ("decision_variable", "parameter")]


@pytest.mark.parametrize("obj", GT["objectives"], ids=lambda o: o["objective_id"])
def test_dependency_sets_match_execution(obj):
    oid = obj["objective_id"]
    required = {d for d in obj["required_dependencies"] if d in INPUT_IDS}
    actual = {i for i in INPUT_IDS if affects(i, oid)}
    assert actual == required, f"{oid}: execution says {sorted(actual)}, ground truth says {sorted(required)}"
    for nd in obj["not_dependencies"]:
        assert not affects(nd["id"], oid)


def test_formulas_match_desdeo():
    F, E, L = DEFAULTS["f"], DEFAULTS["e"], DEFAULTS["l"]
    x = X0
    f1 = L * (2 * x[0] + np.sqrt(2) * x[1] + np.sqrt(x[2]) + x[3])
    f2 = F * L / E * (2 / x[0] + 2 * np.sqrt(2) / x[1] - 2 * np.sqrt(2) / x[2] + 2 / x[3])
    got = evaluate(X0)
    assert np.isclose(got["f1"], f1) and np.isclose(got["f2"], f2)
    # DESDEO's own unit-test reference point
    ref = evaluate(np.full(4, 2.0))
    assert np.allclose([ref["f1"], ref["f2"]], [2048.528137, 0.02])


def test_problem_structure():
    p = re21()
    assert [v.symbol for v in p.variables] == ["x_1", "x_2", "x_3", "x_4"]
    assert [o.symbol for o in p.objectives] == ["f_1", "f_2"]
    assert all(o.maximize is False for o in p.objectives)
    assert p.constants is None and p.constraints is None
    a = DEFAULTS["f"] / DEFAULTS["sigma"]
    expected = {"x_1": (a, 3 * a), "x_2": (np.sqrt(2) * a, 3 * a), "x_3": (np.sqrt(2) * a, 3 * a), "x_4": (a, 3 * a)}
    for v in p.variables:
        assert np.allclose((v.lowerbound, v.upperbound), expected[v.symbol])


def test_bounds_depend_on_sigma_and_force_only():
    def bounds(**kw):
        return [(v.lowerbound, v.upperbound) for v in re21(**{**DEFAULTS, **kw}).variables]

    base = bounds()
    assert bounds(sigma=15.0) != base
    assert bounds(f=15.0) != base
    assert bounds(e=3e5) == base
    assert bounds(l=300.0) == base


def test_ground_truth_references_are_consistent():
    for obj in GT["objectives"]:
        for d in obj["required_dependencies"] + [n["id"] for n in obj["not_dependencies"]]:
            assert d in ENTITIES, d
        assert set(obj["required_dependencies"]).isdisjoint(n["id"] for n in obj["not_dependencies"])
