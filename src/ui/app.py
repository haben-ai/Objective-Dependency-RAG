"""Guided demo: a step-by-step story for presenting the prototype.

    .venv/bin/streamlit run src/ui/app.py

The full technical view is the second page ("Detailed view").
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # make src/ importable

import plotly.graph_objects as go  # noqa: E402
import streamlit as st  # noqa: E402

from config import DESCRIPTIONS, GROUND_TRUTH, RESULTS  # noqa: E402

st.set_page_config(page_title="Guided demo", layout="centered")

PROBLEM = "RE21"
STEPS = ["The problem", "What the AI reads", "Answer key", "A · No documents", "B · With documents", "C · With checking", "Scores"]
METHOD_NAMES = {"direct": "A · No documents", "rag": "B · With documents", "rag_verify": "C · With checking"}
METHOD_COLOURS = {"direct": "#7F77DD", "rag": "#1D9E75", "rag_verify": "#0F6E56"}
DOC_SETS = {
    "full": "All documents (code, paper, docs)",
    "no_source_code": "Paper and docs (no code)",
    "documentation_only": "General docs only",
}
DOC_NAMES = {
    "desdeo_re_problem.py": "DESDEO source code",
    "tanabe_ishibuchi_supplementary_S1.txt": "Original paper (Tanabe & Ishibuchi)",
    "desdeo_howto_re_problems.md": "DESDEO guide to RE problems",
    "desdeo_explanation_problem_format.md": "DESDEO docs: problem format",
}
EVIDENCE = {
    "explicit": ("In the description", "#1a7f37"),
    "retrieved": ("Found in a document", "#0969da"),
    "inferred": ("Guessed, no proof", "#9a6700"),
    "unknown": ("Unknown", "#6e7781"),
}
GOAL_SHORT = {"f1": "Volume", "f2": "Displacement"}


# ------------------------------------------------------------------------------------------------ data


def load_runs() -> list[dict]:
    runs = []
    for f in sorted((RESULTS / "runs").glob("*.json")):
        if not f.name.startswith("superseded_"):
            runs.append(json.loads(f.read_text()))
    return runs


def pick(runs, method, variant, corpus):
    m = [r for r in runs if r["method"] == method and r["problem_id"] == PROBLEM and r["description_variant"] == variant
         and (method == "direct" or r["corpus"] == corpus)]
    # Prefer the newest run that has been scored; fall back to the newest run.
    return max(m, key=lambda r: ((RESULTS / "scores" / f"{r['run_id']}.json").exists(), r["timestamp"])) if m else None


def load_score(run_id: str):
    f = RESULTS / "scores" / f"{run_id}.json"
    return json.loads(f.read_text()) if f.exists() else None


GT = json.loads((GROUND_TRUTH / f"{PROBLEM.lower()}_ground_truth.json").read_text())
ENT = {e["id"]: e for e in GT["entities"]}
SHORT = {"x1": "Area of bar 1", "x2": "Area of bar 2", "x3": "Area of bar 3", "x4": "Area of bar 4",
         "F": "Force (load)", "E": "Material stiffness (E)", "L": "Bar length", "sigma": "Stress limit",
         "expr_volume": "Volume formula", "expr_displacement": "Displacement formula"}


def doc_name(chunk_id: str | None) -> str:
    if not chunk_id:
        return ""
    return DOC_NAMES.get(chunk_id.split("::")[0], chunk_id.split("::")[0])


def chip(text: str, colour: str) -> str:
    return (f"<span style='display:inline-block;margin:2px 4px 2px 0;padding:2px 10px;border-radius:12px;"
            f"border:1px solid {colour};color:{colour};font-size:0.85em'>{text}</span>")


def card(title: str, body: str) -> None:
    st.markdown(
        f"<div style='border:1px solid rgba(128,128,128,0.35);border-radius:12px;padding:14px 16px;margin-bottom:10px'>"
        f"<div style='font-weight:600;margin-bottom:4px'>{title}</div><div>{body}</div></div>",
        unsafe_allow_html=True,
    )


# ------------------------------------------------------------------------------------------------ sidebar

with st.sidebar:
    st.header("Settings")
    variant = st.radio("Description given to the AI", ["incomplete", "complete"],
                       format_func=lambda v: {"incomplete": "Short (some facts left out)", "complete": "Full (all facts given)"}[v])
    corpus = st.selectbox("Documents B and C may search", list(DOC_SETS), format_func=DOC_SETS.get)
    st.caption("The page shows the most recent saved results for these settings.")
    with st.expander("Run a new experiment"):
        st.caption("Calls Gemini 4 times (1–3 minutes). Free tier: 20 calls per day per model.")
        model = st.text_input("Gemini model", value="gemini-3.6-flash")
        if st.button("Run A, B and C now", type="primary"):
            from extraction.llm_client import LLMError, default_llm
            from extraction.run import run_methods, save_run

            with st.status("Running…", expanded=True) as status:
                try:
                    run_methods(default_llm(model), PROBLEM, variant, list(METHOD_NAMES), corpus,
                                on_done=lambda m, rec: (save_run(rec), st.write(f"✓ {METHOD_NAMES[m]} done")))
                    status.update(label="Done. Scores need the 'Score' button in the last step.", state="complete")
                except LLMError as e:
                    status.update(label="Failed", state="error")
                    st.error(str(e))

runs = load_runs()
RUN = {m: pick(runs, m, variant, corpus) for m in METHOD_NAMES}
SCORE = {m: (load_score(r["run_id"]) if r else None) for m, r in RUN.items()}

# ------------------------------------------------------------------------------------------------ navigation

if "step" not in st.session_state:
    st.session_state.step = STEPS[0]


def go_to(delta: int) -> None:
    i = STEPS.index(st.session_state.step) + delta
    st.session_state.step = STEPS[max(0, min(len(STEPS) - 1, i))]


st.title("Can an AI tell what an objective needs?")
st.segmented_control("Step", STEPS, key="step", label_visibility="collapsed")
step = st.session_state.step or STEPS[0]
i = STEPS.index(step)
st.caption(f"Step {i + 1} of {len(STEPS)}")
st.divider()


def nav_buttons() -> None:
    st.divider()
    a, _, b = st.columns([1, 3, 1])
    a.button("← Back", on_click=go_to, args=(-1,), disabled=i == 0, use_container_width=True)
    b.button("Next →", on_click=go_to, args=(1,), disabled=i == len(STEPS) - 1, type="primary", use_container_width=True)


# ------------------------------------------------------------------------------------------------ method step


def method_step(method: str, intro: str, show_title: bool = True) -> None:
    run, score = RUN[method], SCORE[method]
    if show_title:
        st.subheader(METHOD_NAMES[method])
    st.markdown(intro)
    if not run:
        st.warning("No saved result for these settings yet. Use **Run a new experiment** in the sidebar.")
        return

    legend = " ".join(chip(lbl, col) for lbl, col in EVIDENCE.values())
    st.markdown(f"<small>Where each answer came from:</small><br>{legend}", unsafe_allow_html=True)

    items = {(r["extracted_objective_id"], r["dependency"]): r for r in score["items"]} if score else {}
    mapping = score["objective_mapping"] if score else {}
    for o in run["extraction"]["objectives"]:
        ref = mapping.get(o["objective_id"])
        title = f"Goal: {o['direction']} {o['objective_name'].lower()}"
        rows = []
        for d in o["dependencies"]:
            label, colour = EVIDENCE.get(d["evidence_status"], (d["evidence_status"], "#6e7781"))
            r = items.get((o["objective_id"], d["name"]))
            if r is None:
                verdict = "<span style='color:#6e7781'>not scored</span>"
            elif r["outcome"] == "true_positive":
                verdict = "<span style='color:#1a7f37'>✓ correct</span>"
            elif r["outcome"] == "duplicate":
                verdict = "<span style='color:#6e7781'>= repeat</span>"
            else:
                why = r["reason"]
                why = ("not needed for this goal" if why.startswith("over-attribution") or why.startswith("real entity")
                       else "too vague" if why.startswith("too vague")
                       else "not part of the actual problem" if why.startswith("plausible") else why)
                verdict = f"<span style='color:#cf222e'>✗ wrong ({why})</span>"
            src = f" · {doc_name(d['source_chunk_id'])}" if d["source_chunk_id"] else ""
            rows.append(f"<tr><td style='padding:4px 8px'>{d['name']}</td>"
                        f"<td style='padding:4px 8px'>{chip(label, colour)}<small>{src}</small></td>"
                        f"<td style='padding:4px 8px'>{verdict}</td></tr>")
        missed = ""
        if score and ref in score["per_objective"]:
            miss = [SHORT.get(m.split(":")[1], m) for m in score["per_objective"][ref]["missing_ids"]]
            missed = ("<div style='margin-top:6px;color:#cf222e'>Missed: " + ", ".join(miss) + "</div>") if miss else \
                     "<div style='margin-top:6px;color:#1a7f37'>Nothing missed</div>"
        card(title, "<table style='width:100%'><tr><th align=left>Answer</th><th align=left>Source</th>"
                    "<th align=left>Checked against key</th></tr>" + "".join(rows) + "</table>" + missed)

    if score:
        o = score["overall"]
        c1, c2, c3 = st.columns(3)
        c1.metric("Ingredients found", f"{o['covered']} of {o['required']}")
        c2.metric("Wrong answers", o["false_positives"])
        c3.metric("Answers without proof", f"{o['unsupported_items']} of {o['items']}")
    else:
        st.info("This result has not been scored against the answer key yet (see the last step).")


# ------------------------------------------------------------------------------------------------ steps

if step == "The problem":
    st.subheader("The test problem: a four-bar truss")
    st.markdown("An engineer designs a small structure made of **four bars**. This is a standard test problem "
                "(called RE21) from the optimization library **DESDEO**.")
    c1, c2, c3 = st.columns(3)
    with c1:
        card("You choose", "How thick each of the 4 bars is")
    with c2:
        card("Goal 1", "Use as little material as possible (volume)")
    with c3:
        card("Goal 2", "Let the structure bend as little as possible (displacement)")
    st.markdown("#### The research question")
    st.markdown("To **calculate** each goal you need certain *ingredients*: numbers you choose, fixed constants, "
                "formulas. **Can an AI read a plain-English description and list those ingredients correctly?** "
                "And does it help if the AI can **search documents** first?")

elif step == "What the AI reads":
    st.subheader("What the AI is given")
    st.markdown("Every method gets **exactly this text**: no formulas, no code.")
    st.info((DESCRIPTIONS / f"{PROBLEM.lower()}_{variant}.txt").read_text())
    log = json.loads((DESCRIPTIONS / f"{PROBLEM.lower()}_descriptions.json").read_text())
    plain = {"L": "The bar length (200 cm)", "F": "The force on the truss (10 kN)",
             "E": "How stiff the material is (2×10⁵ kN/cm²)", "sigma": "The stress limit (sets how thin bars may be)",
             "expr_volume": "The formula for the volume", "expr_displacement": "The formula for the displacement"}
    left_out = [plain.get(f["ground_truth_ids"][0], "Exact limits on how thick each bar may be") if f["ground_truth_ids"]
                else "Exact limits on how thick each bar may be"
                for f in log["facts"] if f[variant].upper().startswith(("OMITTED", "NOT STATED"))]
    if left_out:
        st.markdown("**Not in this text** (the AI must find or work these out itself):")
        for fact in dict.fromkeys(left_out):
            st.markdown(f"- {fact}")

elif step == "Answer key":
    st.subheader("The answer key")
    st.markdown("Taken from DESDEO's own code and **checked by running it**: change an input, see which goal changes.")
    c1, c2 = st.columns(2)
    for col, o in zip((c1, c2), GT["objectives"], strict=True):
        with col:
            card(f"{GOAL_SHORT[o['objective_id']]} needs",
                 "".join(chip(SHORT[e], "#1a7f37") for e in o["required_dependencies"]))
    card("A trap: the stress limit",
         "It appears in the problem but affects <b>neither</b> goal. It only limits how thin the bars may be. "
         "An AI that lists it as an ingredient is wrong.")
    st.caption(f"In total: {sum(len(o['required_dependencies']) for o in GT['objectives'])} ingredients to find "
               "(6 for volume, 8 for displacement). The answer key is never shown to the AI.")

elif step == "A · No documents":
    method_step("direct", "The AI reads **only the description** and answers from its own knowledge.")

elif step == "B · With documents":
    method_step("rag", f"Same AI, same description, but first it **searches documents**: *{DOC_SETS[corpus]}*.")
    run = RUN["rag"]
    if run and run.get("retrieval"):
        docs = {}
        for p in run["retrieval"]["passages"]:
            docs.setdefault(DOC_NAMES.get(p["metadata"]["source_file"], p["metadata"]["source_file"]), []).append(p)
        with st.expander(f"What the search found ({len(run['retrieval']['passages'])} passages)"):
            for name, ps in docs.items():
                st.markdown(f"**{name}**: {len(ps)} passage(s)")
                for p in ps:
                    st.code(p["content"][:600] + ("…" if len(p["content"]) > 600 else ""), language=None, wrap_lines=True)

elif step == "C · With checking":
    run = RUN["rag_verify"]
    st.subheader(METHOD_NAMES["rag_verify"])
    st.markdown("Takes B's answers and **checks every one**: is the quoted proof really in the description or "
                "the documents, and does it show the ingredient is used for *that* goal? "
                "Answers the evidence contradicts are **removed**.")
    if run:
        t = run["verification"]["table"]
        c1, c2, c3 = st.columns(3)
        c1.metric("Confirmed by evidence", sum(r.get("objective_link_established", False) for r in t))
        c2.metric("No proof found", sum(r["final_status"] == "inferred" for r in t))
        c3.metric("Removed as wrong", len(run["verification"]["removed"]))
        st.divider()
    method_step("rag_verify", "**Final answers after checking:**", show_title=False)

elif step == "Scores":
    st.subheader("How did each method do?")
    scored = {m: s for m, s in SCORE.items() if s}
    unscored = [m for m in METHOD_NAMES if RUN[m] and not SCORE[m]]
    if unscored:
        st.info("Not scored yet: " + ", ".join(METHOD_NAMES[m] for m in unscored))
        if st.button("Score them (1 Gemini call each)"):
            from evaluation.comparison import score_and_save
            for m in unscored:
                try:
                    score_and_save(RUN[m])
                except Exception as e:
                    st.error(f"{METHOD_NAMES[m]}: {e}")
            st.rerun()
    if scored:
        names = [METHOD_NAMES[m] for m in scored]
        fig = go.Figure(go.Bar(
            x=names, y=[s["overall"]["f1"] or 0 for s in scored.values()],
            marker_color=[METHOD_COLOURS[m] for m in scored],
            text=[f"{s['overall']['f1']:.2f}" if s["overall"]["f1"] is not None else "n/a" for s in scored.values()],
            textposition="outside",
        ))
        fig.update_layout(title="Overall score (1.00 = perfect match with the answer key)", yaxis_range=[0, 1.15],
                          height=330, margin=dict(t=50, b=10, l=10, r=10), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

        rows = [
            ("Ingredients found", lambda o: f"{o['covered']} of {o['required']}"),
            ("Wrong answers", lambda o: str(o["false_positives"])),
            ("Answers without proof", lambda o: f"{o['unsupported_items']} of {o['items']}"),
            ("Found although not in the description", lambda o: str(o["covered_beyond_description"])),
        ]
        header = "".join(f"<th style='padding:4px 10px' align=left>{n}</th>" for n in names)
        body = "".join(
            f"<tr><td style='padding:4px 10px'>{label}</td>"
            + "".join(f"<td style='padding:4px 10px'>{fn(s['overall'])}</td>" for s in scored.values()) + "</tr>"
            for label, fn in rows
        )
        st.markdown(f"<table style='width:100%'><tr><th></th>{header}</tr>{body}</table>", unsafe_allow_html=True)
        with st.expander("What the overall score means"):
            st.markdown(
                "- **Precision**: of the answers given, how many are correct.\n"
                "- **Recall**: of the 14 ingredients in the answer key, how many were found.\n"
                "- **Overall score (F1)**: one number combining both.\n\n"
                + "\n".join(
                    f"- {METHOD_NAMES[m]}: precision {s['overall']['precision']:.2f}, recall {s['overall']['recall']:.2f}"
                    for m, s in scored.items() if s["overall"]["precision"] is not None
                )
            )
        st.caption("Each method was run once, so small differences may be chance. Matching answers to the key was done "
                   "by a second Gemini model and checked by hand.")
        if corpus == "full":
            st.warning("With **all documents**, the search can find the exact formulas in the DESDEO code and the "
                       "original paper. A perfect score here partly means *the answer was in the documents*. "
                       "Compare with **General docs only** in the sidebar.")

nav_buttons()
