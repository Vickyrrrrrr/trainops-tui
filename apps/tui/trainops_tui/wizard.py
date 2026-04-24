"""First-time setup wizard — runs in plain terminal (no Textual) so it works
before the TUI is launched.
"""
from __future__ import annotations

from trainops_tui.config import save_config

_PROVIDERS = {
    "1": ("openai",    "gpt-4o",                   "OpenAI"),
    "2": ("anthropic", "claude-opus-4-5",           "Anthropic"),
    "3": ("gemini",    "gemini/gemini-2.0-flash",   "Google Gemini"),
    "4": ("azure",     "azure/gpt-4o",              "Azure OpenAI"),
    "5": ("ollama",    "ollama/llama3",             "Ollama (local, no key needed)"),
    "6": ("custom",    "",                          "Other / Custom"),
}

_COMPUTE = {
    "1": "local",
    "2": "ssh",
    "3": "cloud",
}

_CLOUD_PROVIDERS = {
    "1": "lambda",
    "2": "runpod",
    "3": "vast",
    "4": "modal",
}


def _prompt(msg: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    val = input(f"  {msg}{suffix}: ").strip()
    return val or default


def _choose(options: dict[str, tuple]) -> str:
    for k, v in options.items():
        label = v[2] if len(v) > 2 else v[0]
        print(f"    {k}) {label}")
    while True:
        choice = input("  Choice: ").strip()
        if choice in options:
            return choice
        print("  Invalid choice, try again.")


def run_wizard() -> None:
    print("=" * 60)
    print("  TrainOps — First-Time Setup")
    print("=" * 60)

    print("\n[1/4] Choose your LLM provider:\n")
    pkey = _choose(_PROVIDERS)
    provider, default_model, _ = _PROVIDERS[pkey]

    if pkey == "6":
        provider = _prompt("Provider name (e.g. 'cohere')")
        default_model = _prompt("Model name (e.g. 'cohere/command-r-plus')")

    model = _prompt("Model name", default_model)

    if provider == "ollama":
        api_key = "ollama"
        print("  ℹ️  Ollama uses no API key — make sure `ollama serve` is running locally.")
    else:
        api_key = _prompt(f"API key for {provider}")

    print("\n[2/4] Hugging Face token (for pushing trained models to HF Hub):\n")
    print("  Get yours at https://huggingface.co/settings/tokens")
    hf_token = _prompt("HF token (hf_...)")

    print("\n[3/4] Where will training run?\n")
    ckey = _choose(_COMPUTE)
    compute_target = _COMPUTE[ckey]

    ssh_host = ssh_user = ssh_key_path = ""
    cloud_provider = cloud_api_key = ""

    if compute_target == "ssh":
        print("\n  SSH target details:")
        ssh_host = _prompt("Host or IP (e.g. 192.168.1.10)")
        ssh_user = _prompt("SSH user", "ubuntu")
        ssh_key_path = _prompt("Path to private key", "~/.ssh/id_rsa")

    elif compute_target == "cloud":
        print("\n  Cloud GPU provider:\n")
        ck = _choose(_CLOUD_PROVIDERS)
        cloud_provider = _CLOUD_PROVIDERS[ck]
        cloud_api_key = _prompt(f"API key for {cloud_provider}")

    print("\n[4/4] Database & queue mode:\n")
    print("    1) Lightweight — SQLite + asyncio queue  (recommended for solo use)")
    print("    2) Production  — Postgres + Temporal     (team / multi-user)")
    imode = input("  Choice [1]: ").strip() or "1"

    db_mode = "sqlite"
    database_url = ""
    queue_mode = "asyncio"
    temporal_host = "localhost:7233"

    if imode == "2":
        db_mode = "postgres"
        database_url = _prompt("DATABASE_URL", "postgresql+psycopg://user:pass@localhost/trainops")
        queue_mode = "temporal"
        temporal_host = _prompt("Temporal host", "localhost:7233")

    save_config(
        llm_provider=provider,
        llm_model=model,
        llm_api_key=api_key,
        hf_token=hf_token,
        compute_target=compute_target,
        ssh_host=ssh_host,
        ssh_user=ssh_user,
        ssh_key_path=ssh_key_path,
        cloud_provider=cloud_provider,
        cloud_api_key=cloud_api_key,
        db_mode=db_mode,
        database_url=database_url,
        queue_mode=queue_mode,
        temporal_host=temporal_host,
    )

    print("\n✅  Config saved to ~/.trainops/config.toml  (secrets AES-256-GCM encrypted)")
    print("    Run `trainops` to launch the TUI.\n")
