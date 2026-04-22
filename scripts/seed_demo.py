from __future__ import annotations

from trainops_api.services import RunService, ensure_demo_workspace
from trainops_common.database import SessionLocal, create_all_for_local_tests
from trainops_domain.repositories import run_count


def main() -> None:
    create_all_for_local_tests()
    with SessionLocal() as session:
        workspace = ensure_demo_workspace(session)
        if run_count(session) == 0:
            RunService(session).create_run(
                workspace_id=workspace.id,
                objective="Fine-tune a small instruction model with visible dataset approval and benchmark gates.",
                base_model="Qwen/Qwen2.5-0.5B-Instruct",
                dataset_hint=None,
                budget_limit_usd=25,
            )
        session.commit()
        print(f"seeded workspace={workspace.id}")


if __name__ == "__main__":
    main()

