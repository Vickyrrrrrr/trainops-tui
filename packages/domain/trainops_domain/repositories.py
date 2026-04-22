from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from trainops_domain.enums import ApprovalAction, ApprovalStatus, AuditAction, RunStatus
from trainops_domain.models import (
    AlertEvent,
    AuditEvent,
    DatasetCandidate,
    DatasetDecision,
    PlanApproval,
    PlanDraft,
    Run,
    SpendEvent,
)
from trainops_domain.state_machine import RunStateMachine


class NotFoundError(LookupError):
    pass


class ConflictError(RuntimeError):
    pass


def one_or_404(session: Session, statement: Select[tuple[Any]] | Select[Any]) -> Any:
    row = session.execute(statement).scalar_one_or_none()
    if row is None:
        raise NotFoundError("resource not found")
    return row


class AuditRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def record(
        self,
        *,
        workspace_id: uuid.UUID,
        action: AuditAction,
        entity_type: str,
        entity_id: str,
        reason: str,
        run_id: uuid.UUID | None = None,
        actor_id: uuid.UUID | None = None,
        payload: dict[str, Any] | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            workspace_id=workspace_id,
            run_id=run_id,
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            reason=reason,
            payload=payload or {},
        )
        self.session.add(event)
        return event


class RunRepository:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.audit = AuditRepository(session)
        self.machine = RunStateMachine()

    def get(self, run_id: uuid.UUID) -> Run:
        return one_or_404(self.session, select(Run).where(Run.id == run_id))

    def transition(
        self,
        run_id: uuid.UUID,
        target: RunStatus,
        *,
        reason: str,
        actor_id: uuid.UUID | None = None,
    ) -> Run:
        run = self.get(run_id)
        source = run.status
        transition = self.machine.transition(source, target, reason=reason, actor_id=str(actor_id) if actor_id else None)
        run.status = transition.target
        self.audit.record(
            workspace_id=run.workspace_id,
            run_id=run.id,
            actor_id=actor_id,
            action=AuditAction.STATE_TRANSITION,
            entity_type="run",
            entity_id=str(run.id),
            reason=reason,
            payload={"from": source.value, "to": target.value},
        )
        return run

    def add_spend(
        self,
        *,
        run_id: uuid.UUID,
        amount_usd: Decimal,
        provider: str,
        description: str,
        idempotency_key: str,
    ) -> tuple[SpendEvent, bool]:
        run = self.get(run_id)
        before = Decimal(run.total_spend_usd or 0)
        event = SpendEvent(
            run_id=run.id,
            amount_usd=amount_usd,
            provider=provider,
            description=description,
            idempotency_key=idempotency_key,
        )
        self.session.add(event)
        try:
            self.session.flush()
        except IntegrityError as exc:
            self.session.rollback()
            raise ConflictError("duplicate spend event idempotency key") from exc
        run.total_spend_usd = before + amount_usd
        crossed_threshold = int(before) < int(run.total_spend_usd)
        self.audit.record(
            workspace_id=run.workspace_id,
            run_id=run.id,
            action=AuditAction.SPEND_RECORDED,
            entity_type="spend_event",
            entity_id=str(event.id),
            reason=description,
            payload={"amount_usd": str(amount_usd), "total_spend_usd": str(run.total_spend_usd)},
        )
        if crossed_threshold:
            alert = AlertEvent(
                run_id=run.id,
                severity="warning",
                category="budget",
                message=f"Spend crossed ${int(run.total_spend_usd)}",
                payload={"total_spend_usd": str(run.total_spend_usd)},
            )
            self.session.add(alert)
            self.audit.record(
                workspace_id=run.workspace_id,
                run_id=run.id,
                action=AuditAction.ALERT_EMITTED,
                entity_type="alert_event",
                entity_id=str(alert.id),
                reason="spend threshold notification",
                payload=alert.payload,
            )
        return event, crossed_threshold


class ApprovalRepository:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.audit = AuditRepository(session)

    def approve(
        self,
        *,
        run_id: uuid.UUID,
        action: ApprovalAction,
        signer_user_id: uuid.UUID,
        signed_payload: str,
    ) -> PlanApproval:
        run = one_or_404(self.session, select(Run).where(Run.id == run_id))
        approval = self.session.execute(
            select(PlanApproval).where(
                PlanApproval.run_id == run_id,
                PlanApproval.action == action,
                PlanApproval.status == ApprovalStatus.PENDING,
            )
        ).scalar_one_or_none()
        if approval is None:
            approval = PlanApproval(run_id=run_id, action=action, status=ApprovalStatus.PENDING)
            self.session.add(approval)
        approval.status = ApprovalStatus.APPROVED
        approval.signer_user_id = signer_user_id
        approval.signed_at = datetime.now(UTC)
        approval.signed_payload_hash = hashlib.sha256(signed_payload.encode("utf-8")).hexdigest()
        self.audit.record(
            workspace_id=run.workspace_id,
            run_id=run_id,
            actor_id=signer_user_id,
            action=AuditAction.APPROVAL_SIGNED,
            entity_type="plan_approval",
            entity_id=str(approval.id),
            reason=f"{action.value} explicitly approved",
            payload={"signed_payload_hash": approval.signed_payload_hash},
        )
        return approval


class DatasetRepository:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.audit = AuditRepository(session)

    def latest_candidates(self, run_id: uuid.UUID) -> list[DatasetCandidate]:
        return list(self.session.execute(select(DatasetCandidate).where(DatasetCandidate.run_id == run_id)).scalars())

    def decide(self, *, run_id: uuid.UUID, candidate_id: uuid.UUID, decision: str, rationale: str, markdown: str) -> DatasetDecision:
        run = one_or_404(self.session, select(Run).where(Run.id == run_id))
        entry = DatasetDecision(
            run_id=run_id,
            candidate_id=candidate_id,
            decision=decision,
            rationale=rationale,
            markdown=markdown,
        )
        self.session.add(entry)
        self.audit.record(
            workspace_id=run.workspace_id,
            run_id=run_id,
            action=AuditAction.DATASET_SELECTED,
            entity_type="dataset_decision",
            entity_id=str(entry.id),
            reason=rationale,
            payload={"candidate_id": str(candidate_id), "decision": decision},
        )
        return entry


def latest_plan(session: Session, run_id: uuid.UUID) -> PlanDraft | None:
    return session.execute(
        select(PlanDraft)
        .where(PlanDraft.run_id == run_id)
        .order_by(PlanDraft.version.desc())
        .limit(1)
    ).scalar_one_or_none()


def run_count(session: Session) -> int:
    return int(session.scalar(select(func.count()).select_from(Run)) or 0)

