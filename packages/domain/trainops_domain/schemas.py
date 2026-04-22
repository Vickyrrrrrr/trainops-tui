from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from trainops_domain.enums import ApprovalAction, ApprovalStatus, ComputeKind, RunStatus, SecretKind


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UserRead(OrmModel):
    id: UUID
    email: str
    display_name: str


class WorkspaceRead(OrmModel):
    id: UUID
    organization_id: UUID
    name: str
    slug: str


class SecretCreate(BaseModel):
    workspace_id: UUID
    name: str = Field(min_length=2, max_length=120)
    kind: SecretKind
    value: SecretStr


class SecretRead(OrmModel):
    id: UUID
    workspace_id: UUID
    name: str
    kind: SecretKind
    redacted_value: str = "********"
    created_at: datetime


class ComputeTargetCreate(BaseModel):
    workspace_id: UUID
    name: str
    kind: ComputeKind
    config: dict[str, Any]
    hourly_rate_usd: Decimal = Decimal("0")

    @field_validator("hourly_rate_usd")
    @classmethod
    def non_negative_rate(cls, value: Decimal) -> Decimal:
        if value < 0:
            raise ValueError("hourly_rate_usd must be non-negative")
        return value


class ComputeTargetRead(OrmModel):
    id: UUID
    workspace_id: UUID
    name: str
    kind: ComputeKind
    config: dict[str, Any]
    hourly_rate_usd: Decimal


class TrainingIntentCreate(BaseModel):
    workspace_id: UUID
    objective: str = Field(min_length=10)
    base_model: str | None = None
    dataset_hint: str | None = None
    target_benchmarks: list[str] = Field(default_factory=list)
    budget_limit_usd: Decimal = Decimal("25")


class DatasetCandidateRead(OrmModel):
    id: UUID
    run_id: UUID
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


class DatasetDecisionCreate(BaseModel):
    candidate_id: UUID
    decision: str = Field(pattern="^(selected|rejected|uploaded)$")
    rationale: str = Field(min_length=5)


class PlanDraftRead(OrmModel):
    id: UUID
    run_id: UUID
    version: int
    markdown: str
    diff_markdown: str
    estimated_min_cost_usd: Decimal
    estimated_max_cost_usd: Decimal
    created_at: datetime


class ApprovalCreate(BaseModel):
    action: ApprovalAction
    signed_payload: str = Field(min_length=12)
    signer_user_id: UUID


class PlanApprovalRead(OrmModel):
    id: UUID
    run_id: UUID
    action: ApprovalAction
    status: ApprovalStatus
    signer_user_id: UUID | None
    signed_at: datetime | None


class RunCreate(BaseModel):
    workspace_id: UUID
    objective: str = Field(min_length=10)
    base_model: str | None = None
    dataset_hint: str | None = None
    budget_limit_usd: Decimal = Decimal("25")


class RunRead(OrmModel):
    id: UUID
    workspace_id: UUID
    status: RunStatus
    objective: str
    base_model: str | None
    budget_limit_usd: Decimal
    total_spend_usd: Decimal
    created_at: datetime
    updated_at: datetime


class RunEvent(BaseModel):
    run_id: UUID
    type: str
    message: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SpendEventCreate(BaseModel):
    run_id: UUID
    amount_usd: Decimal
    provider: str
    description: str
    idempotency_key: str


class BudgetState(BaseModel):
    run_id: UUID
    total_spend_usd: Decimal
    next_threshold_usd: Decimal
    budget_limit_usd: Decimal


class EvalResultRead(OrmModel):
    id: UUID
    run_id: UUID
    suite_name: str
    metrics: dict[str, Any]
    summary_markdown: str


class PublicationDraftRead(OrmModel):
    id: UUID
    run_id: UUID
    repo_id: str
    readme_markdown: str
    metadata: dict[str, Any] = Field(validation_alias="metadata_")


class PublicationRead(OrmModel):
    id: UUID
    run_id: UUID
    repo_id: str
    commit_url: str | None
    published_at: datetime
