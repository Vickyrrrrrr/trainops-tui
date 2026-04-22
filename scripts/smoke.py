from __future__ import annotations

from fastapi.testclient import TestClient
from trainops_api.main import app
from trainops_api.services import ensure_demo_workspace
from trainops_common.database import SessionLocal, create_all_for_local_tests

TOKEN = {"X-TrainOps-Token": "dev-token-change-me"}


def main() -> None:
    create_all_for_local_tests()
    with SessionLocal() as session:
        workspace = ensure_demo_workspace(session)
        session.commit()
        workspace_id = str(workspace.id)

    client = TestClient(app)
    run_response = client.post(
        "/api/v1/runs",
        headers=TOKEN,
        json={
            "workspace_id": workspace_id,
            "objective": "Train a small instruction model and publish only after benchmark approval.",
            "base_model": "Qwen/Qwen2.5-0.5B-Instruct",
            "budget_limit_usd": "25",
        },
    )
    run_response.raise_for_status()
    run_id = run_response.json()["id"]
    plan_response = client.get(f"/api/v1/plans/{run_id}", headers=TOKEN)
    plan_response.raise_for_status()
    print({"run_id": run_id, "plan_version": plan_response.json()["version"]})


if __name__ == "__main__":
    main()

