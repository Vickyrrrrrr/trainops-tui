from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass
class ApiClient:
    base_url: str = "http://localhost:8080"
    token: str = "dev-token-change-me"

    @property
    def headers(self) -> dict[str, str]:
        return {"X-TrainOps-Token": self.token}

    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        async with httpx.AsyncClient(base_url=self.base_url, headers=self.headers, timeout=20) as client:
            response = await client.get(path, params=params)
            response.raise_for_status()
            return response.json()

    async def post(self, path: str, json: dict[str, Any] | None = None, params: dict[str, Any] | None = None) -> Any:
        async with httpx.AsyncClient(base_url=self.base_url, headers=self.headers, timeout=20) as client:
            response = await client.post(path, json=json, params=params)
            response.raise_for_status()
            return response.json()

    async def stream(self, run_id: str) -> AsyncIterator[str]:
        async with httpx.AsyncClient(base_url=self.base_url, headers=self.headers, timeout=None) as client:
            async with client.stream("GET", f"/api/v1/streams/runs/{run_id}") as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        yield line[6:]

