"""RunPod cloud GPU adapter."""
from __future__ import annotations

from typing import AsyncIterator

import httpx

from trainops_connectors.gpu_providers.base import ComputeResult, GPUProvider
from trainops_connectors.gpu_providers.ssh_provider import SSHProvider

_BASE = "https://api.runpod.io/graphql"


class RunPodProvider(GPUProvider):
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self._pod_id: str = ""
        self._ssh: SSHProvider | None = None

    async def probe(self) -> dict[str, str]:
        return {"target": "runpod", "status": "configured"}

    async def _launch(self) -> tuple[str, str, int]:
        query = """
        mutation {
          podFindAndDeployOnDemand(input: {
            cloudType: SECURE, gpuCount: 1, volumeInGb: 20, containerDiskInGb: 10,
            minMemoryInGb: 16, minVcpuCount: 4,
            gpuTypeId: "NVIDIA RTX A5000",
            imageName: "runpod/pytorch:2.2.0-py3.10-cuda12.1.1-devel-ubuntu22.04",
            dockerArgs: "", ports: "22/tcp",
          }) { id machine { podHostId } runtime { ports { ip privatePort publicPort type } } }
        }
        """
        async with httpx.AsyncClient() as client:
            r = await client.post(
                _BASE, json={"query": query},
                headers={"Authorization": f"Bearer {self.api_key}"}
            )
            r.raise_for_status()
            pod = r.json()["data"]["podFindAndDeployOnDemand"]
            self._pod_id = pod["id"]
            for port in pod["runtime"]["ports"]:
                if port["privatePort"] == 22:
                    return pod["id"], port["ip"], port["publicPort"]
        raise RuntimeError("SSH port not found in pod response")

    async def run(
        self, script: str, env: dict[str, str] | None = None, *, workdir: str = "/tmp/trainops"
    ) -> ComputeResult:
        _, ip, port = await self._launch()
        self._ssh = SSHProvider(host=f"{ip}:{port}", user="root")
        result = await self._ssh.run(script, env, workdir=workdir)
        await self._terminate()
        return result

    async def stream(
        self, script: str, env: dict[str, str] | None = None, *, workdir: str = "/tmp/trainops"
    ) -> AsyncIterator[str]:
        _, ip, port = await self._launch()
        self._ssh = SSHProvider(host=f"{ip}:{port}", user="root")
        async for line in self._ssh.stream(script, env, workdir=workdir):
            yield line
        await self._terminate()

    async def _terminate(self) -> None:
        if not self._pod_id:
            return
        query = f'mutation {{ podTerminate(input: {{ podId: "{self._pod_id}" }}) }}'
        async with httpx.AsyncClient() as client:
            await client.post(
                _BASE, json={"query": query},
                headers={"Authorization": f"Bearer {self.api_key}"}
            )

    async def estimated_cost_per_hour(self) -> float:
        return 0.44
