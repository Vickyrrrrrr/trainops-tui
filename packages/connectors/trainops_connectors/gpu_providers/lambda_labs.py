"""Lambda Labs cloud GPU adapter."""
from __future__ import annotations

import asyncio
from typing import AsyncIterator

import httpx

from trainops_connectors.gpu_providers.base import ComputeResult, GPUProvider
from trainops_connectors.gpu_providers.ssh_provider import SSHProvider

_BASE = "https://cloud.lambdalabs.com/api/v1"


class LambdaLabsProvider(GPUProvider):
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self._instance_id: str = ""
        self._ssh: SSHProvider | None = None

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Basic {self.api_key}"}

    async def probe(self) -> dict[str, str]:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{_BASE}/instance-types", headers=self._headers())
            r.raise_for_status()
            types = list(r.json().get("data", {}).keys())
        return {"target": "lambda_labs", "available_types": ", ".join(types[:5])}

    async def _launch(self, instance_type: str = "gpu_1x_a10") -> str:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{_BASE}/instance-operations/launch",
                headers=self._headers(),
                json={"region_name": "us-east-1", "instance_type_name": instance_type,
                      "ssh_key_names": ["trainops"], "quantity": 1},
            )
            r.raise_for_status()
            instance = r.json()["data"]["instance_ids"][0]
        self._instance_id = instance
        return instance

    async def _get_ip(self) -> str:
        async with httpx.AsyncClient(timeout=120) as client:
            for _ in range(60):
                r = await client.get(f"{_BASE}/instances/{self._instance_id}", headers=self._headers())
                data = r.json().get("data", {})
                if data.get("status") == "active" and data.get("ip"):
                    return data["ip"]
                await asyncio.sleep(10)
        raise TimeoutError("Instance did not become active in time.")

    async def run(
        self, script: str, env: dict[str, str] | None = None, *, workdir: str = "/tmp/trainops"
    ) -> ComputeResult:
        await self._launch()
        ip = await self._get_ip()
        self._ssh = SSHProvider(host=ip, user="ubuntu")
        result = await self._ssh.run(script, env, workdir=workdir)
        await self._terminate()
        return result

    async def stream(
        self, script: str, env: dict[str, str] | None = None, *, workdir: str = "/tmp/trainops"
    ) -> AsyncIterator[str]:
        await self._launch()
        ip = await self._get_ip()
        self._ssh = SSHProvider(host=ip, user="ubuntu")
        async for line in self._ssh.stream(script, env, workdir=workdir):
            yield line
        await self._terminate()

    async def _terminate(self) -> None:
        if not self._instance_id:
            return
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{_BASE}/instance-operations/terminate",
                headers=self._headers(),
                json={"instance_ids": [self._instance_id]},
            )

    async def estimated_cost_per_hour(self) -> float:
        return 0.76
