from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import asyncssh


@dataclass(frozen=True)
class SSHProbeResult:
    status: str
    report: dict[str, Any]


class SSHAdapter:
    async def probe(self, *, host: str, username: str, private_key: str, port: int = 22) -> SSHProbeResult:
        key = asyncssh.import_private_key(private_key)
        async with asyncssh.connect(host, port=port, username=username, client_keys=[key], known_hosts=None) as conn:
            commands = {
                "hostname": "hostname",
                "gpu": "nvidia-smi --query-gpu=name,memory.total --format=csv,noheader || true",
                "cuda": "nvcc --version || true",
                "python": "python3 --version || python --version || true",
                "torch": "python3 -c \"import torch; print(torch.__version__)\" || true",
                "disk": "df -h . | tail -1",
                "ram": "free -h | awk '/Mem:/ {print $2}'",
            }
            report: dict[str, Any] = {}
            for key_name, command in commands.items():
                result = await conn.run(command, check=False)
                report[key_name] = result.stdout.strip() or result.stderr.strip()
            return SSHProbeResult(status="ok", report=report)

    async def run(self, *, host: str, username: str, private_key: str, command: str, port: int = 22) -> str:
        key = asyncssh.import_private_key(private_key)
        async with asyncssh.connect(host, port=port, username=username, client_keys=[key], known_hosts=None) as conn:
            result = await conn.run(command, check=False)
            if result.exit_status != 0:
                raise RuntimeError(result.stderr.strip() or f"remote command failed with {result.exit_status}")
            return result.stdout

