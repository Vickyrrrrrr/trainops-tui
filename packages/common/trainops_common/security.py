from __future__ import annotations

import base64
import hashlib
import hmac
from dataclasses import dataclass
from typing import Annotated

from cryptography.fernet import Fernet, InvalidToken
from fastapi import Header, HTTPException, status

from trainops_common.settings import get_settings


def _fernet_key(raw: str) -> bytes:
    if raw.startswith("gAAAA") or len(raw) == 44:
        return raw.encode("utf-8")
    digest = hashlib.sha256(raw.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


class SecretBox:
    def __init__(self, key: str | None = None) -> None:
        self._fernet = Fernet(_fernet_key(key or get_settings().secret_key))

    def encrypt(self, value: str) -> str:
        return self._fernet.encrypt(value.encode("utf-8")).decode("utf-8")

    def decrypt(self, value: str) -> str:
        try:
            return self._fernet.decrypt(value.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            raise ValueError("secret could not be decrypted with configured key") from exc


@dataclass(frozen=True)
class Principal:
    token_fingerprint: str


def verify_api_token(x_trainops_token: Annotated[str | None, Header()] = None) -> Principal:
    expected = get_settings().api_token
    if not x_trainops_token or not hmac.compare_digest(x_trainops_token, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid TrainOps API token")
    return Principal(token_fingerprint=hashlib.sha256(x_trainops_token.encode()).hexdigest()[:12])


def sign_approval_payload(payload: str, token: str | None = None) -> str:
    secret = (token or get_settings().api_token).encode("utf-8")
    return hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()
