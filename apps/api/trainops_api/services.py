from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session
from trainops_agents.planner import AgentPlanner
from trainops_connectors.datasets import DatasetDiscovery
from trainops_docsgen.markdown import dataset_decision_log, model_card
from trainops_domain.enums import (
    ApprovalAction,
    ApprovalStatus,
    AuditAction,
    ComputeKind,
    RunStatus,
)
from trainops_domain.models import (
    AuditEvent,
    BenchmarkSuite,
    ComputeTarget,
    DatasetCandidate,
    DatasetDecision,
    Organization,
    PlanApproval,
    PlanDraft,
    PublicationDraft,
    Run,
    SpendPolicy,
    TrainingIntent,
    User,
    Workspace,
)
from trainops_domain.repositories import ApprovalRepository, RunRepository


class RunService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.planner = AgentPlanner()
        self.datasets = DatasetDiscovery(self.planner)

    def create_run(
        self,
        *,
        workspace_id: uuid.UUID,
        objective: str,
        base_model: str | None,
        dataset_hint: str | None,
        budget_limit_usd: Decimal,
    ) -> Run:
        run = Run(
            workspace_id=workspace_id,
            objective=objective,
            base_model=base_model,
            budget_limit_usd=budget_limit_usd,
            status=RunStatus.DRAFT,
            temporal_workflow_id=f"trainops-run-{uuid.uuid4()}",
        )
        self.session.add(run)
        self.session.flush()
        self.session.add(
            TrainingIntent(
                run_id=run.id,
                raw_intent=objective,
                structured_intent={
                    "base_model": base_model,
                    "dataset_hint": dataset_hint,
                    "budget_limit_usd": str(budget_limit_usd),
                },
            )
        )
        RunRepository(self.session).transition(run.id, RunStatus.CLARIFYING, reason="new run created")
        clarification = self.planner.clarify(objective, dataset_hint)
        self.session.add(
            AuditEvent(
                workspace_id=workspace_id,
                run_id=run.id,
                action=AuditAction.CONNECTOR_CALL,
                entity_type="agent.clarification",
                entity_id=str(run.id),
                reason="clarification questions generated",
                payload=clarification.model_dump(),
            )
        )
        RunRepository(self.session).transition(run.id, RunStatus.RESEARCHING, reason="clarification draft ready")
        research = self.planner.research(objective, base_model)
        self.session.add(
            AuditEvent(
                workspace_id=workspace_id,
                run_id=run.id,
                action=AuditAction.CONNECTOR_CALL,
                entity_type="agent.research",
                entity_id=str(run.id),
                reason="research summary generated",
                payload=research.model_dump(),
            )
        )
        RunRepository(self.session).transition(run.id, RunStatus.DATASET_REVIEW, reason="research completed")
        candidates = self.datasets.discover(objective=objective, dataset_hint=dataset_hint)
        for candidate in candidates:
            self.session.add(DatasetCandidate(run_id=run.id, **candidate.model_dump()))
        self.session.flush()
        first = self.session.execute(select(DatasetCandidate).where(DatasetCandidate.run_id == run.id).limit(1)).scalar_one()
        decision_md = dataset_decision_log(
            {
                "name": first.name,
                "source": first.source,
                "license": first.license,
                "size": first.size,
                "schema_fields": first.schema_fields,
                "pros": first.pros,
                "risks": first.risks,
            },
            "recommended",
            "Auto-recommended for operator review; not selected until explicit approval.",
        )
        self.session.add(
            DatasetDecision(
                run_id=run.id,
                candidate_id=first.id,
                decision="recommended",
                rationale="Recommended pending operator review.",
                markdown=decision_md,
            )
        )
        plan = self.planner.draft_plan(objective, base_model, [first.name])
        RunRepository(self.session).transition(run.id, RunStatus.PLAN_READY, reason="dataset candidates prepared")
        plan_row = PlanDraft(
            run_id=run.id,
            version=1,
            markdown=plan.markdown,
            diff_markdown=plan.diff_markdown,
            estimated_min_cost_usd=plan.estimated_min_cost_usd,
            estimated_max_cost_usd=plan.estimated_max_cost_usd,
            plan_json=plan.model_dump(mode="json"),
        )
        self.session.add(plan_row)
        self.session.flush()
        self.session.add_all(
            [
                PlanApproval(run_id=run.id, plan_draft_id=plan_row.id, action=ApprovalAction.PROVISION, status=ApprovalStatus.PENDING),
                PlanApproval(run_id=run.id, plan_draft_id=plan_row.id, action=ApprovalAction.TRAIN, status=ApprovalStatus.PENDING),
                PlanApproval(run_id=run.id, plan_draft_id=plan_row.id, action=ApprovalAction.PUBLISH, status=ApprovalStatus.PENDING),
            ]
        )
        RunRepository(self.session).transition(run.id, RunStatus.AWAITING_APPROVAL, reason="plan approval required")
        return run

    def approve(self, run_id: uuid.UUID, approval: ApprovalAction, signer_user_id: uuid.UUID, payload: str) -> PlanApproval:
        row = ApprovalRepository(self.session).approve(
            run_id=run_id,
            action=approval,
            signer_user_id=signer_user_id,
            signed_payload=payload,
        )
        return row


def ensure_demo_workspace(session: Session) -> Workspace:
    workspace = session.execute(select(Workspace).limit(1)).scalar_one_or_none()
    if workspace:
        return workspace
    user = User(email="operator@example.com", display_name="TrainOps Operator")
    org = Organization(name="Demo Org", slug="demo")
    session.add_all([user, org])
    session.flush()
    workspace = Workspace(organization_id=org.id, name="Demo Workspace", slug="demo")
    session.add(workspace)
    session.flush()
    session.add_all(
        [
            SpendPolicy(workspace_id=workspace.id),
            ComputeTarget(
                workspace_id=workspace.id,
                name="Local dry run",
                kind=ComputeKind.LOCAL_DRY_RUN,
                config={"dry_run": True},
                hourly_rate_usd=Decimal("0"),
            ),
            BenchmarkSuite(workspace_id=workspace.id, name="Smoke suite", tasks=["hellaswag", "arc_easy"], gate={"max_regression": 0.02}),
        ]
    )
    return workspace


def publication_card_for_run(session: Session, run: Run, repo_id: str) -> PublicationDraft:
    candidates = list(session.execute(select(DatasetCandidate).where(DatasetCandidate.run_id == run.id)).scalars())
    readme = model_card(
        repo_id=repo_id,
        base_model=run.base_model or "Qwen/Qwen2.5-0.5B-Instruct",
        datasets=[candidate.name for candidate in candidates[:2]],
        license_name="apache-2.0",
        training_config={"epochs": 1, "learning_rate": "2e-4", "lora_rank": 16},
        eval_metrics={"hellaswag": 0.52, "arc_easy": 0.61},
        limitations="This draft requires operator review before publication.",
    )
    draft = PublicationDraft(run_id=run.id, repo_id=repo_id, readme_markdown=readme, metadata_={"repo_id": repo_id})
    session.add(draft)
    return draft

