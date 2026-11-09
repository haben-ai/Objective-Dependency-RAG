"""Copy the raw RAG source documents into data/documents/ and record their provenance.

Usage:
    python scripts/collect_sources.py --desdeo-repo PATH --reproblems-repo PATH

Only extracts the parts that are relevant (RE problem sources, RE documentation, DESDEO problem-format
explanation, Tanabe & Ishibuchi supplementary sections S.1.1-S.1.4). The ground-truth file is never copied.
"""

import argparse
import json
import subprocess
from pathlib import Path

import pypdf

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "documents"


def git_commit(repo: Path) -> str:
    return subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()


def notebook_markdown(path: Path) -> str:
    nb = json.loads(path.read_text())
    return "\n\n".join("".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "markdown")


def tanabe_sections(pdf: Path) -> str:
    text = "\n".join(p.extract_text() for p in pypdf.PdfReader(pdf).pages)
    start = text.index("S.1.1. RE2-4-1")
    end = text.index("S.1.5.")
    body = text[start:end]
    # drop the title-page footer that pypdf interleaves into section S.1.1
    for junk in ("∗Corresponding author", "Email addresses:", "(Hisao Ishibuchi)", "Preprint submitted to"):
        body = "\n".join(line for line in body.splitlines() if junk not in line)
    return body


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--desdeo-repo", type=Path, required=True)
    ap.add_argument("--reproblems-repo", type=Path, required=True)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    d, t = args.desdeo_repo, args.reproblems_repo

    docs = [
        {
            "file": "desdeo_re_problem.py",
            "content": (d / "desdeo/problem/testproblems/re_problem.py").read_text(),
            "origin": "DESDEO desdeo/problem/testproblems/re_problem.py",
            "repo": "https://github.com/industrial-optimization-group/DESDEO",
            "commit": git_commit(d),
            "document_type": "source_code",
        },
        {
            "file": "desdeo_howto_re_problems.md",
            "content": notebook_markdown(d / "docs/howtoguides/re_problems.ipynb"),
            "origin": "DESDEO docs/howtoguides/re_problems.ipynb (markdown cells only)",
            "repo": "https://github.com/industrial-optimization-group/DESDEO",
            "commit": git_commit(d),
            "document_type": "documentation",
        },
        {
            "file": "desdeo_explanation_problem_format.md",
            "content": notebook_markdown(d / "docs/explanation/problem_format.ipynb"),
            "origin": "DESDEO docs/explanation/problem_format.ipynb (markdown cells only)",
            "repo": "https://github.com/industrial-optimization-group/DESDEO",
            "commit": git_commit(d),
            "document_type": "documentation",
        },
        {
            "file": "tanabe_ishibuchi_supplementary_S1.txt",
            "content": tanabe_sections(t / "doc/re-supplementary_file.pdf"),
            "origin": "Tanabe & Ishibuchi, supplementary file to 'An easy-to-use real-world multi-objective "
            "optimization problem suite' (Applied Soft Computing 89, 2020), sections S.1.1-S.1.4, text extracted with pypdf",
            "repo": "https://github.com/ryojitanabe/reproblems (doc/re-supplementary_file.pdf)",
            "commit": git_commit(t),
            "document_type": "literature",
        },
    ]
    manifest = []
    for doc in docs:
        (OUT / doc["file"]).write_text(doc.pop("content"))
        manifest.append(doc)
    (OUT / "SOURCES.json").write_text(json.dumps(manifest, indent=2))
    print(f"wrote {len(manifest)} documents to {OUT}")


if __name__ == "__main__":
    main()
