from __future__ import annotations

import asyncio

from temporalio.client import Client
from temporalio.worker import Worker
from trainops_common.settings import get_settings
from trainops_observability.logging import configure_logging

from trainops_worker import activities
from trainops_worker.workflows import (
    EvaluationWorkflow,
    ProvisioningWorkflow,
    PublishingWorkflow,
    RunWorkflow,
    TrainingWorkflow,
)


async def main() -> None:
    settings = get_settings()
    configure_logging("trainops-worker")
    client = await Client.connect(settings.temporal_address, namespace=settings.temporal_namespace)
    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[RunWorkflow, ProvisioningWorkflow, TrainingWorkflow, EvaluationWorkflow, PublishingWorkflow],
        activities=[
            activities.emit_event,
            activities.transition_run,
            activities.provision_environment,
            activities.launch_training,
            activities.run_evaluation,
            activities.draft_publication,
            activities.publish_to_hf,
        ],
    )
    await worker.run()


def run() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    run()

