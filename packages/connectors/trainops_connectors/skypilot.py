from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SkyPilotJob:
    job_id: str
    cluster_name: str
    submitted: bool


class SkyPilotAdapter:
    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled

    async def available(self) -> bool:
        if not self.enabled:
            return False
        proc = await asyncio.create_subprocess_exec(
            "python",
            "-c",
            "import importlib.util; raise SystemExit(0 if importlib.util.find_spec('sky') else 1)",
        )
        return await proc.wait() == 0

    async def render_task(self, bundle_dir: Path, config: dict[str, Any]) -> Path:
        task_path = bundle_dir / "sky.yaml"
        resources = config.get("resources", {"accelerators": "T4:1"})
        command = config.get("command", "python train.py --config config.json")
        task_path.write_text(
            "\n".join(
                [
                    "name: trainops-run",
                    f"resources: {json.dumps(resources)}",
                    "workdir: .",
                    "run: |",
                    f"  {command}",
                ]
            ),
            encoding="utf-8",
        )
        return task_path

    async def launch(self, task_file: Path, cluster_name: str, *, dry_run: bool = False) -> SkyPilotJob:
        if dry_run:
            return SkyPilotJob(job_id=f"dry-{cluster_name}", cluster_name=cluster_name, submitted=False)
        proc = await asyncio.create_subprocess_exec(
            "sky",
            "launch",
            str(task_file),
            "-c",
            cluster_name,
            "-y",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        output = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(output[0].decode("utf-8", errors="replace"))
        return SkyPilotJob(job_id=cluster_name, cluster_name=cluster_name, submitted=True)

    async def stream_logs(self, cluster_name: str) -> AsyncIterator[str]:
        proc = await asyncio.create_subprocess_exec(
            "sky",
            "logs",
            cluster_name,
            "--follow",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        if proc.stdout is None:
            return
        async for line in proc.stdout:
            yield line.decode("utf-8", errors="replace").rstrip()

