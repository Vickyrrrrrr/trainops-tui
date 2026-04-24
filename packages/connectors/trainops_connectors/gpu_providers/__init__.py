"""GPU provider adapters — local, SSH, Lambda Labs, RunPod, Vast.ai, Modal."""
from __future__ import annotations

from trainops_connectors.gpu_providers.base import ComputeResult, GPUProvider
from trainops_connectors.gpu_providers.local import LocalGPUProvider

__all__ = ["GPUProvider", "ComputeResult", "LocalGPUProvider", "get_provider"]


def get_provider(target: str, **kwargs: str) -> "GPUProvider":
    """Factory — returns the correct provider for the configured compute target."""
    if target == "local":
        return LocalGPUProvider()
    if target == "ssh":
        from trainops_connectors.gpu_providers.ssh_provider import SSHProvider
        return SSHProvider(
            host=kwargs["ssh_host"],
            user=kwargs.get("ssh_user", "ubuntu"),
            key_path=kwargs.get("ssh_key_path", "~/.ssh/id_rsa"),
        )
    if target == "cloud":
        cloud = kwargs.get("cloud_provider", "")
        api_key = kwargs.get("cloud_api_key", "")
        if cloud == "lambda":
            from trainops_connectors.gpu_providers.lambda_labs import LambdaLabsProvider
            return LambdaLabsProvider(api_key=api_key)
        if cloud == "runpod":
            from trainops_connectors.gpu_providers.runpod import RunPodProvider
            return RunPodProvider(api_key=api_key)
        if cloud == "vast":
            from trainops_connectors.gpu_providers.vast import VastProvider
            return VastProvider(api_key=api_key)
        if cloud == "modal":
            from trainops_connectors.gpu_providers.modal_provider import ModalProvider
            return ModalProvider(api_key=api_key)
        raise ValueError(f"Unknown cloud provider: {cloud!r}")
    raise ValueError(f"Unknown compute target: {target!r}")
