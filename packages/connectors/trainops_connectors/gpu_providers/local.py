"""Local GPU provider — runs training in a subprocess on the user's machine.
Detects CUDA/ROCm automatically. Zero SSH, zero cloud account needed.
"""
from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import sys
import tempfile
from typing import AsyncIterator

from trainops_connectors.gpu_providers.base import ComputeResult, GPUProvider


class LocalGPUProvider(GPUProvider):

    async def probe(self) -> dict[str, str]:
        info: dict[str, str] = {"target": "local"}
        if shutil.which("nvidia-smi"):
            try:
                out = subprocess.check_output(
                    ["nvidia-smi", "--query-gpu=name,memory.total,driver_version",
                     "--format=csv,noheader,nounits"],
                    text=True,
                ).strip().splitlines()[0]
                parts = [p.strip() for p in out.split(",")]
                info["gpu_name"] = parts[0] if len(parts) > 0 else "unknown"
                info["vram_mb"] = parts[1] if len(parts) > 1 else "unknown"
                info["driver"] = parts[2] if len(parts) > 2 else "unknown"
                info["backend"] = "cuda"
            except Exception:  # noqa: BLE001
                info["backend"] = "cuda_error"
        elif shutil.which("rocm-smi"):
            info["backend"] = "rocm"
        else:
            info["backend"] = "cpu"
            info["warning"] = "No GPU detected — training will run on CPU and be very slow."
        info["python"] = sys.executable
        return info

    async def run(
        self,
        script: str,
        env: dict[str, str] | None = None,
        *,
        workdir: str = "/tmp/trainops",
    ) -> ComputeResult:
        os.makedirs(workdir, exist_ok=True)
        with tempfile.NamedTemporaryFile(suffix=".sh", mode="w", delete=False) as f:
            f.write("#!/bin/bash\nset -euo pipefail\n")
            f.write(script)
            script_path = f.name
        merged_env = {**os.environ, **(env or {})}
        proc = await asyncio.create_subprocess_exec(
            "bash", script_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=merged_env,
            cwd=workdir,
        )
        stdout_b, stderr_b = await proc.communicate()
        return ComputeResult(
            exit_code=proc.returncode or 0,
            stdout=stdout_b.decode(errors="replace"),
            stderr=stderr_b.decode(errors="replace"),
            cost_usd=0.0,
            instance_id="local",
        )

    async def stream(
        self,
        script: str,
        env: dict[str, str] | None = None,
        *,
        workdir: str = "/tmp/trainops",
    ) -> AsyncIterator[str]:
        os.makedirs(workdir, exist_ok=True)
        with tempfile.NamedTemporaryFile(suffix=".sh", mode="w", delete=False) as f:
            f.write("#!/bin/bash\nset -euo pipefail\n")
            f.write(script)
            script_path = f.name
        merged_env = {**os.environ, **(env or {})}
        proc = await asyncio.create_subprocess_exec(
            "bash", script_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=merged_env,
            cwd=workdir,
        )
        assert proc.stdout
        async for line in proc.stdout:
            yield line.decode(errors="replace").rstrip()
        await proc.wait()

    async def estimated_cost_per_hour(self) -> float:
        return 0.0
