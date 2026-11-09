"""Streamlit demo: RAG-assisted identification of objective-function dependencies.

    .venv/bin/streamlit run src/ui/app.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # make src/ importable

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from config import DESCRIPTIONS, GROUND_TRUTH, RESULTS  # noqa: E402

st.set_page_config(page_title="Detailed view", layout="wide")

METHODS = {
    "direct": "A · Direct LLM",
    "rag": "B · RAG-assisted",
    "rag_verify": "C · RAG + verification",
}
METHOD_INFO = {
    "direct": "Sees only the natural-language description.",
    "rag": "Description + passages retrieved from the DESDEO / literature corpus.",
    "rag_verify": "B's extraction, reviewed against the same evidence. Quotes are checked mechanically; contradicted items are removed.",
}
STATUS = {  # label, colour, symbol (colour is never the only cue)
    "explicit": ("Explicit", "#1a7f37", "●"),
    "retrieved": ("Retrieved", "#0969da", "◆"),
    "inferred": ("Inferred", "#9a6700", "▲"),
    "unknown": ("Unknown", "#6e7781", "?"),
}
CORPUS_LABELS = {
    "full": "Full (DESDEO source + literature + docs)",
    "no_source_code": "No source code (literature + docs)",
    "documentation_only": "Documentation only",
}
PROBLEMS = {
    "RE21": "RE21 · Four-bar truss design: minimise structural volume and joint displacement by choosing the cross-sectional areas of four bars. Source: DESDEO 2.8.0.",
}


# ----------------------------------------------------------------------------------------- data helpers


def load_runs() -> list[dict]:
    runs = []
    for f in sorted((RESULTS / "runs").glob("*.json")):
        if f.name.startswith("superseded_"):
            continue
        r = json.loads(f.read_text())
        r["_file"] = f.name
        runs.append(r)
    return runs


def latest(runs: list[dict], method: str, problem: str, variant: str, corpus: str | None) -> dict | None:
    match = [
        r
        for r in runs
        if r["method"] == method
        and r["problem_id"] == problem
        and r["description_variant"] == variant
        and (method == "direct" or r["corpus"] == corpus)
    ]
    return max(match, key=lambda r: r["timestamp"]) if match else None


def badge(status: str) -> str:
    label, colour, sym = STATUS.get(status, (status, "#6e7781", "·"))
    return f"<span style='color:{colour};font-weight:600'>{sym} {label}</span>"


def short_source(chunk_id: str | None) -> str:
    if not chunk_id:
        return ""
    file, _, rest = chunk_id.partition("::")
    return f"{file} › {rest}" if rest else file


# ----------------------------------------------------------------------------------------- sidebar

with st.sidebar:
    st.header("Setup")
    problem = st.selectbox("Problem", list(PROBLEMS), help="UTOPIA forest management is planned as an extension.")
    st.caption("UTOPIA forest management: planned (not yet verified)")
    variant = st.radio("Description", ["incomplete", "complete"], format_func=str.capitalize)
    corpus = st.selectbox("Retrieval corpus (B, C)", list(CORPUS_LABELS), format_func=CORPUS_LABELS.get)
    st.divider()
    st.subheader("Run live")
    chosen = st.multiselect("Methods", list(METHODS), default=list(METHODS), format_func=METHODS.get)
    model = st.text_input("Gemini model", value="gemini-3.6-flash")
    run_clicked = st.button("Run with Gemini", type="primary", use_container_width=True)
    st.caption("Without a live run, the page shows the most recent saved run for this setup.")

description_default = (DESCRIPTIONS / f"{problem.lower()}_{variant}.txt").read_text()

# ----------------------------------------------------------------------------------------- header

st.title("Which components does each objective need?")
st.markdown(
    "Identifying **objective-function dependencies** (decision variables, parameters, expressions, models, data) "
    "from a natural-language problem description, with and without retrieval-augmented evidence."
)

# ----------------------------------------------------------------------------------------- 1-2 problem + description

c1, c2 = st.columns([2, 3])
with c1:
    st.subheader("1 · Problem")
    st.info(PROBLEMS[problem])
    st.markdown("**Methods**")
    for m, label in METHODS.items():
        st.markdown(f"- **{label}**: {METHOD_INFO[m]}")
with c2:
    st.subheader(f"2 · Problem description ({variant})")
    description = st.text_area("Given identically to every method", description_default, height=190)
    edited = description.strip() != description_default.strip()
    if edited:
        st.warning("Edited description: a live run will use this text. Saved runs used the original.")
    with st.expander("Presenter notes: what this description leaves out (not shown to the LLM)"):
        log = json.loads((DESCRIPTIONS / f"{problem.lower()}_descriptions.json").read_text())
        st.dataframe(
            pd.DataFrame([{"Fact": f["fact"], "In this description": f[variant]} for f in log["facts"]]),
            hide_index=True,
            use_container_width=True,
        )

# ----------------------------------------------------------------------------------------- live run

if run_clicked:
    from extraction.llm_client import LLMError, default_llm
    from extraction.run import run_methods, save_run

    status = st.status("Running extraction with Gemini…", expanded=True)
    try:
        llm = default_llm(model or None)
        with status:
            def on_done(method, rec):
                save_run(rec)
                st.write(f"✓ {METHODS[method]} finished ({sum(len(o['dependencies']) for o in rec['extraction']['objectives'])} dependencies)")

            st.write("Calls can take 10–60 s each when the model is busy.")
            run_methods(llm, problem, variant, chosen, corpus, description=description, on_done=on_done)
        status.update(label="Run complete", state="complete")
    except LLMError as e:
        status.update(label="Run failed", state="error")
        st.error(str(e))

runs = load_runs()
selected = {m: latest(runs, m, problem, variant, corpus) for m in METHODS}
available = {m: r for m, r in selected.items() if r}

if not available:
    st.warning("No saved runs for this setup yet. Use **Run with Gemini** in the sidebar.")
    st.stop()

with st.expander("Runs shown on this page"):
    st.dataframe(
        pd.DataFrame(
            [
                {"Method": METHODS[m], "Run": r["run_id"], "Model": r["model"], "Corpus": r["corpus"] or "–", "Time (UTC)": r["timestamp"][:19]}
                for m, r in available.items()
            ]
        ),
        hide_index=True,
        use_container_width=True,
    )
    if any(r["description"].strip() != description_default.strip() for r in available.values()):
        st.caption("⚠ At least one run used an edited description.")

tabs = st.tabs(["3 · Dependencies", "4 · Retrieval evidence", "5 · Dependency graph", "6 · Verification", "7 · Ground-truth comparison"])

# ----------------------------------------------------------------------------------------- dependencies

with tabs[0]:
    st.markdown(" ".join(badge(s) + f" <span style='color:#57606a'>{d}</span> &nbsp;" for s, d in [
        ("explicit", "stated in the description"),
        ("retrieved", "found in a retrieved passage"),
        ("inferred", "LLM reasoning, no quote"),
        ("unknown", "needed but not identified"),
    ]), unsafe_allow_html=True)
    cols = st.columns(len(available))
    for col, (m, r) in zip(cols, available.items(), strict=True):
        with col:
            st.markdown(f"#### {METHODS[m]}")
            checks = {(c["objective_id"], c["dependency"]): c for c in r["evidence_checks"]}
            for o in r["extraction"]["objectives"]:
                st.markdown(f"**{o['objective_id']}: {o['direction']} {o['objective_name']}**")
                rows = []
                for d in o["dependencies"]:
                    chk = checks.get((o["objective_id"], d["name"]), {})
                    rows.append(
                        f"<tr><td><b>{d['name']}</b><br><span style='color:#57606a;font-size:0.85em'>{d['relationship']}</span></td>"
                        f"<td>{d['type'].replace('_', ' ')}</td><td>{badge(d['evidence_status'])}"
                        + ("" if chk.get("supported") or d["evidence_status"] in ("inferred", "unknown") else "<br><span style='color:#cf222e;font-size:0.8em'>quote not found</span>")
                        + "</td></tr>"
                    )
                st.markdown(
                    "<table style='width:100%;font-size:0.9em'><tr><th>Dependency</th><th>Type</th><th>Evidence</th></tr>"
                    + "".join(rows)
                    + "</table>",
                    unsafe_allow_html=True,
                )
                with st.expander("Quotes and sources"):
                    for d in o["dependencies"]:
                        if d["evidence"]:
                            st.markdown(f"**{d['name']}**: “{d['evidence']}”  \n<small>{short_source(d['source_chunk_id']) or 'problem description'}</small>", unsafe_allow_html=True)
                        else:
                            st.markdown(f"**{d['name']}**: _no quote ({d['evidence_status']})_")
            if r["extraction"]["open_questions"]:
                st.markdown("**Open questions raised**")
                for q in r["extraction"]["open_questions"]:
                    st.markdown(f"- {q}")

# ----------------------------------------------------------------------------------------- retrieval

with tabs[1]:
    rr = available.get("rag") or available.get("rag_verify")
    if not rr or not rr.get("retrieval"):
        st.info("No retrieval run for this setup. The direct method uses no retrieval.")
    else:
        st.caption(f"Corpus: {CORPUS_LABELS[rr['corpus']]}. Problem-specific passages are ranked first, followed by up to 2 shared documentation passages.")
        st.markdown("**Queries**")
        for q in rr["retrieval"]["queries"]:
            st.markdown(f"- `{q}`")
        cited = {d["source_chunk_id"] for o in rr["extraction"]["objectives"] for d in o["dependencies"] if d["source_chunk_id"]}
        st.markdown("**Retrieved passages**")
        for p in rr["retrieval"]["passages"]:
            m = p["metadata"]
            mark = "  ·  **cited by B**" if p["chunk_id"] in cited else ""
            with st.expander(f"{p['score']:.3f}  ·  {m['problem_id']}  ·  {m['source_file']} › {m['source_section']}{mark}"):
                st.caption(
                    f"type: {m['document_type']} / {m['component_type']} · objective: {m['objective_id']} · location: {m['source_location']}"
                )
                st.caption(f"Why retrieved: {p['why']}")
                st.code(p["content"], language="python" if m["source_file"].endswith(".py") else None, wrap_lines=True)

# ----------------------------------------------------------------------------------------- graph

NODE_STYLE = {
    "decision_variable": ("box", "#ddf4ff"),
    "parameter": ("ellipse", "#fff8c5"),
    "input_data": ("cylinder", "#ffebe9"),
    "mathematical_expression": ("note", "#f6f8fa"),
    "analytical_model": ("component", "#fbefff"),
    "predictive_model": ("component", "#fbefff"),
    "simulation": ("component", "#ffebe9"),
    "intermediate_output": ("diamond", "#f6f8fa"),
    "external_data_source": ("cylinder", "#ffebe9"),
    "unknown": ("plaintext", "#ffffff"),
}
EDGE_COLOUR = {k: v[1] for k, v in STATUS.items()}


def dot_for(run: dict) -> str:
    def q(s: str) -> str:
        return s.replace('"', "'")

    lines = ["digraph G {", "rankdir=LR; node [fontname=Helvetica fontsize=10 style=filled]; edge [fontsize=8 fontname=Helvetica];"]
    seen = set()
    for o in run["extraction"]["objectives"]:
        oid = f"obj_{o['objective_id']}"
        lines.append(f'"{oid}" [label="{q(o["objective_name"])}\\n({o["direction"]})" shape=doubleoctagon fillcolor="#d1d9e0"];')
        for d in o["dependencies"]:
            nid = f"dep_{q(d['name']).lower()}"
            if nid not in seen:
                shape, fill = NODE_STYLE.get(d["type"], ("ellipse", "#ffffff"))
                lines.append(f'"{nid}" [label="{q(d["name"])}\\n<{d["type"].replace("_", " ")}>" shape={shape} fillcolor="{fill}"];')
                seen.add(nid)
            colour = EDGE_COLOUR.get(d["evidence_status"], "#6e7781")
            style = "solid" if d["evidence_status"] in ("explicit", "retrieved") else "dashed"
            label = STATUS.get(d["evidence_status"], (d["evidence_status"],))[0]
            if d["source_chunk_id"]:
                src = d["source_chunk_id"].split("::")[0]
                sid = f"src_{q(src)}"
                if sid not in seen:
                    lines.append(f'"{sid}" [label="{q(src)}" shape=folder fillcolor="#ffffff" fontsize=8];')
                    seen.add(sid)
                lines.append(f'"{nid}" -> "{sid}" [style=dotted color="#0969da" arrowhead=none];')
            lines.append(f'"{oid}" -> "{nid}" [color="{colour}" style={style} label="{label}"];')
    lines.append("}")
    return "\n".join(lines)


with tabs[2]:
    st.caption(
        "Generated from the selected run's actual output. Objective → dependency edges: solid = quoted evidence "
        "(explicit/retrieved), dashed = inferred/unknown. Dotted links point to the cited source document."
    )
    gm = st.radio("Method", list(available), format_func=METHODS.get, horizontal=True)
    st.graphviz_chart(dot_for(available[gm]), use_container_width=True)

# ----------------------------------------------------------------------------------------- verification

with tabs[3]:
    rv = available.get("rag_verify")
    if not rv:
        st.info("No verification run for this setup.")
    else:
        st.caption(
            f"Reviews run {rv['based_on_run']} (method B). A verdict counts only if the verifier's quote is found in the description or the cited passage."
        )
        tbl = pd.DataFrame(rv["verification"]["table"])
        tbl = tbl.rename(columns={
            "objective_id": "Objective", "dependency": "Dependency", "original_status": "B status", "final_status": "Final status",
            "verdict": "Verifier verdict", "verified_quote": "Quote verified", "objective_link_established": "Link to objective shown",
            "link_evidence": "Link evidence", "note": "Note",
        })
        st.dataframe(tbl.drop(columns=["link_source"], errors="ignore"), hide_index=True, use_container_width=True)
        removed = rv["verification"]["removed"]
        st.markdown(f"**Removed as contradicted by evidence:** {len(removed)}")
        for x in removed:
            st.markdown(f"- {x['objective_id']} · **{x['dependency']['name']}**: {x['reason']} (“{x['quote']}”, {x['source']})")

# ----------------------------------------------------------------------------------------- ground truth

def pct(x) -> str:
    return "n/a" if x is None else f"{x:.2f}"


with tabs[4]:
    from evaluation.comparison import load_score, score_and_save

    scores = {m: load_score(r["run_id"]) for m, r in available.items()}
    unscored = [m for m, s in scores.items() if s is None]
    if unscored:
        st.info(f"Not scored yet: {', '.join(METHODS[m] for m in unscored)}.")
        if st.button("Score these runs (calls the judge model)"):
            with st.spinner("Judging and scoring…"):
                for m in unscored:
                    try:
                        scores[m] = score_and_save(available[m])
                    except Exception as e:
                        st.error(f"{METHODS[m]}: {e}")
            st.rerun()

    scored = {m: s for m, s in scores.items() if s}
    if scored:
        st.markdown("#### Comparison (computed from the runs shown above)")
        metric_rows = [
            ("Precision", "precision", pct), ("Recall", "recall", pct), ("F1", "f1", pct),
            ("Unsupported claim rate", "unsupported_rate", pct),
            ("Missing dependencies", "missing", str),
            ("Items extracted (excl. duplicates)", None, None),
            ("Found beyond the description", "covered_beyond_description", str),
            ("  … of which with verified evidence", "beyond_description_with_verified_evidence", str),
            ("Over-attributions", "over_attributions", str),
            ("Not in implementation", "not_in_implementation", str),
            ("Vague items", "vague", str),
            ("Type errors", "type_errors", str),
        ]
        table = []
        for label, key, f in metric_rows:
            row = {"Metric": label}
            for m, s in scored.items():
                o = s["overall"]
                row[METHODS[m]] = f"{o['true_positives'] + o['false_positives']}" if key is None else f(o[key])
            table.append(row)
        st.dataframe(pd.DataFrame(table), hide_index=True, use_container_width=True)
        judge_models = {s["judge_model"] for s in scored.values()}
        st.caption(
            f"Micro-averaged over both objectives ({next(iter(scored.values()))['overall']['required']} reference dependencies). "
            f"Item-to-entity mapping by judge model {', '.join(judge_models)} (different from the evaluated model), "
            "then counted deterministically. Unsupported = no quote found in the description or a retrieved passage "
            "(inferred items count as unsupported). One run per method: no variance estimate."
        )
        for s in scored.values():
            for w in s["warnings"]:
                st.warning(f"{METHODS[s['method']]}: {w}")
            if s["overrides_applied"]:
                st.caption(f"{METHODS[s['method']]}: manual overrides applied to {len(s['overrides_applied'])} items.")

        st.markdown("#### Per objective")
        per = []
        for m, s in scored.items():
            for oid, o in s["per_objective"].items():
                per.append({"Method": METHODS[m], "Objective": oid, "Precision": pct(o["precision"]), "Recall": pct(o["recall"]),
                            "F1": pct(o["f1"]), "Missing": ", ".join(i.split(":")[1] for i in o["missing_ids"]) or "–"})
        st.dataframe(pd.DataFrame(per), hide_index=True, use_container_width=True)

        st.markdown("#### Item-level decisions")
        im = st.radio("Method ", list(scored), format_func=METHODS.get, horizontal=True)
        outcome_icon = {"true_positive": "✓ correct", "false_positive": "✗ incorrect", "duplicate": "= duplicate"}
        st.dataframe(
            pd.DataFrame([
                {"Objective": f"{r['extracted_objective_id']} → {r['reference_objective_id'] or '–'}", "Extracted dependency": r["dependency"],
                 "Outcome": outcome_icon[r["outcome"]], "Reason": r["reason"], "Matched entities": ", ".join(r["entity_ids"]) or "–",
                 "Evidence verified": "yes" if r["evidence_verified"] else "no", "Judge note": r["judge_explanation"]}
                for r in scored[im]["items"]
            ]),
            hide_index=True,
            use_container_width=True,
        )

    st.markdown("#### Reference dependencies")
    gt = json.loads((GROUND_TRUTH / f"{problem.lower()}_ground_truth.json").read_text())
    ents = {e["id"]: e for e in gt["entities"]}
    st.markdown(
        f"Reference established from DESDEO {gt['reference_implementation']['version']} "
        f"(`{gt['reference_implementation']['file']}`), verified by execution. It is never shown to the extraction methods."
    )
    gcols = st.columns(len(gt["objectives"]))
    for col, o in zip(gcols, gt["objectives"], strict=True):
        with col:
            st.markdown(f"**{o['objective_id']}: {o['direction']} {o['meaning'].lower()}**")
            st.dataframe(
                pd.DataFrame([{"Dependency": ents[i]["name"], "Type": ents[i]["type"].replace("_", " "), "Relationship": o["relationships"].get(i, "")} for i in o["required_dependencies"]]),
                hide_index=True,
                use_container_width=True,
            )
            if o["not_dependencies"]:
                st.caption("Not a dependency: " + "; ".join(f"{ents[n['id']]['name']} ({n['reason'].split('.')[0]})" for n in o["not_dependencies"]))
    with st.expander("Caveats"):
        for c in gt["caveats"]:
            st.markdown(f"- {c}")
