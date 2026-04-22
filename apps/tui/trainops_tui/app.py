from __future__ import annotations

from textual.app import App

from trainops_tui.screens import (
    AuditLogScreen,
    ClarificationScreen,
    ComputeTargetScreen,
    CredentialsScreen,
    DashboardScreen,
    DatasetReviewScreen,
    EvaluationResultsScreen,
    LiveRunConsoleScreen,
    LoginScreen,
    ModelRegistryScreen,
    NewRunWizardScreen,
    PlanApprovalScreen,
    PublishReviewScreen,
)


class TrainOpsApp(App):
    CSS_PATH = "trainops.tcss"
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("d", "push_screen('dashboard')", "Dashboard"),
        ("ctrl+n", "push_screen('new_run')", "New Run"),
        ("c", "push_screen('clarification')", "Clarify"),
        ("r", "push_screen('datasets')", "Datasets"),
        ("p", "push_screen('plan')", "Plan"),
        ("l", "push_screen('console')", "Console"),
        ("e", "push_screen('evaluation')", "Eval"),
        ("u", "push_screen('publish')", "Publish"),
        ("m", "push_screen('registry')", "Registry"),
        ("k", "push_screen('credentials')", "Keys"),
        ("g", "push_screen('compute')", "Compute"),
        ("a", "push_screen('audit')", "Audit"),
        ("t", "toggle_dark", "Theme"),
    ]
    SCREENS = {
        "login": LoginScreen,
        "dashboard": DashboardScreen,
        "new_run": NewRunWizardScreen,
        "clarification": ClarificationScreen,
        "datasets": DatasetReviewScreen,
        "plan": PlanApprovalScreen,
        "console": LiveRunConsoleScreen,
        "evaluation": EvaluationResultsScreen,
        "publish": PublishReviewScreen,
        "registry": ModelRegistryScreen,
        "credentials": CredentialsScreen,
        "compute": ComputeTargetScreen,
        "audit": AuditLogScreen,
    }

    def on_mount(self) -> None:
        self.push_screen("login")


def main() -> None:
    TrainOpsApp().run()


if __name__ == "__main__":
    main()

