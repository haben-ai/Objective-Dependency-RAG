"""Judge + score saved runs and write results/scores/<run_id>.json.

    PYTHONPATH=src python -m evaluation.comparison              # all saved runs (judgments are cached)
    PYTHONPATH=src python -m evaluation.comparison --refresh    # re-ask the judge
"""

import argparse
import json

from config import RESULTS
from evaluation.judge import judge_run, load_ground_truth
from evaluation.metrics import score_run
from extraction.llm_client import log

SCORES = RESULTS / "scores"


def load_saved_runs() -> list[dict]:
    return [
        json.loads(f.read_text())
        for f in sorted((RESULTS / "runs").glob("*.json"))
        if not f.name.startswith("superseded_")
    ]


def load_score(run_id: str) -> dict | None:
    f = SCORES / f"{run_id}.json"
    return json.loads(f.read_text()) if f.exists() else None


def score_and_save(run: dict, refresh: bool = False) -> dict:
    judged = judge_run(run, refresh=refresh)
    score = score_run(run, judged, load_ground_truth(run["problem_id"]))
    SCORES.mkdir(parents=True, exist_ok=True)
    (SCORES / f"{run['run_id']}.json").write_text(json.dumps(score, indent=2, ensure_ascii=False, default=str))
    return score


def fmt(x: float | None) -> str:
    return "n/a" if x is None else f"{x:.2f}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()
    for run in load_saved_runs():
        try:
            s = score_and_save(run, refresh=args.refresh)
        except Exception as e:  # keep scoring the others
            log(f"FAILED {run['run_id']}: {e}")
            continue
        o = s["overall"]
        print(
            f"{s['method']:10s} {s['description_variant']:10s} {str(s['corpus']):18s} "
            f"P={fmt(o['precision'])} R={fmt(o['recall'])} F1={fmt(o['f1'])} "
            f"unsupported={fmt(o['unsupported_rate'])} missing={o['missing']}  [{s['run_id']}]"
        )


if __name__ == "__main__":
    main()
