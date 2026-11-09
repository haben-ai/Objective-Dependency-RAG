"""Common output schema for all three extraction approaches (also sent to Gemini as the response schema)."""

from typing import Literal

from pydantic import BaseModel, Field

DependencyType = Literal[
    "decision_variable",
    "parameter",
    "input_data",
    "mathematical_expression",
    "analytical_model",
    "predictive_model",
    "simulation",
    "intermediate_output",
    "external_data_source",
    "unknown",
]
EvidenceStatus = Literal["explicit", "retrieved", "inferred", "unknown"]


class Dependency(BaseModel):
    name: str = Field(description="Short name of the component, e.g. 'Applied force' or 'Cross-sectional area of bar 1'.")
    symbol: str | None = Field(default=None, description="Symbol if one is stated in the evidence, e.g. 'F' or 'x_1'.")
    type: DependencyType
    relationship: str = Field(description="How the objective uses this component.")
    evidence_status: EvidenceStatus
    evidence: str | None = Field(
        default=None, description="Verbatim quote from the description or from the cited passage. Null if inferred/unknown."
    )
    source_chunk_id: str | None = Field(
        default=None, description="ID of the retrieved passage that contains the quote. Null unless evidence_status is 'retrieved'."
    )


class ObjectiveDependencies(BaseModel):
    objective_id: str = Field(description="o1, o2, ... in the order the objectives are mentioned.")
    objective_name: str
    direction: Literal["minimize", "maximize", "unknown"]
    dependencies: list[Dependency]


class ExtractionResult(BaseModel):
    objectives: list[ObjectiveDependencies]
    open_questions: list[str] = Field(
        default_factory=list,
        description="Information needed to evaluate an objective that could not be established from the available evidence.",
    )


class ObjectiveList(BaseModel):
    objectives: list[str] = Field(description="Names of the objectives, one short phrase each, in order of mention.")


Verdict = Literal["supported", "contradicted", "not_found"]


class DependencyVerdict(BaseModel):
    objective_id: str
    dependency_name: str
    verdict: Verdict = Field(
        description="supported: the evidence states this component is used for THIS objective; contradicted: the evidence "
        "shows it is not used for this objective; not_found: no passage or description sentence settles it."
    )
    supporting_chunk_id: str | None = Field(default=None, description="'description' or a passage ID; null if not_found.")
    supporting_quote: str | None = Field(default=None, description="Verbatim quote that settles the verdict.")
    explanation: str


class VerificationResult(BaseModel):
    verdicts: list[DependencyVerdict]
