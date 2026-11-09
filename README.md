# RAG-assisted identification of objective-function dependencies (DESDEO prototype)

Research prototype for the thesis *LLM-Assisted Identification of Objective Function Dependencies in
Multiobjective Optimization*. It compares three ways of identifying what each objective needs in order to
be evaluated (decision variables, parameters, expressions, models, data):

| Approach | Sees |
|---|---|
| A. Direct LLM | the natural-language description only |
| B. RAG | description + passages retrieved from a DESDEO / literature corpus |
| C. RAG + verification | B's output, reviewed against the same evidence; quotes are checked mechanically, contradicted items are removed |

First benchmark: **RE21 four-bar truss** (DESDEO 2.8.0). The extension is the forest problem.

## Status

| Phase | State |
|---|---|
| 1 Inspection | ✅ [docs/DESDEO_INSPECTION.md](docs/DESDEO_INSPECTION.md) |
| 2 Ground truth | ✅ [data/ground_truth/re21_ground_truth.json](data/ground_truth/re21_ground_truth.json), checked against DESDEO by execution |
| 3 Descriptions | ✅ complete / incomplete variants, plus an omission log [re21_descriptions.json](data/descriptions/re21_descriptions.json) |
| 4 Ingestion | ✅ 129 structure-aware chunks, ChromaDB, local MiniLM embeddings |
| 5 Retrieval | ✅ problem filter, problem-specific passages prioritised, 3 corpus configurations |
| 6 Extractors | ✅ first live run 2026-11-09 with `gemini-3.6-flash` (RE21, incomplete description, full corpus). 3.8/3.7-flash were overloaded (503/504) at the time |
| 7 Evaluation | ✅ judge model maps items to reference entities (cached, manually reviewed: [docs/JUDGE_REVIEW.md](docs/JUDGE_REVIEW.md), overridable); metrics computed deterministically. `python -m evaluation.comparison` |
| 8 UI | ✅ first version: `streamlit run src/ui/app.py` |
| 9 Forest extension | ⏳ |

## Setup

```bash
uv venv --python 3.13 .venv
uv pip install --python .venv -r requirements.txt
cp .env.example .env        # then put your GEMINI_API_KEY in .env
```

## Run

```bash
PYTHONPATH=src .venv/bin/python -m ingestion.indexing          # build the vector index (first run downloads the embedding model)
PYTHONPATH=src .venv/bin/python -m extraction.run --variant incomplete --corpus full
.venv/bin/python -m pytest -q                                  # 26 tests, no API calls
.venv/bin/streamlit run src/ui/app.py                          # demo UI at http://localhost:8501
```

Each run is saved to `results/runs/<run_id>.json`. It contains the description, model, retrieval queries,
passages with scores and reasons, every prompt and raw response, the extraction, the evidence checks, and
(for C) the verification table.

## Design choices relevant to validity

- **Information separation.** The ground truth is never indexed (a test enforces this). The direct baseline never sees passages, and any "retrieved" claim it makes is reset to "inferred".
- **Corpus configurations** (`--corpus`):
  - `full`: DESDEO source, literature and docs.
  - `no_source_code`: literature and docs.
  - `documentation_only`: docs only.

  The RE21 docstring and the Tanabe & Ishibuchi supplementary file both contain the full formulation. Comparing the configurations shows how much of a RAG gain is just "retrieving the answer".
- **Evidence is checked mechanically.** A quote counts only if it is found in the description or in the cited retrieved passage, using fuzzy matching to tolerate PDF-extraction noise. The same check is applied to all three approaches, so unsupported-claim rates are comparable.
- **C builds on B's own run.** C reviews the same extraction B produced, so the B to C difference isolates the effect of verification.
- **Same model, temperature 0, fixed seed, same core prompt** for all approaches. The model is set by `GEMINI_MODEL` (default `gemini-3.8-flash`, the example name in google-genai 3.0's docs; not yet verified against the live API).

## Findings so far (for the advisor meeting)

1. **σ (allowable stress) is not a dependency of either RE21 objective.** It only sets the variable bounds. This is a natural over-attribution test.
2. **DESDEO's RE21 source names neither the objectives nor the variables** (`f_1`, `x_1`, ...). Their meaning comes from the literature.
3. **The literature itself is misleading in one place.** Tanabe & Ishibuchi's supplementary file says the variables "determine the length of four bars", but the units show they are cross-sectional areas. A retrieved, authoritative source can be wrong.
4. **In the UTOPIA forest code, the docstring disagrees with the implementation** about what the NPV objective depends on. This is a strong case for the verification step.

## API quota

On the Gemini free tier, each model allows **20 requests per day**. A full A+B+C run uses 4 requests of the
evaluated model; scoring uses 1 request of the judge model per run. Judgments are cached, so re-scoring is free.
