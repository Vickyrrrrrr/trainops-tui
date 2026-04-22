from __future__ import annotations

from enum import StrEnum


class RunStatus(StrEnum):
    DRAFT = "draft"
    CLARIFYING = "clarifying"
    RESEARCHING = "researching"
    DATASET_REVIEW = "dataset_review"
    PLAN_READY = "plan_ready"
    AWAITING_APPROVAL = "awaiting_approval"
    PROVISIONING = "provisioning"
    ENVIRONMENT_CHECK = "environment_check"
    TRAINING = "training"
    EVALUATING = "evaluating"
    PUBLISH_REVIEW = "publish_review"
    PUBLISHING = "publishing"
    COMPLETED = "completed"
    PAUSED = "paused"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ROLLBACK_REQUIRED = "rollback_required"


class ApprovalAction(StrEnum):
    PROVISION = "provision"
    TRAIN = "train"
    PUBLISH = "publish"
    RETRAIN = "retrain"


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ComputeKind(StrEnum):
    SKYPILOT = "skypilot"
    SSH = "ssh"
    LOCAL_DRY_RUN = "local_dry_run"


class SecretKind(StrEnum):
    HUGGING_FACE = "hugging_face"
    SSH_PRIVATE_KEY = "ssh_private_key"
    CLOUD_PROVIDER = "cloud_provider"
    API_TOKEN = "api_token"


class AuditAction(StrEnum):
    STATE_TRANSITION = "state_transition"
    SECRET_CREATED = "secret_created"
    SECRET_ACCESSED = "secret_accessed"
    APPROVAL_SIGNED = "approval_signed"
    APPROVAL_REJECTED = "approval_rejected"
    DATASET_SELECTED = "dataset_selected"
    SPEND_RECORDED = "spend_recorded"
    ALERT_EMITTED = "alert_emitted"
    CONNECTOR_CALL = "connector_call"
    PUBLICATION_UPLOADED = "publication_uploaded"
    WORKFLOW_SIGNAL = "workflow_signal"


class RunStepKind(StrEnum):
    CLARIFICATION = "clarification"
    RESEARCH = "research"
    DATASET_REVIEW = "dataset_review"
    PLAN = "plan"
    PROVISIONING = "provisioning"
    TRAINING = "training"
    EVALUATION = "evaluation"
    PUBLISHING = "publishing"

