from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from trainops_domain.enums import (
    ApprovalAction,
    ApprovalStatus,
    AuditAction,
    ComputeKind,
    RunStatus,
    RunStepKind,
    SecretKind,
)


def now_utc() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JSON, list[str]: JSON}


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)


class Organization(Base, TimestampMixin):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)


class Workspace(Base, TimestampMixin):
    __tablename__ = "workspaces"
    __table_args__ = (UniqueConstraint("organization_id", "slug", name="uq_workspace_org_slug"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    organization: Mapped[Organization] = relationship()


class Secret(Base, TimestampMixin):
    __tablename__ = "secrets"
    __table_args__ = (
        UniqueConstraint("workspace_id", "name", name="uq_secret_workspace_name"),
        Index("ix_secret_workspace_kind", "workspace_id", "kind"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    kind: Mapped[SecretKind] = mapped_column(Enum(SecretKind, native_enum=False), nullable=False)
    encrypted_value: Mapped[str] = mapped_column(Text, nullable=False)
    workspace: Mapped[Workspace] = relationship()


class SecretAccessAudit(Base):
    __tablename__ = "secret_access_audits"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    secret_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("secrets.id"), nullable=False, index=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    purpose: Mapped[str] = mapped_column(String(300), nullable=False)
    accessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)


class ComputeTarget(Base, TimestampMixin):
    __tablename__ = "compute_targets"
    __table_args__ = (UniqueConstraint("workspace_id", "name", name="uq_compute_workspace_name"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    kind: Mapped[ComputeKind] = mapped_column(Enum(ComputeKind, native_enum=False), nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    hourly_rate_usd: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal("0"))


class ComputeProbe(Base, TimestampMixin):
    __tablename__ = "compute_probes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    compute_target_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("compute_targets.id"), index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    gpu_model: Mapped[str | None] = mapped_column(String(160))
    vram_gb: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    cuda_version: Mapped[str | None] = mapped_column(String(80))
    python_version: Mapped[str | None] = mapped_column(String(80))
    torch_version: Mapped[str | None] = mapped_column(String(80))
    report: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class DatasetSource(Base, TimestampMixin):
    __tablename__ = "dataset_sources"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    source_type: Mapped[str] = mapped_column(String(60), nullable=False)
    uri: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)


class Run(Base, TimestampMixin):
    __tablename__ = "runs"
    __table_args__ = (Index("ix_runs_workspace_status", "workspace_id", "status"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    status: Mapped[RunStatus] = mapped_column(Enum(RunStatus, native_enum=False), default=RunStatus.DRAFT, nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    base_model: Mapped[str | None] = mapped_column(String(240))
    budget_limit_usd: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal("25"))
    total_spend_usd: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal("0"))
    temporal_workflow_id: Mapped[str | None] = mapped_column(String(240), unique=True)
    workspace: Mapped[Workspace] = relationship()


class TrainingIntent(Base, TimestampMixin):
    __tablename__ = "training_intents"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id"), nullable=False, unique=True)
    raw_intent: Mapped[str] = mapped_column(Text, nullable=False)
    structured_intent: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class ClarificationAnswer(Base, TimestampMixin):
    __tablename__ = "clarification_answers"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id"), nullable=False, index=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)


class ResearchArtifact(Base, TimestampMixin):
    __tablename__ = "research_artifacts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id"), nullable=False, index=True)
    artifact_type: Mapped[str] = mapped_column(String(80), nullable=False)
    markdown: Mapped[str] = mapped_column(Text, nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class DatasetCandidate(Base, TimestampMixin):
    __tablename__ = "dataset_candidates"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    source: Mapped[str] = mapped_column(String(240), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    task_fit: Mapped[str] = mapped_column(Text, nullable=False)
    schema_fields: Mapped[list[str]] = mapped_column(JSON, default=list)
    split_info: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    size: Mapped[str] = mapped_column(String(80), nullable=False)
    license: Mapped[str | None] = mapped_column(String(120))
    pros: Mapped[list[str]] = mapped_column(JSON, default=list)
    risks: Mapped[list[str]] = mapped_column(JSON, default=list)


class DatasetDecision(Base, TimestampMixin):
    __tablename__ = "dataset_decisions"
    __table_args__ = (Index("ix_dataset_decision_run_decision", "run_id", "decision"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id"), nullable=False, index=True)
    candidate_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("dataset_candidates.id"), nullable=True)
    decision: Mapped[str] = mapped_column(String(40), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    markdown: Mapped[str] = mapped_column(Text, nullable=False)


class BenchmarkSuite(Base, TimestampMixin):
    __tablename__ = "benchmark_suites"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    tasks: Mapped[list[str]] = mapped_column(JSON, default=list)
    gate: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class PlanDraft(Base, TimestampMixin):
    __tablename__ = "plan_drafts"
    __table_args__ = (UniqueConstraint("run_id", "version", name="uq_plan_run_version"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(nullable=False)
    markdown: Mapped[str] = mapped_column(Text, nullable=False)
    diff_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    estimated_min_cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    estimated_max_cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    plan_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class PlanApproval(Base, TimestampMixin):
    __tablename__ = "plan_approvals"
    __table_args__ = (Index("ix_plan_approval_run_action_status", "run_id", "action", "status"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id"), nullable=False, index=True)
    plan_draft_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("plan_drafts.id"))
    action: Mapped[ApprovalAction] = mapped_column(Enum(ApprovalAction, native_enum=False), nullable=False)
    status: Mapped[ApprovalStatus] = mapped_column(Enum(ApprovalStatus, native_enum=False), default=ApprovalStatus.PENDING)
    signer_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    signed_payload_hash: Mapped[str | None] = mapped_column(String(128))
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RunStep(Base, TimestampMixin):
    __tablename__ = "run_steps"
    __table_args__ = (Index("ix_run_steps_run_kind", "run_id", "kind"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id"), nullable=False, index=True)
    kind: Mapped[RunStepKind] = mapped_column(Enum(RunStepKind, native_enum=False), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class SpendPolicy(Base, TimestampMixin):
    __tablename__ = "spend_policies"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    default_limit_usd: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal("25"))
    notification_increment_usd: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal("1"))
    hard_stop_enabled: Mapped[bool] = mapped_column(default=True)


class SpendEvent(Base):
    __tablename__ = "spend_events"
    __table_args__ = (
        UniqueConstraint("run_id", "idempotency_key", name="uq_spend_run_idempotency"),
        Index("ix_spend_event_run_created", "run_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id"), nullable=False, index=True)
    amount_usd: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    provider: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(180), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)


class AlertEvent(Base):
    __tablename__ = "alert_events"
    __table_args__ = (Index("ix_alert_event_run_created", "run_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id"), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(40), nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)


class CheckpointArtifact(Base, TimestampMixin):
    __tablename__ = "checkpoint_artifacts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id"), nullable=False, index=True)
    step_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("run_steps.id"))
    uri: Mapped[str] = mapped_column(Text, nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    checksum: Mapped[str | None] = mapped_column(String(128))


class EvalResult(Base, TimestampMixin):
    __tablename__ = "eval_results"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id"), nullable=False, index=True)
    suite_name: Mapped[str] = mapped_column(String(180), nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    raw_uri: Mapped[str | None] = mapped_column(Text)
    summary_markdown: Mapped[str] = mapped_column(Text, nullable=False)


class EvalComparison(Base, TimestampMixin):
    __tablename__ = "eval_comparisons"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id"), nullable=False, index=True)
    baseline: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    target: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    gate_passed: Mapped[bool] = mapped_column(default=False)


class PublicationDraft(Base, TimestampMixin):
    __tablename__ = "publication_drafts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id"), nullable=False, index=True)
    repo_id: Mapped[str] = mapped_column(String(240), nullable=False)
    readme_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)


class Publication(Base, TimestampMixin):
    __tablename__ = "publications"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id"), nullable=False, index=True)
    publication_draft_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("publication_drafts.id"), nullable=False)
    repo_id: Mapped[str] = mapped_column(String(240), nullable=False)
    commit_url: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_workspace_created", "workspace_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("runs.id"), nullable=True, index=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    action: Mapped[AuditAction] = mapped_column(Enum(AuditAction, native_enum=False), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(120), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
