from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any


class EvaluationHarness:
    async def run(
        self,
        *,
        model: str,
        tasks: list[str],
        output_path: Path,
        limit: int | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if dry_run:
            result = {"results": {task: {"acc": 0.5, "acc_norm": 0.52} for task in tasks}}
            output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
            return result
        command = [
            "lm_eval",
            "--model",
            "hf",
            "--model_args",
            f"pretrained={model}",
            "--tasks",
            ",".join(tasks),
            "--output_path",
            str(output_path),
        ]
        if limit is not None:
            command.extend(["--limit", str(limit)])
        proc = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        stdout, _ = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(stdout.decode("utf-8", errors="replace"))
        return json.loads(output_path.read_text(encoding="utf-8"))

