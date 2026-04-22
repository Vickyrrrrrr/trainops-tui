from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import (
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    Log,
    Markdown,
    Static,
)

from trainops_tui.widgets import CommandBar, LeftRail, RightRail


class ShellScreen(Screen):
    TITLE = "TrainOps"

    def shell(self, content) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="layout"):
            yield LeftRail(id="left-rail")
            with Vertical(id="main-pane"):
                yield content
            yield RightRail(id="right-rail")
        yield CommandBar()
        yield Footer()


class LoginScreen(ShellScreen):
    def compose(self) -> ComposeResult:
        with Horizontal(id="login-wrap"):
            yield LeftRail(id="left-rail")
            with Vertical(id="main-pane"):
                yield Label("Workspace", classes="screen-title")
                yield Input(placeholder="API URL", value="http://localhost:8080", id="api-url")
                yield Input(placeholder="TrainOps API token", password=True, value="dev-token-change-me", id="api-token")
                yield Static("Demo Workspace\noperator@example.com\nPress d for dashboard.", classes="panel")
            yield RightRail(id="right-rail")
        yield CommandBar()


class DashboardScreen(ShellScreen):
    def compose(self) -> ComposeResult:
        table = DataTable(id="runs-table")
        table.add_columns("Run", "Status", "Objective", "Spend", "Updated")
        table.add_row("demo", "awaiting approval", "Fine-tune instruction model", "$0.00", "now")
        yield from self.shell(
            Vertical(
                Label("Dashboard", classes="screen-title"),
                Static("Active runs, approvals, spend thresholds, and recent alerts.", classes="panel"),
                table,
            )
        )


class NewRunWizardScreen(ShellScreen):
    def compose(self) -> ComposeResult:
        yield from self.shell(
            Vertical(
                Label("New Run", classes="screen-title"),
                Input(placeholder="Objective", id="objective"),
                Input(placeholder="Base model, optional", id="base-model"),
                Input(placeholder="Dataset hint or URL, optional", id="dataset-hint"),
                Input(placeholder="Budget limit USD", value="25", id="budget-limit"),
                Static("Submit creates clarification questions, dataset candidates, and a plan draft.", classes="panel"),
            )
        )


class ClarificationScreen(ShellScreen):
    def compose(self) -> ComposeResult:
        yield from self.shell(
            Vertical(
                Label("Clarification", classes="screen-title"),
                Static("Success metric: pending\nLicense constraints: pending\nDataset preference: recommend public candidates", classes="panel"),
            )
        )


class DatasetReviewScreen(ShellScreen):
    def compose(self) -> ComposeResult:
        table = DataTable(id="dataset-table")
        table.add_columns("Name", "Source", "License", "Size", "Task Fit", "Risks")
        table.add_row("databricks/dolly-15k", "HF", "cc-by-sa-3.0", "15k", "instruction smoke", "license inheritance")
        table.add_row("tatsu-lab/alpaca", "HF", "cc-by-nc-4.0", "52k", "instruction baseline", "non-commercial")
        yield from self.shell(
            Vertical(
                Label("Dataset Review", classes="screen-title"),
                table,
                Static("Schema: instruction, context/input, response/output, category/text", classes="panel"),
            )
        )


class PlanApprovalScreen(ShellScreen):
    def compose(self) -> ComposeResult:
        plan = """# TrainOps Plan

## Objective
Fine-tune an instruction model with visible dataset control.

```diff
+ Dataset candidates surfaced before training
+ Budget notifications every $1
+ SkyPilot default with SSH fallback
+ Evaluation gate before publish review
```

No provisioning, training, or publishing runs until approval is signed.
"""
        yield from self.shell(
            Vertical(
                Label("Plan Approval", classes="screen-title"),
                Markdown(plan, id="plan-markdown"),
                Static("Approval required: provision, train, publish", classes="approval-bar"),
            )
        )


class LiveRunConsoleScreen(ShellScreen):
    def compose(self) -> ComposeResult:
        log = Log(id="run-log", highlight=True)
        log.write_line("waiting for run stream...")
        yield from self.shell(Vertical(Label("Live Run Console", classes="screen-title"), log))


class EvaluationResultsScreen(ShellScreen):
    def compose(self) -> ComposeResult:
        table = DataTable(id="eval-table")
        table.add_columns("Task", "Metric", "Value", "Gate")
        table.add_row("hellaswag", "acc", "0.50", "pass")
        table.add_row("arc_easy", "acc", "0.61", "pass")
        yield from self.shell(Vertical(Label("Evaluation", classes="screen-title"), table, Markdown("# Summary\n\nDry-run benchmark passed.")))


class PublishReviewScreen(ShellScreen):
    def compose(self) -> ComposeResult:
        card = """# Hugging Face Model Card Draft

- Base model: Qwen/Qwen2.5-0.5B-Instruct
- Datasets: operator-approved dataset
- License: apache-2.0
- Includes training config, eval metrics, limitations, and governance log.
"""
        yield from self.shell(Vertical(Label("Publish Review", classes="screen-title"), Markdown(card), Static("Upload requires publish approval.", classes="approval-bar")))


class ModelRegistryScreen(ShellScreen):
    def compose(self) -> ComposeResult:
        table = DataTable()
        table.add_columns("Repo", "Run", "Published", "Commit")
        table.add_row("operator/trainops-demo-model", "demo", "dry-run", "dry-run")
        yield from self.shell(Vertical(Label("Model Registry", classes="screen-title"), table))


class CredentialsScreen(ShellScreen):
    def compose(self) -> ComposeResult:
        yield from self.shell(
            Vertical(
                Label("Credentials / BYOK", classes="screen-title"),
                Input(placeholder="Hugging Face token", password=True),
                Input(placeholder="SSH private key path or paste key", password=True),
                Static("Secrets are encrypted at rest and never displayed after saving.", classes="panel"),
            )
        )


class ComputeTargetScreen(ShellScreen):
    def compose(self) -> ComposeResult:
        table = DataTable()
        table.add_columns("Name", "Kind", "GPU", "Hourly", "Status")
        table.add_row("Local dry run", "local_dry_run", "none", "$0", "ready")
        table.add_row("BYO GPU VM", "ssh", "probe required", "operator supplied", "pending")
        yield from self.shell(Vertical(Label("Compute Targets", classes="screen-title"), table))


class AuditLogScreen(ShellScreen):
    def compose(self) -> ComposeResult:
        table = DataTable()
        table.add_columns("Time", "Action", "Entity", "Reason")
        table.add_row("now", "state_transition", "run", "plan approval required")
        table.add_row("now", "approval_signed", "plan_approval", "operator approval")
        yield from self.shell(Vertical(Label("Audit Log", classes="screen-title"), table))

