from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from trainops_common.events import event_bus
from trainops_common.security import SecretBox
from trainops_domain.enums import AuditAction, RunStatus
from trainops_domain.models import (
    AuditEvent,
    ComputeTarget,
    DatasetCandidate,
    EvalResult,
    PlanApproval,
    PlanDraft,
    Publication,
    PublicationDraft,
    Run,
    Secret,
    Workspace,
)
from trainops_domain.repositories import (
    DatasetRepository,
    NotFoundError,
    RunRepository,
    latest_plan,
)
from trainops_domain.schemas import (
    ApprovalCreate,
    ComputeTargetCreate,
    ComputeTargetRead,
    DatasetCandidateRead,
    DatasetDecisionCreate,
    EvalResultRead,
    PlanApprovalRead,
    PlanDraftRead,
    PublicationDraftRead,
    PublicationRead,
    RunCreate,
    RunEvent,
    RunRead,
    SecretCreate,
    SecretRead,
    SpendEventCreate,
    WorkspaceRead,
)

from trainops_api.deps import Authed, DbSession
from trainops_api.services import RunService, ensure_demo_workspace, publication_card_for_run

router = APIRouter(prefix="/api/v1")


@router.get("/auth/me")
def me(_: Authed) -> dict[str, str]:
    return {"principal": "api-token", "auth": "ok"}


@router.get("/workspaces", response_model=list[WorkspaceRead])
def list_workspaces(_: Authed, session: DbSession) -> list[Workspace]:
    ensure_demo_workspace(session)
    session.commit()
    return list(session.execute(select(Workspace).order_by(Workspace.created_at)).scalars())


@router.post("/secrets", response_model=SecretRead, status_code=status.HTTP_201_CREATED)
def create_secret(payload: SecretCreate, _: Authed, session: DbSession) -> Secret:
    box = SecretBox()
    secret = Secret(
        workspace_id=payload.workspace_id,
        name=payload.name,
        kind=payload.kind,
        encrypted_value=box.encrypt(payload.value.get_secret_value()),
    )
    session.add(secret)
    session.flush()
    session.add(
        AuditEvent(
            workspace_id=payload.workspace_id,
            action=AuditAction.SECRET_CREATED,
            entity_type="secret",
            entity_id=str(secret.id),
            reason=f"{payload.kind.value} secret created",
            payload={"name": payload.name},
        )
    )
    session.commit()
    return secret


@router.get("/secrets", response_model=list[SecretRead])
def list_secrets(workspace_id: uuid.UUID, _: Authed, session: DbSession) -> list[Secret]:
    return list(session.execute(select(Secret).where(Secret.workspace_id == workspace_id)).scalars())


@router.post("/compute-targets", response_model=ComputeTargetRead, status_code=status.HTTP_201_CREATED)
def create_compute_target(payload: ComputeTargetCreate, _: Authed, session: DbSession) -> ComputeTarget:
    target = ComputeTarget(**payload.model_dump())
    session.add(target)
    session.commit()
    return target


@router.get("/compute-targets", response_model=list[ComputeTargetRead])
def list_compute_targets(workspace_id: uuid.UUID, _: Authed, session: DbSession) -> list[ComputeTarget]:
    return list(session.execute(select(ComputeTarget).where(ComputeTarget.workspace_id == workspace_id)).scalars())


@router.post("/runs", response_model=RunRead, status_code=status.HTTP_201_CREATED)
def create_run(payload: RunCreate, _: Authed, session: DbSession) -> Run:
    ensure_demo_workspace(session)
    run = RunService(session).create_run(
        workspace_id=payload.workspace_id,
        objective=payload.objective,
        base_model=payload.base_model,
        dataset_hint=payload.dataset_hint,
        budget_limit_usd=payload.budget_limit_usd,
    )
    session.commit()
    return run


@router.get("/runs", response_model=list[RunRead])
def list_runs(workspace_id: uuid.UUID, _: Authed, session: DbSession) -> list[Run]:
    return list(session.execute(select(Run).where(Run.workspace_id == workspace_id).order_by(Run.created_at.desc())).scalars())


@router.get("/runs/{run_id}", response_model=RunRead)
def get_run(run_id: uuid.UUID, _: Authed, session: DbSession) -> Run:
    try:
        return RunRepository(session).get(run_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail="run not found") from exc


@router.post("/runs/{run_id}/pause", response_model=RunRead)
def pause_run(run_id: uuid.UUID, _: Authed, session: DbSession) -> Run:
    run = RunRepository(session).transition(run_id, RunStatus.PAUSED, reason="operator requested pause")
    session.commit()
    return run


@router.post("/runs/{run_id}/cancel", response_model=RunRead)
def cancel_run(run_id: uuid.UUID, _: Authed, session: DbSession) -> Run:
    run = RunRepository(session).transition(run_id, RunStatus.CANCELLED, reason="operator requested cancellation")
    session.commit()
    return run


@router.post("/runs/{run_id}/spend", status_code=status.HTTP_201_CREATED)
async def record_spend(run_id: uuid.UUID, payload: SpendEventCreate, _: Authed, session: DbSession) -> dict[str, str]:
    if payload.run_id != run_id:
        raise HTTPException(status_code=400, detail="payload run_id does not match path")
    event, crossed = RunRepository(session).add_spend(
        run_id=run_id,
        amount_usd=payload.amount_usd,
        provider=payload.provider,
        description=payload.description,
        idempotency_key=payload.idempotency_key,
    )
    session.commit()
    await event_bus.publish(
        RunEvent(
            run_id=run_id,
            type="spend",
            message=f"Spend recorded: ${payload.amount_usd}",
            payload={"event_id": str(event.id), "threshold_crossed": crossed},
        )
    )
    return {"id": str(event.id), "threshold_crossed": str(crossed)}


@router.get("/datasets/{run_id}/candidates", response_model=list[DatasetCandidateRead])
def dataset_candidates(run_id: uuid.UUID, _: Authed, session: DbSession) -> list[DatasetCandidate]:
    return DatasetRepository(session).latest_candidates(run_id)


@router.post("/datasets/{run_id}/decisions")
def dataset_decision(run_id: uuid.UUID, payload: DatasetDecisionCreate, _: Authed, session: DbSession) -> dict[str, str]:
    candidate = session.get(DatasetCandidate, payload.candidate_id)
    if candidate is None or candidate.run_id != run_id:
        raise HTTPException(status_code=404, detail="dataset candidate not found")
    markdown = (
        f"# Dataset Decision Log\n\n- Dataset: {candidate.name}\n- Decision: {payload.decision}\n\n{payload.rationale}\n"
    )
    decision = DatasetRepository(session).decide(
        run_id=run_id,
        candidate_id=payload.candidate_id,
        decision=payload.decision,
        rationale=payload.rationale,
        markdown=markdown,
    )
    session.commit()
    return {"id": str(decision.id)}


@router.get("/plans/{run_id}", response_model=PlanDraftRead)
def get_plan(run_id: uuid.UUID, _: Authed, session: DbSession) -> PlanDraft:
    plan = latest_plan(session, run_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="plan not found")
    return plan


@router.get("/approvals/{run_id}", response_model=list[PlanApprovalRead])
def approvals(run_id: uuid.UUID, _: Authed, session: DbSession) -> list[PlanApproval]:
    return list(session.execute(select(PlanApproval).where(PlanApproval.run_id == run_id)).scalars())


@router.post("/approvals/{run_id}", response_model=PlanApprovalRead)
async def approve(run_id: uuid.UUID, payload: ApprovalCreate, _: Authed, session: DbSession) -> PlanApproval:
    approval = RunService(session).approve(run_id, payload.action, payload.signer_user_id, payload.signed_payload)
    session.commit()
    await event_bus.publish(
        RunEvent(run_id=run_id, type="approval", message=f"{payload.action.value} approved", payload={"approval_id": str(approval.id)})
    )
    return approval


@router.get("/streams/runs/{run_id}")
async def stream_run(run_id: uuid.UUID, _: Authed) -> StreamingResponse:
    async def events():
        async for payload in event_bus.subscribe(str(run_id)):
            yield f"data: {payload}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")


@router.get("/evals/{run_id}", response_model=list[EvalResultRead])
def list_evals(run_id: uuid.UUID, _: Authed, session: DbSession) -> list[EvalResult]:
    return list(session.execute(select(EvalResult).where(EvalResult.run_id == run_id)).scalars())


@router.post("/evals/{run_id}/dry-run", response_model=EvalResultRead)
async def create_eval_dry_run(run_id: uuid.UUID, _: Authed, session: DbSession) -> EvalResult:
    result = EvalResult(
        run_id=run_id,
        suite_name="Smoke suite",
        metrics={"hellaswag.acc": 0.5, "arc_easy.acc": 0.61},
        summary_markdown="# Evaluation Summary\n\nDry-run benchmark completed.",
    )
    session.add(result)
    session.commit()
    await event_bus.publish(RunEvent(run_id=run_id, type="eval", message="evaluation completed", payload={"result_id": str(result.id)}))
    return result


@router.post("/publications/{run_id}/draft", response_model=PublicationDraftRead)
def draft_publication(run_id: uuid.UUID, repo_id: str, _: Authed, session: DbSession) -> PublicationDraft:
    run = session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    draft = publication_card_for_run(session, run, repo_id)
    session.commit()
    return draft


@router.post("/publications/{run_id}/dry-run", response_model=PublicationRead)
async def publish_dry_run(run_id: uuid.UUID, _: Authed, session: DbSession) -> Publication:
    draft = session.execute(select(PublicationDraft).where(PublicationDraft.run_id == run_id).limit(1)).scalar_one_or_none()
    if draft is None:
        raise HTTPException(status_code=404, detail="publication draft not found")
    publication = Publication(
        run_id=run_id,
        publication_draft_id=draft.id,
        repo_id=draft.repo_id,
        commit_url=f"https://huggingface.co/{draft.repo_id}/commit/dry-run",
    )
    session.add(publication)
    session.commit()
    await event_bus.publish(RunEvent(run_id=run_id, type="publication", message="publication dry-run completed"))
    return publication


@router.get("/audit", response_model=list[dict])
def audit(workspace_id: uuid.UUID, _: Authed, session: DbSession) -> list[dict]:
    rows = session.execute(
        select(AuditEvent).where(AuditEvent.workspace_id == workspace_id).order_by(AuditEvent.created_at.desc()).limit(200)
    ).scalars()
    return [
        {
            "id": str(row.id),
            "action": row.action.value,
            "entity_type": row.entity_type,
            "entity_id": row.entity_id,
            "reason": row.reason,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


@router.get("/healthz")
def healthz(_: Authed) -> dict[str, str]:
    return {"status": "ok"}

