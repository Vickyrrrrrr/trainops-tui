"""trainops CLI entry point.
Runs first-time init wizard if config is missing, then launches the TUI.
"""
from __future__ import annotations

import sys

from trainops_tui.config import CONFIG_PATH, load_config
from trainops_tui.wizard import run_wizard


def main() -> None:
    if not CONFIG_PATH.exists():
        print("\n👋  Welcome to TrainOps — first-time setup\n")
        try:
            run_wizard()
        except KeyboardInterrupt:
            print("\nSetup cancelled.")
            sys.exit(0)

    cfg = load_config()
    if not cfg:
        print("Config invalid. Run `trainops` again to re-run setup.")
        sys.exit(1)

    from trainops_tui.app import main as tui_main  # noqa: PLC0415
    tui_main()


if __name__ == "__main__":
    main()
