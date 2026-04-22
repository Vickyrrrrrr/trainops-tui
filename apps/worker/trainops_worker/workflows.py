from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

from trainops_worker.types import ApprovalSignal, BudgetState, RunWorkflowInput, WorkflowSummary

with workflow.unsafe.imports_passed_through():
    from trainops_worker import activities


ACTIVITY_RETRY = RetryPolicy(initial_interval=timedelta(seconds=2), maximum_interval=timedelta(minutes=2), maximum_attempts=5)


async def call_activity(fn, *args):
    return await workflow.execute_activity(
        fn,
        args=args,
        start_to_close_timeout=timedelta(minutes=10),
        heartbeat_timeout=timedelta(seconds=30),
        retry_policy=ACTIVITY_RETRY,
    )


@workflow.defn
class ProvisioningWorkflow:
    @workflow.run
    async def run(self, run_id: str, compute_config: dict) -> dict:
        await call_activity(activities.transition_run, run_id, "provisioning", "approval received")
        await call_activity(activities.emit_event, run_id, "phase", "provisioning started", {"phase": "provisioning"})
        return await call_activity(activities.provision_environment, run_id, compute_config)


@workflow.defn
class TrainingWorkflow:
    @workflow.run
    async def run(self, run_id: str, plan: dict) -> dict:
        await call_activity(activities.transition_run, run_id, "training", "environment ready")
        return await call_activity(activities.launch_training, run_id, plan)


@workflow.defn
class EvaluationWorkflow:
    @workflow.run
    async def run(self, run_id: str, model: str, tasks: list[str]) -> dict:
        await call_activity(activities.transition_run, run_id, "evaluating", "training completed")
        return await call_activity(activities.run_evaluation, run_id, model, tasks)


@workflow.defn
class PublishingWorkflow:
    @workflow.run
    async def run(self, run_id: str, repo_id: str) -> dict:
        await call_activity(activities.transition_run, run_id, "publish_review", "evaluation gate passed")
        draft = await call_activity(activities.draft_publication, run_id, repo_id)
        return draft


@workflow.defn
class RunWorkflow:
    def __init__(self) -> None:
        self.summary = WorkflowSummary(phase="draft")
        self._cancelled = False
        self._paused = False

    @workflow.signal
    async def approve(self, signal: ApprovalSignal) -> None:
        self.summary.approvals[signal.action] = True
        self.summary.latest_message = f"{signal.action} approved"

    @workflow.signal
    async def pause(self) -> None:
        self._paused = True
        self.summary.paused = True
        self.summary.latest_message = "paused by operator"

    @workflow.signal
    async def resume(self) -> None:
        self._paused = False
        self.summary.paused = False
        self.summary.latest_message = "resumed by operator"

    @workflow.signal
    async def cancel(self) -> None:
        self._cancelled = True
        self.summary.latest_message = "cancel requested"

    @workflow.query
    def current_phase(self) -> str:
        return self.summary.phase

    @workflow.query
    def budget_state(self) -> BudgetState:
        return self.summary.budget

    @workflow.query
    def latest_summary(self) -> WorkflowSummary:
        return self.summary

    @workflow.run
    async def run(self, payload: RunWorkflowInput) -> WorkflowSummary:
        self.summary.phase = "awaiting_approval"
        self.summary.budget.budget_limit_usd = payload.budget_limit_usd
        await call_activity(activities.emit_event, payload.run_id, "phase", "waiting for provisioning approval", {"phase": "awaiting_approval"})

        await workflow.wait_condition(lambda: self._cancelled or self.summary.approvals.get("provision", False))
        if self._cancelled:
            await call_activity(activities.transition_run, payload.run_id, "cancelled", "operator cancelled before provisioning")
            self.summary.phase = "cancelled"
            return self.summary

        while self._paused:
            await workflow.sleep(timedelta(seconds=5))

        self.summary.phase = "provisioning"
        await workflow.execute_child_workflow(
            ProvisioningWorkflow.run,
            args=[payload.run_id, {"kind": "local_dry_run"}],
            id=f"{payload.run_id}-provisioning",
        )
        self.summary.phase = "awaiting_training_approval"
        await workflow.wait_condition(lambda: self._cancelled or self.summary.approvals.get("train", False))
        if self._cancelled:
            await call_activity(activities.transition_run, payload.run_id, "cancelled", "operator cancelled before training")
            self.summary.phase = "cancelled"
            return self.summary

        self.summary.phase = "training"
        await workflow.execute_child_workflow(
            TrainingWorkflow.run,
            args=[payload.run_id, {"dry_run": True, "skypilot_enabled": False}],
            id=f"{payload.run_id}-training",
        )
        self.summary.budget.total_spend_usd = "1.00"
        self.summary.budget.next_threshold_usd = "2.00"

        self.summary.phase = "evaluating"
        await workflow.execute_child_workflow(
            EvaluationWorkflow.run,
            args=[payload.run_id, payload.base_model or "Qwen/Qwen2.5-0.5B-Instruct", ["hellaswag", "arc_easy"]],
            id=f"{payload.run_id}-evaluation",
        )

        self.summary.phase = "publish_review"
        draft = await workflow.execute_child_workflow(
            PublishingWorkflow.run,
            args=[payload.run_id, "operator/trainops-demo-model"],
            id=f"{payload.run_id}-publishing-draft",
        )
        await workflow.wait_condition(lambda: self._cancelled or self.summary.approvals.get("publish", False))
        if self._cancelled:
            await call_activity(activities.transition_run, payload.run_id, "cancelled", "operator cancelled before publishing")
            self.summary.phase = "cancelled"
            return self.summary

        self.summary.phase = "publishing"
        await call_activity(activities.transition_run, payload.run_id, "publishing", "publish approved")
        await call_activity(activities.publish_to_hf, payload.run_id, draft["draft_id"], True)
        await call_activity(activities.transition_run, payload.run_id, "completed", "publication completed")
        self.summary.phase = "completed"
        self.summary.latest_message = "run completed"
        return self.summary

