from __future__ import annotations

from typing import Any


def dataset_decision_log(candidate: dict[str, Any], decision: str, rationale: str) -> str:
    risks = "\n".join(f"- {risk}" for risk in candidate.get("risks", [])) or "- None recorded"
    pros = "\n".join(f"- {pro}" for pro in candidate.get("pros", [])) or "- None recorded"
    return f"""# Dataset Decision Log

## Candidate
- Name: {candidate.get("name")}
- Source: {candidate.get("source")}
- License: {candidate.get("license") or "unknown"}
- Size: {candidate.get("size")}

## Decision
{decision}

## Rationale
{rationale}

## Schema
{", ".join(candidate.get("schema_fields", []))}

## Pros
{pros}

## Risks
{risks}
"""


def environment_report(probe: dict[str, Any]) -> str:
    rows = "\n".join(f"- {key}: {value}" for key, value in probe.items())
    return f"# Environment Report\n\n{rows}\n"


def evaluation_summary(metrics: dict[str, Any], gate_passed: bool) -> str:
    rows = "\n".join(f"| {key} | {value} |" for key, value in metrics.items())
    return f"""# Evaluation Summary

Gate passed: **{gate_passed}**

| Metric | Value |
| --- | --- |
{rows}
"""


def run_report(run: dict[str, Any], artifacts: list[str]) -> str:
    artifact_rows = "\n".join(f"- `{artifact}`" for artifact in artifacts)
    return f"""# Run Report

- Run ID: {run.get("id")}
- Status: {run.get("status")}
- Objective: {run.get("objective")}
- Total spend: ${run.get("total_spend_usd")}

## Artifacts
{artifact_rows}
"""


def model_card(
    *,
    repo_id: str,
    base_model: str,
    datasets: list[str],
    license_name: str,
    training_config: dict[str, Any],
    eval_metrics: dict[str, Any],
    limitations: str,
) -> str:
    dataset_tags = "\n".join(f"- {dataset}" for dataset in datasets)
    config_rows = "\n".join(f"- {key}: {value}" for key, value in training_config.items())
    metric_rows = "\n".join(f"| {key} | {value} |" for key, value in eval_metrics.items())
    return f"""---
license: {license_name}
base_model: {base_model}
library_name: transformers
pipeline_tag: text-generation
tags:
- trainops
- human-in-the-loop
---

# {repo_id}

## Model Details

This model was produced with TrainOps TUI from base model `{base_model}`.

## Datasets

{dataset_tags}

## Training Configuration

{config_rows}

## Evaluation

| Metric | Value |
| --- | --- |
{metric_rows}

## Limitations

{limitations}

## Reproducibility and Governance

TrainOps recorded the dataset decision log, approval signatures, spend ledger,
environment report, benchmark output, and publication approval before upload.
"""

