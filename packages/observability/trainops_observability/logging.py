from __future__ import annotations

import logging
import re
from typing import Any

import structlog
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider

SECRET_PATTERNS = [
    re.compile(r"hf_[A-Za-z0-9]{20,}"),
    re.compile(r"-----BEGIN [A-Z ]+PRIVATE KEY-----.*?-----END [A-Z ]+PRIVATE KEY-----", re.S),
    re.compile(r"(?i)(password|token|secret|api_key)=([^&\s]+)"),
]


def redact_text(value: str) -> str:
    redacted = value
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub(lambda match: f"{match.group(1)}=<redacted>" if len(match.groups()) else "<redacted>", redacted)
    return redacted


def redaction_processor(_: Any, __: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    for key, value in list(event_dict.items()):
        if isinstance(value, str):
            event_dict[key] = redact_text(value)
        elif key.lower() in {"token", "secret", "password", "private_key"}:
            event_dict[key] = "<redacted>"
    return event_dict


def configure_logging(service_name: str = "trainops") -> None:
    logging.basicConfig(format="%(message)s", level=logging.INFO)
    trace.set_tracer_provider(TracerProvider(resource=Resource.create({"service.name": service_name})))
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            redaction_processor,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

