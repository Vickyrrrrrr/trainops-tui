from __future__ import annotations

from decimal import Decimal

from trainops_agents.types import (
    ClarificationOutput,
    ClarificationQuestion,
    DatasetCandidateOutput,
    EvaluationAnalysisOutput,
    PlanOutput,
    PublicationDraftOutput,
    ResearchOutput,
)


class AgentPlanner:
    """Typed deterministic planner used until a BYOK LLM provider is configured."""

    def clarify(self, objective: str, dataset_hint: str | None) -> ClarificationOutput:
        questions = [
            ClarificationQuestion(key="success_metric", question="What benchmark or metric should define success?"),
            ClarificationQuestion(key="license", question="Are there license constraints for datasets or model output?"),
        ]
        if not dataset_hint:
            questions.append(
                ClarificationQuestion(key="dataset_preference", question="Should TrainOps recommend public datasets or wait for an upload?")
            )
        if "chat" in objective.lower() or "instruction" in objective.lower():
            questions.append(ClarificationQuestion(key="safety", question="Should safety refusal behavior be evaluated?"))
        return ClarificationOutput(questions=questions)

    def research(self, objective: str, base_model: str | None) -> ResearchOutput:
        selected_model = base_model or "Qwen/Qwen2.5-0.5B-Instruct"
        return ResearchOutput(
            base_model_candidates=[selected_model, "TinyLlama/TinyLlama-1.1B-Chat-v1.0"],
            method="supervised fine-tuning with LoRA adapters; merge only after eval gate passes",
            benchmark_tasks=["hellaswag", "arc_easy"],
            notes_markdown=(
                "## Research Summary\n\n"
                f"- Objective: {objective}\n"
                f"- Preferred base model: `{selected_model}`\n"
                "- Method: LoRA SFT for cost-aware iteration.\n"
                "- Benchmarks: lightweight harness tasks first, then domain-specific evals.\n"
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
                task_fit="Good broad instruction baseline, weaker for regulated domains.",
                schema_fields=["instruction", "input", "output", "text"],
                split_info={"train": "52k rows"},
                size="52k examples",
                license="cc-by-nc-4.0",
                pros=["Larger instruction coverage", "Simple schema"],
                risks=["Non-commercial license", "Synthetic data artifacts"],
            ),
        ]

    def draft_plan(self, objective: str, base_model: str | None, dataset_names: list[str]) -> PlanOutput:
        model = base_model or "Qwen/Qwen2.5-0.5B-Instruct"
        datasets = ", ".join(dataset_names) or "operator-selected dataset"
        markdown = f"""# TrainOps Plan

## Objective
{objective}

## Model and Data
- Base model: `{model}`
- Dataset(s): {datasets}
- Method: LoRA supervised fine-tuning

## Hyperparameters
- epochs: 1
- learning_rate: 2e-4
- lora_rank: 16
- max_seq_length: 2048

## Compute and Budget
- Backend: SkyPilot by default, SSH fallback if unavailable
- Estimated runtime: 20-90 minutes
- Estimated cost: $1-$5
- Budget notifications: every $1 spent

## Benchmarks
- lm-evaluation-harness: `hellaswag`, `arc_easy`
- Gate: no more than 2% regression against base model smoke baseline

## Artifacts
- config.json
- checkpoint metadata
- evaluation summary
- Hugging Face model card draft
"""
        return PlanOutput(
            markdown=markdown,
            diff_markdown="+ Add LoRA SFT plan\n+ Add explicit budget gates\n+ Add HF publication package",
            hyperparameters={"epochs": 1, "learning_rate": 2e-4, "lora_rank": 16, "max_seq_length": 2048},
            estimated_min_cost_usd=Decimal("1"),
            estimated_max_cost_usd=Decimal("5"),
            artifact_outputs=["config.json", "checkpoints/", "eval/results.json", "README.md"],
        )

    def analyze_eval(self, metrics: dict[str, float]) -> EvaluationAnalysisOutput:
        passed = all(value >= 0 for value in metrics.values())
        return EvaluationAnalysisOutput(
            passed=passed,
            summary_markdown="\n".join(["# Evaluation Summary", "", *(f"- {k}: {v}" for k, v in metrics.items())]),
            metric_deltas=metrics,
            recommendation="Proceed to publication review." if passed else "Pause and require retrain approval before more spend.",
        )

    def draft_publication(self, repo_id: str, model_card: str) -> PublicationDraftOutput:
        return PublicationDraftOutput(
            repo_id=repo_id,
            readme_markdown=model_card,
            metadata={"library_name": "transformers", "pipeline_tag": "text-generation", "trainops": True},
        )

