from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RunWorkflowInput:
    run_id: str
    workspace_id: str
    objective: str
    base_model: str | None
    dataset_hint: str | None
    budget_limit_usd: str


@dataclass
class ApprovalSignal:
    action: str
    signer_user_id: str
    signed_payload: str


@dataclass
class BudgetState:
    total_spend_usd: str = "0"
    next_threshold_usd: str = "1"
    budget_limit_usd: str = "25"


@dataclass
class WorkflowSummary:
    phase: str
    paused: bool = False
    approvals: dict[str, bool] = field(default_factory=dict)
    budget: BudgetState = field(default_factory=BudgetState)
    latest_message: str = ""

