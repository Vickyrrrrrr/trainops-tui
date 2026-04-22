FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    UV_SYSTEM_PYTHON=1

WORKDIR /app
RUN pip install --no-cache-dir uv
COPY pyproject.toml README.md /app/
COPY apps /app/apps
COPY packages /app/packages
COPY infra /app/infra
COPY scripts /app/scripts
RUN uv pip install --system -e ".[dev]"

