"""AgentPlanner — backed by real LLM via LiteLLM when a key is configured,
falls back to deterministic stub when no key is present (CI / dry-run mode).
"""
from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Any

from trainops_agents.llm import build_system, build_user, chat_json
from trainops_agents.types import (
    ClarificationOutput,
    ClarificationQuestion,
    DatasetCandidateOutput,
    EvaluationAnalysisOutput,
    PlanOutput,
    PublicationDraftOutput,
    ResearchOutput,
)
from trainops_tui.config import get_llm_api_key

_HAS_LLM = bool(get_llm_api_key())

_SYSTEM_CLARIFY = """You are an expert ML engineer assistant embedded in TrainOps.
Ask the minimum clarifying questions needed for a safe, reproducible training plan.
Return ONLY valid JSON: {"questions": [{"key": str, "question": str}]}"""

_SYSTEM_RESEARCH = """You are an expert ML researcher. Given an objective and optional base model, recommend:
- 2 candidate base models from Hugging Face Hub
- Best fine-tuning method (SFT, LoRA, QLoRA, DPO, RLHF, etc.)
- 2-3 lm-evaluation-harness benchmark tasks
Return ONLY valid JSON:
{"base_model_candidates": [str], "method": str, "benchmark_tasks": [str], "notes_markdown": str}"""

_SYSTEM_PLAN = """You are an expert MLOps engineer. Produce a detailed training plan as markdown.
Include: objective, base model, dataset, method, hyperparameters, compute/budget estimate, benchmarks, artifacts.
Return ONLY valid JSON:
{"markdown": str, "diff_markdown": str, "hyperparameters": {str: any},
 "estimated_min_cost_usd": str, "estimated_max_cost_usd": str, "artifact_outputs": [str]}"""

_SYSTEM_EVAL = """You are an ML evaluation expert. Analyse benchmark metric deltas and decide if training passed.
Return ONLY valid JSON:
{"passed": bool, "summary_markdown": str, "metric_deltas": {str: float}, "recommendation": str}"""


class AgentPlanner:
    """Live LLM planner with deterministic fallback for CI/dry-run."""

    def _run(self, coro: Any) -> Any:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    fut = pool.submit(asyncio.run, coro)
                    return fut.result()
        except RuntimeError:
            pass
        return asyncio.run(coro)

    def clarify(self, objective: str, dataset_hint: str | None) -> ClarificationOutput:
        if not _HAS_LLM:
            return self._stub_clarify(objective, dataset_hint)
        prompt = f"Objective: {objective}\nDataset hint: {dataset_hint or 'none'}"
        raw = self._run(chat_json([build_system(_SYSTEM_CLARIFY), build_user(prompt)]))
        questions = [ClarificationQuestion(**q) for q in raw.get("questions", [])]
        return ClarificationOutput(questions=questions)

    def _stub_clarify(self, objective: str, dataset_hint: str | None) -> ClarificationOutput:
        questions = [
            ClarificationQuestion(key="success_metric", question="What benchmark or metric defines success?"),
            ClarificationQuestion(key="license", question="Are there license constraints on datasets or model output?"),
        ]
        if not dataset_hint:
            questions.append(ClarificationQuestion(
                key="dataset_preference",
                question="Should TrainOps recommend public datasets or wait for an upload?",
            ))
        if "chat" in objective.lower() or "instruction" in objective.lower():
            questions.append(ClarificationQuestion(
                key="safety", question="Should safety refusal behaviour be evaluated?"
            ))
        return ClarificationOutput(questions=questions)

    def research(self, objective: str, base_model: str | None) -> ResearchOutput:
        if not _HAS_LLM:
            return self._stub_research(objective, base_model)
        prompt = f"Objective: {objective}\nPreferred base model: {base_model or 'auto-select'}"
        raw = self._run(chat_json([build_system(_SYSTEM_RESEARCH), build_user(prompt)]))
        return ResearchOutput(
            base_model_candidates=raw["base_model_candidates"],
            method=raw["method"],
            benchmark_tasks=raw["benchmark_tasks"],
            notes_markdown=raw["notes_markdown"],
        )

    def _stub_research(self, objective: str, base_model: str | None) -> ResearchOutput:
        selected = base_model or "Qwen/Qwen2.5-0.5B-Instruct"
        return ResearchOutput(
            base_model_candidates=[selected, "TinyLlama/TinyLlama-1.1B-Chat-v1.0"],
            method="supervised fine-tuning with LoRA adapters; merge only after eval gate passes",
            benchmark_tasks=["hellaswag", "arc_easy"],
            notes_markdown=(
                f"## Research Summary\n\n- Objective: {objective}\n"
                f"- Preferred base model: `{selected}`\n"
                "- Method: LoRA SFT for cost-aware iteration.\n"
                "- Benchmarks: lightweight harness tasks first.\n"
            ),
        )

    def recommend_datasets(self, objective: str, dataset_hint: str | None) -> list[DatasetCandidateOutput]:
        if dataset_hint:
            return [
                DatasetCandidateOutput(
                    name=dataset_hint,
                    source="user-provided",
                    summary="Dataset provided by the operator; TrainOps will inspect schema before training.",
                    task_fit="High confidence because it was explicitly supplied.",
                    schema_fields=["text", "label"],
                    split_info={"train": "pending inspection", "validation": "pending inspection"},
                    size="unknown",
                    license="operator supplied",
                    pros=["User-controlled source", "No automatic substitution"],
                    risks=["License and schema must be confirmed before spend"],
                )
            ]
        return [
            DatasetCandidateOutput(
                name="databricks/databricks-dolly-15k",
                source="huggingface",
                summary="Instruction-following examples with categories and human-written responses.",
                task_fit="Useful for small instruction-tuning smoke runs.",
                schema_fields=["instruction", "context", "response", "category"],
                split_info={"train": "15k rows"},
                size="15k examples",
                license="cc-by-sa-3.0",
                pros=["Small", "Well-known", "Fast validation loop"],
                risks=["License inheritance requires care", "Not domain-specific"],
            ),
            DatasetCandidateOutput(
                name="tatsu-lab/alpaca",
                source="huggingface",
                summary="Instruction-response pairs generated for Stanford Alpaca style training.",
                task_fit="Good broad instruction baseline.",
                schema_fields=["instruction", "input", "output", "text"],
                split_info={"train": "52k rows"},
                size="52k examples",
                license="cc-by-nc-4.0",
                pros=["Larger instruction coverage", "Simple schema"],
                risks=["Non-commercial license", "Synthetic data artifacts"],
            ),
        ]

    def draft_plan(self, objective: str, base_model: str | None, dataset_names: list[str]) -> PlanOutput:
        if not _HAS_LLM:
            return self._stub_plan(objective, base_model, dataset_names)
        prompt = (
            f"Objective: {objective}\n"
            f"Base model: {base_model or 'auto-select'}\n"
            f"Datasets: {', '.join(dataset_names) or 'operator-selected'}"
        )
        raw = self._run(chat_json([build_system(_SYSTEM_PLAN), build_user(prompt)]))
        return PlanOutput(
            markdown=raw["markdown"],
            diff_markdown=raw["diff_markdown"],
            hyperparameters=raw["hyperparameters"],
            estimated_min_cost_usd=Decimal(raw["estimated_min_cost_usd"]),
            estimated_max_cost_usd=Decimal(raw["estimated_max_cost_usd"]),
            artifact_outputs=raw["artifact_outputs"],
        )

    def _stub_plan(self, objective: str, base_model: str | None, dataset_names: list[str]) -> PlanOutput:
        model = base_model or "Qwen/Qwen2.5-0.5B-Instruct"
        datasets = ", ".join(dataset_names) or "operator-selected dataset"
        return PlanOutput(
            markdown=(
                f"# TrainOps Plan\n\n## Objective\n{objective}\n\n"
                f"## Model\n- Base: `{model}`\n- Datasets: {datasets}\n"
                "- Method: LoRA SFT\n\n## Hyperparameters\n"
                "- epochs: 1\n- learning_rate: 2e-4\n- lora_rank: 16\n- max_seq_length: 2048\n"
            ),
            diff_markdown="+ Add LoRA SFT plan\n+ Add explicit budget gates",
            hyperparameters={"epochs": 1, "learning_rate": 2e-4, "lora_rank": 16, "max_seq_length": 2048},
            estimated_min_cost_usd=Decimal("1"),
            estimated_max_cost_usd=Decimal("5"),
            artifact_outputs=["config.json", "checkpoints/", "eval/results.json", "README.md"],
        )

    def analyze_eval(self, metrics: dict[str, float]) -> EvaluationAnalysisOutput:
        if not _HAS_LLM:
            passed = all(v >= 0 for v in metrics.values())
            return EvaluationAnalysisOutput(
                passed=passed,
                summary_markdown="# Evaluation Summary\n\n" + "\n".join(f"- {k}: {v}" for k, v in metrics.items()),
                metric_deltas=metrics,
                recommendation="Proceed to publication review." if passed else "Pause and require retrain approval.",
            )
        prompt = f"Metrics: {metrics}"
        raw = self._run(chat_json([build_system(_SYSTEM_EVAL), build_user(prompt)]))
        return EvaluationAnalysisOutput(
            passed=raw["passed"],
            summary_markdown=raw["summary_markdown"],
            metric_deltas=raw["metric_deltas"],
            recommendation=raw["recommendation"],
        )

    def draft_publication(self, repo_id: str, model_card: str) -> PublicationDraftOutput:
        return PublicationDraftOutput(
            repo_id=repo_id,
            readme_markdown=model_card,
            metadata={"library_name": "transformers", "pipeline_tag": "text-generation", "trainops": True},
        )
