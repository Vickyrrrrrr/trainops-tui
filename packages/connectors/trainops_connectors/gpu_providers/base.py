"""Abstract base for all GPU provider adapters."""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import AsyncIterator


@dataclass
class ComputeResult:
    exit_code: int
    stdout: str
    stderr: str
    cost_usd: float = 0.0
    instance_id: str = ""
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        return self.exit_code == 0


class GPUProvider(abc.ABC):
    """All GPU adapters implement this interface."""

    @abc.abstractmethod
    async def probe(self) -> dict[str, str]:
        """Return GPU info: {name, vram_gb, cuda_version, ...}"""

    @abc.abstractmethod
    async def run(
        self,
        script: str,
        env: dict[str, str] | None = None,
        *,
        workdir: str = "/tmp/trainops",
    ) -> ComputeResult:
        """Execute a shell script on the target and return result."""

    @abc.abstractmethod
    async def stream(
        self,
        script: str,
        env: dict[str, str] | None = None,
        *,
        workdir: str = "/tmp/trainops",
    ) -> AsyncIterator[str]:
        """Stream stdout lines from the target in real-time."""

    @abc.abstractmethod
    async def estimated_cost_per_hour(self) -> float:
        """Return estimated USD/hr for this compute target."""
