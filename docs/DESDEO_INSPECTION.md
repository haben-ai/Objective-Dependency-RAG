# DESDEO Inspection Report (Phase 1)

Date: 2026-11-09
Scope: what the installed DESDEO actually contains for RE21 and the UTOPIA / forest problems,
and what this means for ground truth and for the RAG corpus.

---

## 1. Repository and environment

| Item | Finding |
|---|---|
| Repository | `THESIS-2026-Bekir-Afsar/` was **empty** (no code, not a git repo). Everything here is new. |
| System Python | Homebrew Python **3.14.7** only. |
| DESDEO requirement | DESDEO 2.8.0 declares `requires-python = ">=3.12,<3.14"`, so it **cannot be installed on 3.14**. |
| Environment created | `.venv/` with **Python 3.13** (managed by `uv`, installed via Homebrew). |
| DESDEO installed | **desdeo 2.8.0** from GitHub, pinned to commit `64ed671ef65a43e068357af0dec36d1f139faceb` (2026-11-05). |
| Runtime warning | DESDEO warns that `bonmin`, `cbc`, `ipopt` solvers are missing. **Irrelevant for this project**: we only evaluate objectives, we never optimize. |

### 1.1 Version discrepancy you should know about

- PyPI's `desdeo` package is **1.1.1**: that is **DESDEO 1** (the older `desdeo-problem` / `desdeo-mcdm` API). It has neither `re21` in this form nor the `Problem` schema used below.
- The documentation at <https://desdeo.readthedocs.io/en/latest/> describes **DESDEO 2**, which is only on GitHub.
- Conclusion: `pip install desdeo` would give the wrong framework. This project pins the GitHub commit (see `requirements.txt`).

Reproduce:

```bash
uv venv --python 3.13 .venv
uv pip install --python .venv -r requirements.txt
```

---

## 2. RE21: Four-bar truss

### 2.1 Location

| What | Where (in the installed package) |
|---|---|
| Definition | `desdeo/problem/testproblems/re_problem.py`, function `re21(f=10.0, sigma=10.0, e=2.0*1e5, l=200.0)` (line 24) |
| Export | `from desdeo.problem.testproblems import re21` |
| Unit test | `tests/test_testproblems.py::test_re21` (GitHub repo only, not in the wheel): at `x_i = 2` expects `f = (2048.528137, 0.02)` |
| Documentation | `docs/howtoguides/re_problems.ipynb` (solves RE problems with NSGA-III, cites Cheng & Li 1999 and Tanabe & Ishibuchi 2020) |

### 2.2 How DESDEO represents it

`re21()` returns a pydantic `desdeo.problem.schema.Problem`:

- `variables`: four `Variable` objects `x_1 … x_4`, type `real`, with bounds.
- `objectives`: two `Objective` objects `f_1`, `f_2`, `objective_type=analytical`, both **minimized** (`maximize=False`).
- `constants`, `constraints`, `extra_funcs`: **all `None`**.
- Objective expressions are written as infix strings and stored as parsed MathJSON-style lists.
  Evaluation goes through `desdeo.problem.PolarsEvaluator`.

**Important for the research:** the physical parameters `F, E, L, σ` are **not** objects in the `Problem`.
They are Python arguments that get **inlined as numbers** when the expression string is built:

```text
f_1.func = ['Multiply', 200.0, ['Add', ['Multiply', 2, 'x_1'], ['Multiply', 1.414…, 'x_2'], ['Sqrt', 'x_3'], 'x_4']]
f_2.func = ['Multiply', 0.01, ['Add', ['Divide', 2.0, 'x_1'], ['Divide', 2.828…, 'x_2'],
                              ['Negate', ['Divide', 2.828…, 'x_3']], ['Divide', 2.0, 'x_4']]]
```

So the serialized problem (JSON) shows `200.0` (= L) and `0.01` (= F·L/E), but not the names F, L, E.
Those names are visible **only** in the source code (signature and docstring).
This affects what the RAG corpus can expose (see §4).

### 2.3 Mathematical definition (from docstring, confirmed by execution)

```text
min f1(x) = L · (2·x1 + √2·x2 + √x3 + x4)
min f2(x) = (F·L / E) · (2/x1 + 2√2/x2 − 2√2/x3 + 2/x4)

x1, x4 ∈ [a, 3a],   x2, x3 ∈ [√2·a, 3a],   a = F/σ
F = 10 kN,  E = 2e5 kN/cm²,  L = 200 cm,  σ = 10 kN/cm²
```

### 2.4 Verification by execution (not just reading)

Done in `tests/test_ground_truth.py`. Results:

1. `PolarsEvaluator` output equals an independent NumPy recomputation of the formulas above.
2. **Which inputs actually affect each objective.** I perturbed each variable and each `re21()` argument:

| Changed input | Δ f1 | Δ f2 | Δ bounds |
|---|---|---|---|
| x1, x2, x3, x4 | ≠ 0 | ≠ 0 | – |
| F (force) | **0** | ≠ 0 | yes |
| E (elastic modulus) | **0** | ≠ 0 | no |
| L (length) | ≠ 0 | ≠ 0 | no |
| σ (stress) | **0** | **0** | yes |

Resulting dependency sets:

- **f1 (volume):** x1, x2, x3, x4, L.
- **f2 (displacement):** x1, x2, x3, x4, F, E, L.
- **σ** is **not** a dependency of either objective. It only enters the variable bounds through `a = F/σ`.
  This is a useful test of over-attribution: an LLM that says "stress affects displacement" is plausible-sounding but wrong for this implementation.

### 2.5 Discrepancies and caveats found in the source

| # | Issue | Consequence |
|---|---|---|
| C1 | f1 contains **`√x3`**, not `√2·x3` (which is what a physically consistent volume would use). DESDEO cites Tanabe's `reproblem.py` as the reference implementation, so this appears to be inherited from that implementation rather than a DESDEO-only bug. I have **not** checked the Cheng & Li (1999) paper text. | Ground truth follows the **implementation**: x3 enters f1 through a square root. An LLM that reasons from physics would write `√2·x3`. That counts as a correct *dependency* but a different *relationship*. |
| C2 | The docstring says `e` is "Young modulus?", with a question mark, and `sigma` is described only as "Stress". | Semantic labels come partly from the literature, not from authoritative DESDEO text. The ground truth records provenance for each label. |
| C3 | DESDEO names the objectives only `f_1` and `f_2`. "Structural volume" and "joint displacement" **do not appear** in DESDEO's RE21 source or docstring. "Cross-sectional area" does not appear either. | These meanings come from Tanabe & Ishibuchi (2020) and Cheng & Li (1999), which the docstring cites. A RAG query such as "joint displacement objective" will not semantically match the DESDEO source well. The corpus needs a short literature-derived description, labelled as such. |
| C4 | The problem has no `constants`, so DESDEO's own structures cannot answer "which parameters does f2 use?". | Ground truth for parameters is established from the source code signature, the docstring, and the perturbation test. |

---

## 3. UTOPIA / forest management

### 3.1 There are several implementations

| Implementation | File | Data | Runs out of the box? |
|---|---|---|---|
| `utopia_problem()` (used by the UTOPIA web app) | `desdeo/utopia_stuff/utopia_problem.py` | External CSVs at user-supplied paths (`C:/MyTemp/...` in `utopia_db_init.py`) | **No**. The CSVs are not shipped, and it calls `payoff_table_method` with **Gurobi**, which needs a license. |
| `forest_problem()` (test problem) | `desdeo/problem/testproblems/forest_problem.py` | `tests/data/alternatives_290124.csv` + `alternatives_key_290124.csv` (948 rows, **GitHub repo only, not in the wheel**) | Yes, if the CSVs are copied from the repo. |
| `forest_problem_discrete()` | same file | `datasets/forest_holding_4.csv`, objective vectors only | Yes, but there are no real decision variables (index only). |
| `forest_problem_income_carbon_habitat()` | same file | `datasets/forest_income_carbon_habitat.csv` | Yes, but it is an index-only problem. The docstring states the data was "simulated with SIMO over a one hundred year horizon". |

### 3.2 Structure (forest_problem / utopia_problem)

- Decision variables: binary vectors `X_j` for each stand (unit) `j`. Each element is one management schedule. Constraint: `Sum(X_j) = 1`.
- Coefficients: `TensorConstant`s `V_j`, `W_j`, `P_j`, read **from a CSV of precomputed simulation outputs**. The columns are `npv_{1..5}_percent`, `stock_2025/2030/2035`, `harvest_value_period_2025/2030/2035`, keyed by `holding, unit, schedule`. A second CSV maps schedules to treatments (`donothing`, ...).
- Objectives (all maximized, `analytical`, linear): `f1 = Σ V_j·X_j` (NPV), `f2 = Σ W_j·X_j` (stock), `f3 = Σ P_j·X_j` (harvest value).
- **The forest simulator is not part of DESDEO and is not executed.** Its outputs appear only as data. This fits the thesis framing: the simulation is a dependency, but in DESDEO it is only reachable through its output table.

### 3.3 Discrepancies that matter for the research

| # | Finding |
|---|---|
| U1 | **The docstring disagrees with the code in `utopia_problem.py`.** The docstring says `f1 = Σ v_ij x_ij`. The code builds `f1 = V_end + f3`, where `f3` is the discounted harvest income from periods 5/10/20, with discount factors `(0.97)^2, ^7, ^17`. So in the implementation, NPV **depends on the harvest values**, but the documentation says it does not. This is a concrete case where retrieving documentation would give a wrong dependency. It is a good illustration for the thesis. |
| U2 | The two implementations use different CSV columns (`npv_3_percent`, `stock_20`, `harvest_value_5/10/20` versus `npv_5_percent`, `stock_2035`, `harvest_value_period_2025/30/35`). The column names in `utopia_problem.py` do **not** exist in the shipped test CSV, so it is written for a different data export. |
| U3 | `forest_problem()` sums harvest values without discounting. Its comment says "The harvest values are not going to be discounted like this". |

**Recommendation:** treat UTOPIA as the Phase 9 extension using `forest_problem()` with the shipped CSVs, which is the only variant that is reproducible here. Present U1 to the advisor as motivation for the "verify retrieved evidence" step.

---

## 4. What can be indexed for RAG (RE21)

| Source | Content | Exposes | Leakage risk |
|---|---|---|---|
| `re_problem.py::re21` docstring | Formulas, bounds, parameter values, references | Everything: the full formulation | **High**. Effectively the answer. |
| `re_problem.py::re21` code | Variable bounds, expression strings | Variables, inlined constants, parameter names (signature) | High |
| Serialized `Problem` JSON | Variables, bounds, expressions with numbers inlined | Variables and structure, but **not** parameter names | Medium |
| `docs/howtoguides/re_problems.ipynb` | Provenance table, solving with NSGA-III | Problem name, citation | Low |
| DESDEO docs on the `Problem` schema and evaluators | How objectives and variables are represented | General context only | None |
| Literature summary (Tanabe & Ishibuchi 2020, Cheng & Li 1999) | Physical meaning of variables and objectives | Semantics, not equations | Low |

The spec allows the DESDEO implementation in the RAG corpus. Because the RE21 docstring *is* the complete formulation, the corpus design must be explicit about this. Proposal:

- Chunk the source at sub-function granularity (docstring formula block, parameter block, variables block, each objective block) with metadata, so that retrieval returns passages rather than the whole function.
- Run two corpus configurations: **(a) source-included** and **(b) documentation-only** (no RE21 source code). Report both. This shows how much of the "RAG gain" comes from retrieving the answer itself.
- The ground-truth JSON is **never** indexed.

---

## 5. Technical uncertainties and blockers

1. **LLM provider (blocker for Phase 6).** No API key or local model exists in this environment yet. I need to know which provider and model to use (environment variable only).
2. **Embedding model.** I propose local `sentence-transformers` (e.g. `all-MiniLM-L6-v2` or `bge-small`) so that retrieval is free and reproducible. The first run downloads the model.
3. **Physical semantics of RE21 (C1, C3)** come from the literature cited by DESDEO, not from DESDEO itself. I have not read the original papers in this session. Labels are marked with their provenance in the ground truth.
4. **Matching extracted to reference dependencies** needs a defined procedure: alias rules plus manual check, or a separate judge model that is never the evaluated model. The rules are written down in the ground-truth file. The matcher is Phase 7.

---

## 6. Proposed implementation sequence

1. ✅ Phase 1: inspection (this file).
2. ✅ Phase 2: `data/ground_truth/re21_ground_truth.json` plus `tests/test_ground_truth.py`, which checks it against DESDEO by execution.
3. Phase 3: complete and incomplete RE21 descriptions, with an omission log.
4. Phase 4–5: chunk the corpus (two configurations, §4), local embeddings, ChromaDB, retrieval filtered by `problem_id` / `objective_id`, and a manual retrieval check.
5. Phase 6: the three extractors with a shared JSON schema (pydantic validation) and the same model and prompt core.
6. Phase 7: matcher, metrics, and result files saved to `results/`.
7. Phase 8: Streamlit UI.
8. Phase 9: forest extension (`forest_problem()`), using the U1 discrepancy as a showcase.
