"""Run the extraction approaches from the command line and save each run to results/runs/.

    PYTHONPATH=src python -m extraction.run --variant incomplete --methods direct rag rag_verify --corpus full
"""

import argparse
import json
from collections.abc import Callable

from config import DESCRIPTIONS, RESULTS
from extraction.extractors import run_direct, run_rag, run_rag_verify
from extraction.llm_client import LLM, default_llm, log


def load_description(problem_id: str, variant: str) -> str:
    return (DESCRIPTIONS / f"{problem_id.lower()}_{variant}.txt").read_text()


def save_run(rec: dict) -> str:
    out = RESULTS / "runs"
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{rec['run_id']}.json"
    path.write_text(json.dumps(rec, indent=2, ensure_ascii=False, default=str))
    return str(path)


def run_methods(
    llm: LLM,
    problem_id: str,
    variant: str,
    methods: list[str],
    corpus: str,
    description: str | None = None,
    on_done: Callable[[str, dict], None] | None = None,
) -> dict[str, dict]:
    """Run the requested methods. `on_done(method, record)` is called as soon as each one finishes."""
    description = description or load_description(problem_id, variant)
    runs: dict[str, dict] = {}

    def done(method: str, rec: dict) -> None:
        runs[method] = rec
        if on_done and method in methods:
            on_done(method, rec)

    if "direct" in methods:
        log("== A. direct")
        done("direct", run_direct(llm, problem_id, variant, description))
    if "rag" in methods or "rag_verify" in methods:
        log("== B. rag")
        done("rag", run_rag(llm, problem_id, variant, description, corpus))
    if "rag_verify" in methods:
        log("== C. rag_verify")
        done("rag_verify", run_rag_verify(llm, problem_id, variant, description, corpus, rag_run=runs["rag"]))
    return {m: r for m, r in runs.items() if m in methods}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--problem", default="RE21")
    ap.add_argument("--variant", default="incomplete", choices=["complete", "incomplete"])
    ap.add_argument("--methods", nargs="+", default=["direct", "rag", "rag_verify"])
    ap.add_argument("--corpus", default="full", choices=["full", "no_source_code", "documentation_only"])
    ap.add_argument("--model", default=None, help="Gemini model id (default: GEMINI_MODEL or src/config.py)")
    ap.add_argument("--verify-rag-run", default=None, help="Path to a saved rag run: only run C (verification) on it")
    args = ap.parse_args()

    def report(method: str, rec: dict) -> None:
        n = sum(len(o["dependencies"]) for o in rec["extraction"]["objectives"])
        print(f"{method:11s} {n:3d} dependencies -> {save_run(rec)}", flush=True)

    if args.verify_rag_run:
        rag = json.loads(open(args.verify_rag_run).read())
        assert rag["method"] == "rag", "--verify-rag-run needs a run of method 'rag'"
        llm = default_llm(args.model or rag["model"])
        log(f"== C. rag_verify on {rag['run_id']}")
        rec = run_rag_verify(llm, rag["problem_id"], rag["description_variant"], rag["description"], rag["corpus"], rag_run=rag)
        report("rag_verify", rec)
        return

    llm = default_llm(args.model)
    run_methods(llm, args.problem, args.variant, args.methods, args.corpus, on_done=report)


if __name__ == "__main__":
    main()
