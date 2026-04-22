from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class ClarificationQuestion(BaseModel):
    key: str
    question: str
    required: bool = True


class ClarificationOutput(BaseModel):
    questions: list[ClarificationQuestion]


class ResearchOutput(BaseModel):
    base_model_candidates: list[str]
    method: str
    benchmark_tasks: list[str]
    notes_markdown: str


class DatasetCandidateOutput(BaseModel):
    name: str
    source: str
    summary: str
    task_fit: str
    schema_fields: list[str]
    split_info: dict[str, Any]
    size: str
    license: str | None
    pros: list[str]
    risks: list[str]


class PlanOutput(BaseModel):
    markdown: str
    diff_markdown: str
    hyperparameters: dict[str, Any]
    estimated_min_cost_usd: Decimal = Decimal("1")
    estimated_max_cost_usd: Decimal = Decimal("5")
    artifact_outputs: list[str] = Field(default_factory=list)


class EvaluationAnalysisOutput(BaseModel):
    passed: bool
    summary_markdown: str
    metric_deltas: dict[str, float]
    recommendation: str


class PublicationDraftOutput(BaseModel):
    repo_id: str
    readme_markdown: str
    metadata: dict[str, Any]

