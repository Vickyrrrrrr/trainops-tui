from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Button, Label, ListItem, ListView, Static

PHASES = [
    "draft",
    "clarifying",
    "researching",
    "dataset_review",
    "plan_ready",
    "awaiting_approval",
    "provisioning",
    "environment_check",
    "training",
    "evaluating",
    "publish_review",
    "publishing",
    "completed",
]


class LeftRail(Vertical):
    def compose(self) -> ComposeResult:
        yield Label("TrainOps", id="brand")
        yield ListView(*(ListItem(Label(phase.replace("_", " ").title())) for phase in PHASES), id="phase-list")


class RightRail(Vertical):
    def compose(self) -> ComposeResult:
        yield Label("Budget", classes="rail-title")
        yield Static("$0.00 spent\nNext alert: $1.00\nLimit: $25.00", id="budget-box")
        yield Label("Compute", classes="rail-title")
        yield Static("Target: Local dry run\nGPU: pending probe\nETA: pending", id="compute-box")
        yield Label("Approvals", classes="rail-title")
        yield Button("Approve Action", id="approve-action", variant="success")
        yield Button("Pause", id="pause-action")
        yield Button("Cancel", id="cancel-action", variant="error")
        yield Static("No sensitive action will run without approval.", id="approval-note")


class CommandBar(Static):
    DEFAULT_CSS = """
    CommandBar {
        dock: bottom;
        height: 1;
        background: $surface;
        color: $text-muted;
        content-align: center middle;
    }
    """

    def on_mount(self) -> None:
        self.update("ctrl+n new run | d dashboard | p plan | l console | e eval | u publish | a audit | q quit")

