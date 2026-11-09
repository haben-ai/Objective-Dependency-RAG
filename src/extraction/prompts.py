"""Prompts. The CORE instruction is identical for all approaches; only the evidence section differs."""

CORE = """You analyse multiobjective optimization problems.

Task: for each objective function, identify its DEPENDENCIES - every component that is required to
calculate the objective's value: decision variables, parameters and constants, input data, mathematical
expressions, analytical/predictive/simulation models, intermediate outputs, external data sources.

Rules:
- List each physical quantity or variable as its own dependency. Do not merge distinct quantities into
  vague groups such as "material properties" or "geometry". Several decision variables of the same kind
  may be listed as one item only if you say exactly which ones it covers.
- Only list a component under an objective if it is needed to evaluate THAT objective. Quantities that
  only restrict the allowed values of the decision variables (bounds, constraints) are not dependencies
  of an objective.
- Include the mathematical expression that computes the objective as a dependency of type
  "mathematical_expression" if the evidence gives it or lets you describe it.
- Do not invent components. If something is probably needed but the evidence does not establish it, either
  mark it evidence_status "inferred" (you reasoned it from domain knowledge) or record it in open_questions.
- evidence_status meanings:
    explicit  - stated in the problem description; quote the sentence verbatim in "evidence".
    retrieved - stated in a retrieved passage; quote it verbatim and give its passage ID in source_chunk_id.
    inferred  - your own reasoning, not stated in any evidence; evidence = null.
    unknown   - you believe a component of this kind is needed but cannot identify it; evidence = null.
- Quotes must be copied exactly (a contiguous span of the text), not paraphrased.
- Number objectives o1, o2, ... in the order the description mentions them.
"""

DIRECT_EVIDENCE = """You have ONLY the problem description below. No documents are available, so never use
evidence_status "retrieved" and keep source_chunk_id null."""

RAG_EVIDENCE = """You have the problem description and technical passages retrieved from a documentation corpus.
Passages may be irrelevant or describe a different problem; use a passage only if it clearly describes the
same problem. Prefer "explicit" when the description itself states a fact; use "retrieved" only for facts
found in a passage."""


def format_description(description: str) -> str:
    return f"PROBLEM DESCRIPTION:\n<<<\n{description.strip()}\n>>>"


def format_passages(passages) -> str:
    if not passages:
        return "RETRIEVED PASSAGES: (none)"
    blocks = [
        f"--- passage ID: {p.chunk_id}\n(source: {p.metadata['source_file']} / {p.metadata['source_section']})\n{p.content}"
        for p in passages
    ]
    return "RETRIEVED PASSAGES:\n" + "\n\n".join(blocks)


def direct_prompt(description: str) -> tuple[str, str]:
    return CORE + "\n" + DIRECT_EVIDENCE, format_description(description)


def rag_prompt(description: str, passages) -> tuple[str, str]:
    return CORE + "\n" + RAG_EVIDENCE, format_description(description) + "\n\n" + format_passages(passages)


OBJECTIVES_SYSTEM = "List the objectives of the optimization problem described by the user. Use the user's wording."

VERIFY_SYSTEM = """You are a strict reviewer of a dependency extraction for a multiobjective optimization problem.
For EVERY dependency listed in the extraction, decide using ONLY the problem description and the retrieved
passages (not your own knowledge) whether the evidence establishes that the component is used to evaluate
that specific objective:
  supported    - the description or a passage shows it is used for this objective (e.g. it appears in the
                 objective's formula, or the text says so). Give the passage ID (or "description") and a
                 verbatim quote.
  contradicted - the evidence shows it is NOT used for this objective (e.g. the objective's formula is given
                 and does not contain it, or the passage is about a different problem). Quote the evidence.
  not_found    - nothing in the evidence settles it.
Copy objective_id and dependency_name exactly from the extraction. Do not add new dependencies."""


def verify_prompt(description: str, passages, extraction_json: str) -> tuple[str, str]:
    return VERIFY_SYSTEM, (
        format_description(description) + "\n\n" + format_passages(passages) + f"\n\nEXTRACTION TO REVIEW:\n{extraction_json}"
    )
