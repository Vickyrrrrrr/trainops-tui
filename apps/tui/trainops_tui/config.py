"""Manages ~/.trainops/config.toml — encrypted credential store + runtime settings.
All secrets are stored AES-256-GCM encrypted; only the key stays in memory.
"""
from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Any

import toml
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

CONFIG_DIR = Path.home() / ".trainops"
CONFIG_PATH = CONFIG_DIR / "config.toml"
KEY_PATH = CONFIG_DIR / ".key"


def _ensure_key() -> bytes:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if KEY_PATH.exists():
        return base64.b64decode(KEY_PATH.read_bytes())
    key = AESGCM.generate_key(bit_length=256)
    KEY_PATH.write_bytes(base64.b64encode(key))
    KEY_PATH.chmod(0o600)
    return key


def _encrypt(plaintext: str) -> str:
    key = _ensure_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ct = aesgcm.encrypt(nonce, plaintext.encode(), None)
    return base64.b64encode(nonce + ct).decode()


def _decrypt(token: str) -> str:
    key = _ensure_key()
    aesgcm = AESGCM(key)
    raw = base64.b64decode(token)
    nonce, ct = raw[:12], raw[12:]
    return aesgcm.decrypt(nonce, ct, None).decode()


def save_config(
    llm_provider: str,
    llm_model: str,
    llm_api_key: str,
    hf_token: str,
    compute_target: str,
    *,
    ssh_host: str = "",
    ssh_user: str = "ubuntu",
    ssh_key_path: str = "",
    cloud_provider: str = "",
    cloud_api_key: str = "",
    db_mode: str = "sqlite",
    database_url: str = "",
    queue_mode: str = "asyncio",
    temporal_host: str = "localhost:7233",
) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {
        "llm": {
            "provider": llm_provider,
            "model": llm_model,
            "api_key_enc": _encrypt(llm_api_key),
        },
        "huggingface": {
            "token_enc": _encrypt(hf_token),
        },
        "compute": {
            "target": compute_target,
            "ssh_host": ssh_host,
            "ssh_user": ssh_user,
            "ssh_key_path": ssh_key_path,
            "cloud_provider": cloud_provider,
            "cloud_api_key_enc": _encrypt(cloud_api_key) if cloud_api_key else "",
        },
        "database": {
            "mode": db_mode,
            "url": database_url,
        },
        "queue": {
            "mode": queue_mode,
            "temporal_host": temporal_host,
        },
    }
    CONFIG_PATH.write_text(toml.dumps(data))
    CONFIG_PATH.chmod(0o600)


def load_config() -> dict[str, Any] | None:
    if not CONFIG_PATH.exists():
        return None
    raw = toml.loads(CONFIG_PATH.read_text())
    try:
        raw["llm"]["api_key"] = _decrypt(raw["llm"]["api_key_enc"])
        raw["huggingface"]["token"] = _decrypt(raw["huggingface"]["token_enc"])
        if raw["compute"].get("cloud_api_key_enc"):
            raw["compute"]["cloud_api_key"] = _decrypt(raw["compute"]["cloud_api_key_enc"])
    except Exception:  # noqa: BLE001
        return None
    return raw


def get_llm_api_key() -> str:
    cfg = load_config()
    return cfg["llm"]["api_key"] if cfg else ""


def get_hf_token() -> str:
    cfg = load_config()
    return cfg["huggingface"]["token"] if cfg else ""


def get_compute_target() -> str:
    cfg = load_config()
    return cfg["compute"]["target"] if cfg else "local"


def get_llm_model() -> str:
    cfg = load_config()
    return cfg["llm"]["model"] if cfg else "gpt-4o"
