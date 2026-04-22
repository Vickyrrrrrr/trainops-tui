from __future__ import annotations

from dataclasses import dataclass

from trainops_domain.enums import RunStatus


class InvalidTransitionError(ValueError):
    def __init__(self, source: RunStatus, target: RunStatus) -> None:
        super().__init__(f"invalid run state transition: {source.value} -> {target.value}")
        self.source = source
        self.target = target


ALLOWED_TRANSITIONS: dict[RunStatus, set[RunStatus]] = {
    RunStatus.DRAFT: {RunStatus.CLARIFYING, RunStatus.CANCELLED},
    RunStatus.CLARIFYING: {RunStatus.RESEARCHING, RunStatus.DATASET_REVIEW, RunStatus.CANCELLED},
    RunStatus.RESEARCHING: {RunStatus.DATASET_REVIEW, RunStatus.FAILED, RunStatus.CANCELLED},
    RunStatus.DATASET_REVIEW: {RunStatus.PLAN_READY, RunStatus.RESEARCHING, RunStatus.CANCELLED},
    RunStatus.PLAN_READY: {RunStatus.AWAITING_APPROVAL, RunStatus.DATASET_REVIEW, RunStatus.CANCELLED},
    RunStatus.AWAITING_APPROVAL: {
        RunStatus.PROVISIONING,
        RunStatus.PAUSED,
        RunStatus.CANCELLED,
        RunStatus.FAILED,
    },
    RunStatus.PROVISIONING: {
        RunStatus.ENVIRONMENT_CHECK,
        RunStatus.PAUSED,
        RunStatus.FAILED,
        RunStatus.CANCELLED,
        RunStatus.ROLLBACK_REQUIRED,
    },
    RunStatus.ENVIRONMENT_CHECK: {
        RunStatus.TRAINING,
        RunStatus.PAUSED,
        RunStatus.FAILED,
        RunStatus.CANCELLED,
    },
    RunStatus.TRAINING: {
        RunStatus.EVALUATING,
        RunStatus.PAUSED,
        RunStatus.FAILED,
        RunStatus.CANCELLED,
        RunStatus.ROLLBACK_REQUIRED,
    },
    RunStatus.EVALUATING: {
        RunStatus.PUBLISH_REVIEW,
        RunStatus.AWAITING_APPROVAL,
        RunStatus.FAILED,
        RunStatus.CANCELLED,
    },
    RunStatus.PUBLISH_REVIEW: {
        RunStatus.PUBLISHING,
        RunStatus.AWAITING_APPROVAL,
        RunStatus.CANCELLED,
    },
    RunStatus.PUBLISHING: {
        RunStatus.COMPLETED,
        RunStatus.FAILED,
        RunStatus.CANCELLED,
        RunStatus.ROLLBACK_REQUIRED,
    },
    RunStatus.PAUSED: {
        RunStatus.AWAITING_APPROVAL,
        RunStatus.PROVISIONING,
        RunStatus.ENVIRONMENT_CHECK,
        RunStatus.TRAINING,
        RunStatus.EVALUATING,
        RunStatus.PUBLISH_REVIEW,
        RunStatus.CANCELLED,
    },
    RunStatus.FAILED: {RunStatus.ROLLBACK_REQUIRED, RunStatus.CANCELLED},
    RunStatus.ROLLBACK_REQUIRED: {RunStatus.FAILED, RunStatus.CANCELLED},
    RunStatus.CANCELLED: set(),
    RunStatus.COMPLETED: set(),
}


@dataclass(frozen=True)
class Transition:
    source: RunStatus
    target: RunStatus
    reason: str
    actor_id: str | None = None


class RunStateMachine:
    def can_transition(self, source: RunStatus, target: RunStatus) -> bool:
        return target in ALLOWED_TRANSITIONS[source]

    def validate(self, source: RunStatus, target: RunStatus) -> None:
        if not self.can_transition(source, target):
            raise InvalidTransitionError(source, target)

    def transition(self, source: RunStatus, target: RunStatus, reason: str, actor_id: str | None) -> Transition:
        if not reason.strip():
            raise ValueError("state transitions require a reason")
        self.validate(source, target)
        return Transition(source=source, target=target, reason=reason, actor_id=actor_id)

