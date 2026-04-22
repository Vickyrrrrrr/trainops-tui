from __future__ import annotations

from trainops_agents.planner import AgentPlanner
from trainops_agents.types import DatasetCandidateOutput


class DatasetDiscovery:
    def __init__(self, planner: AgentPlanner | None = None) -> None:
        self.planner = planner or AgentPlanner()

    def discover(self, *, objective: str, dataset_hint: str | None = None) -> list[DatasetCandidateOutput]:
        return self.planner.recommend_datasets(objective, dataset_hint)

