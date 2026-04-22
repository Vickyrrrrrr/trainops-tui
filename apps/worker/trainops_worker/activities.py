from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from temporalio import activity
from trainops_common.database import SessionLocal
from trainops_common.events import event_bus
from trainops_connectors.evaluation import EvaluationHarness
from trainops_connectors.huggingface import HuggingFacePublisher
from trainops_connectors.skypilot import SkyPilotAdapter
from trainops_docsgen.markdown import environment_report, evaluation_summary, model_card
from trainops_domain.enums import RunStatus
from trainops_domain.models import (
    CheckpointArtifact,
    EvalResult,
    Publication,
    PublicationDraft,
    Run,
)
from trainops_domain.repositories import RunRepository
from trainops_domain.schemas import RunEvent


@activity.defn
async def emit_event(run_id: str, event_type: str, message: str, payload: dict[str, Any] | None = None) -> None:
    await event_bus.publish(RunEvent(run_id=uuid.UUID(run_id), type=event_type, message=message, payload=payload or {}))


@activity.defn
async def transition_run(run_id: str, status: str, reason: str) -> None:
    with SessionLocal() as session:
        RunRepository(session).transition(uuid.UUID(run_id), RunStatus(status), reason=reason)
        session.commit()


@activity.defn
async def provision_environment(run_id: str, compute_config: dict[str, Any]) -> dict[str, Any]:
    await emit_event(run_id, "phase", "environment check started", {"phase": "environment_check"})
    probe = {
        "status": "ok",
        "backend": compute_config.get("kind", "local_dry_run"),
        "gpu": compute_config.get("gpu", "dry-run GPU"),
        "vram_gb": compute_config.get("vram_gb", 16),
        "cuda": compute_config.get("cuda", "dry-run"),
        "python": "3.12",
        "torch": "compatible",
        "filesystem": "writable",
    }
    report = environment_report(probe)
    await emit_event(run_id, "environment", "environment check passed", {"report": report})
    return {"probe": probe, "report": report}


@activity.defn
async def launch_training(run_id: str, plan: dict[str, Any]) -> dict[str, Any]:
    adapter = SkyPilotAdapter(enabled=bool(plan.get("skypilot_enabled", False)))
    await emit_event(run_id, "phase", "training started", {"phase": "training"})
    with TemporaryDirectory(prefix="trainops-run-") as tmp:
        bundle_dir = Path(tmp)
        (bundle_dir / "config.json").write_text(__import__("json").dumps(plan, indent=2), encoding="utf-8")
        if await adapter.available():
            task_file = await adapter.render_task(bundle_dir, {"command": "python train.py --config config.json"})
            await adapter.launch(task_file, cluster_name=f"trainops-{run_id[:8]}", dry_run=bool(plan.get("dry_run", True)))
        for step in range(1, 4):
            activity.heartbeat({"step": step})
            await asyncio.sleep(0.1)
            await emit_event(run_id, "log", f"training step {step}/3 completed", {"eta_seconds": (3 - step) * 20})
        checkpoint_uri = f"trainops://runs/{run_id}/checkpoints/final"
    with SessionLocal() as session:
        session.add(CheckpointArtifact(run_id=uuid.UUID(run_id), uri=checkpoint_uri, metrics={"loss": 1.2}))
        RunRepository(session).add_spend(
            run_id=uuid.UUID(run_id),
            amount_usd=Decimal("1.00"),
            provider="internal-ledger",
            description="dry-run training spend increment",
            idempotency_key=f"{run_id}:training:1",
        )
        session.commit()
    await emit_event(run_id, "checkpoint", "checkpoint completed", {"uri": checkpoint_uri})
    return {"checkpoint_uri": checkpoint_uri}


@activity.defn
async def run_evaluation(run_id: str, model: str, tasks: list[str]) -> dict[str, Any]:
    harness = EvaluationHarness()
    with TemporaryDirectory(prefix="trainops-eval-") as tmp:
        result = await harness.run(model=model, tasks=tasks, output_path=Path(tmp) / "results.json", dry_run=True)
    metrics = {f"{task}.acc": values["acc"] for task, values in result["results"].items()}
    summary = evaluation_summary(metrics, gate_passed=True)
    with SessionLocal() as session:
        session.add(EvalResult(run_id=uuid.UUID(run_id), suite_name="default", metrics=metrics, summary_markdown=summary))
        session.commit()
    await emit_event(run_id, "eval", "evaluation completed", {"metrics": metrics})
    return {"metrics": metrics, "summary": summary, "gate_passed": True}


@activity.defn
async def draft_publication(run_id: str, repo_id: str) -> dict[str, Any]:
    with SessionLocal() as session:
        run = session.get(Run, uuid.UUID(run_id))
        if run is None:
            raise RuntimeError("run not found")
        readme = model_card(
            repo_id=repo_id,
            base_model=run.base_model or "Qwen/Qwen2.5-0.5B-Instruct",
            datasets=["operator-approved dataset"],
            license_name="apache-2.0",
            training_config={"epochs": 1, "learning_rate": "2e-4", "lora_rank": 16},
            eval_metrics={"hellaswag.acc": 0.5},
            limitations="Generated by a dry-run worker path; review before real publication.",
        )
        draft = PublicationDraft(run_id=run.id, repo_id=repo_id, readme_markdown=readme, metadata_={"repo_id": repo_id})
        session.add(draft)
        session.commit()
        draft_id = str(draft.id)
    await emit_event(run_id, "publication", "publication draft ready", {"draft_id": draft_id})
    return {"draft_id": draft_id, "readme": readme}


@activity.defn
async def publish_to_hf(run_id: str, draft_id: str, dry_run: bool = True) -> dict[str, Any]:
    with SessionLocal() as session:
        draft = session.get(PublicationDraft, uuid.UUID(draft_id))
        if draft is None:
            raise RuntimeError("publication draft not found")
        with TemporaryDirectory(prefix="trainops-publish-") as tmp:
            publisher = HuggingFacePublisher()
            package_dir = Path(tmp) / "package"
            publisher.prepare_repo(package_dir, draft.readme_markdown, draft.metadata_)
            commit_url = publisher.upload(repo_id=draft.repo_id, package_dir=package_dir, dry_run=dry_run)
        publication = Publication(
            run_id=uuid.UUID(run_id),
            publication_draft_id=draft.id,
            repo_id=draft.repo_id,
            commit_url=commit_url,
            published_at=datetime.now(UTC),
        )
        session.add(publication)
        session.commit()
    await emit_event(run_id, "publication", "publication uploaded", {"commit_url": commit_url})
    return {"commit_url": commit_url}

