"""SSH GPU provider — wraps asyncssh for remote VM execution."""
from __future__ import annotations

import os
from typing import AsyncIterator

import asyncssh

from trainops_connectors.gpu_providers.base import ComputeResult, GPUProvider


class SSHProvider(GPUProvider):
    def __init__(self, host: str, user: str = "ubuntu", key_path: str = "~/.ssh/id_rsa") -> None:
        self.host = host
        self.user = user
        self.key_path = key_path

    def _conn_kwargs(self) -> dict:
        return {
            "host": self.host,
            "username": self.user,
            "client_keys": [os.path.expanduser(self.key_path)],
            "known_hosts": None,
        }

    async def probe(self) -> dict[str, str]:
        async with asyncssh.connect(**self._conn_kwargs()) as conn:
            result = await conn.run(
                "nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits 2>/dev/null || echo 'no_gpu'"
            )
            return {"target": "ssh", "host": self.host, "gpu_info": result.stdout.strip()}

    async def run(
        self,
        script: str,
        env: dict[str, str] | None = None,
        *,
        workdir: str = "/tmp/trainops",
    ) -> ComputeResult:
        async with asyncssh.connect(**self._conn_kwargs()) as conn:
            await conn.run(f"mkdir -p {workdir}")
            await conn.run(f"cat > {workdir}/run.sh << 'TRAINOPS_EOF'\n{script}\nTRAINOPS_EOF")
            await conn.run(f"chmod +x {workdir}/run.sh")
            env_str = " ".join(f"{k}={v}" for k, v in (env or {}).items())
            result = await conn.run(f"cd {workdir} && {env_str} bash run.sh")
            return ComputeResult(
                exit_code=result.exit_status or 0,
                stdout=result.stdout or "",
                stderr=result.stderr or "",
                instance_id=self.host,
            )

    async def stream(
        self,
        script: str,
        env: dict[str, str] | None = None,
        *,
        workdir: str = "/tmp/trainops",
    ) -> AsyncIterator[str]:
        async with asyncssh.connect(**self._conn_kwargs()) as conn:
            await conn.run(f"mkdir -p {workdir}")
            env_str = " ".join(f"{k}={v}" for k, v in (env or {}).items())
            async with conn.create_process(f"cd {workdir} && {env_str} bash -s") as proc:
                proc.stdin.write(script)
                proc.stdin.write_eof()
                async for line in proc.stdout:
                    yield line.rstrip()

    async def estimated_cost_per_hour(self) -> float:
        return 0.0
