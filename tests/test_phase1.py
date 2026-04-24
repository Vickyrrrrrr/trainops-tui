"""Phase 1 smoke tests — run without any real API keys or GPU."""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("TRAINOPS_CI", "true")


def test_config_save_load(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    import importlib
    import trainops_tui.config as cfg_mod
    importlib.reload(cfg_mod)

    cfg_mod.save_config(
        llm_provider="openai",
        llm_model="gpt-4o",
        llm_api_key="sk-test",
        hf_token="hf_test",
        compute_target="local",
    )
    loaded = cfg_mod.load_config()
    assert loaded is not None
    assert loaded["llm"]["api_key"] == "sk-test"
    assert loaded["huggingface"]["token"] == "hf_test"
    assert loaded["compute"]["target"] == "local"


def test_local_provider_probe():
    import asyncio
    from trainops_connectors.gpu_providers.local import LocalGPUProvider
    info = asyncio.run(LocalGPUProvider().probe())
    assert "backend" in info
    assert info["target"] == "local"


def test_local_provider_run():
    import asyncio
    from trainops_connectors.gpu_providers.local import LocalGPUProvider
    result = asyncio.run(LocalGPUProvider().run("echo hello_trainops"))
    assert result.success
    assert "hello_trainops" in result.stdout


def test_stub_planner_no_key(monkeypatch):
    monkeypatch.setattr("trainops_tui.config.get_llm_api_key", lambda: "")
    import importlib
    import trainops_agents.planner as pm
    importlib.reload(pm)
    planner = pm.AgentPlanner()
    out = planner.clarify("train a sentiment classifier", None)
    assert len(out.questions) > 0
    research = planner.research("train a sentiment classifier", None)
    assert len(research.base_model_candidates) > 0
    plan = planner.draft_plan("train a sentiment classifier", None, ["my_dataset"])
    assert "LoRA" in plan.markdown


def test_get_provider_local():
    from trainops_connectors.gpu_providers import get_provider
    from trainops_connectors.gpu_providers.local import LocalGPUProvider
    p = get_provider("local")
    assert isinstance(p, LocalGPUProvider)
