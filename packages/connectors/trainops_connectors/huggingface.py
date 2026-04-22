from __future__ import annotations

from pathlib import Path
from typing import Any

from huggingface_hub import HfApi


class HuggingFacePublisher:
    def __init__(self, token: str | None = None, api: HfApi | None = None) -> None:
        self.token = token
        self.api = api or HfApi()

    def prepare_repo(self, package_dir: Path, readme_markdown: str, metadata: dict[str, Any]) -> None:
        package_dir.mkdir(parents=True, exist_ok=True)
        (package_dir / "README.md").write_text(readme_markdown, encoding="utf-8")
        (package_dir / "trainops-metadata.json").write_text(__import__("json").dumps(metadata, indent=2), encoding="utf-8")

    def upload(self, *, repo_id: str, package_dir: Path, private: bool = False, dry_run: bool = False) -> str:
        if dry_run:
            return f"https://huggingface.co/{repo_id}/commit/dry-run"
        self.api.create_repo(repo_id=repo_id, repo_type="model", private=private, exist_ok=True, token=self.token)
        commit = self.api.upload_folder(
            repo_id=repo_id,
            repo_type="model",
            folder_path=str(package_dir),
            token=self.token,
            commit_message="Publish TrainOps model package",
        )
        return str(commit)

