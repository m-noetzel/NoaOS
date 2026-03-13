# External Worker container — LLM APIs + Tool integrations + Coding
# SPEC.md §8.2: Sandboxed, allowlisted egress only
# Network: noa-external only

FROM python:3.11-slim AS base

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
RUN groupadd -r noa && useradd -r -g noa -s /sbin/nologin noa

WORKDIR /app

COPY pyproject.toml ./
COPY src/ ./src/

RUN pip install --no-cache-dir ".[api]" && rm -rf /root/.cache

USER noa

EXPOSE 8002

HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=60s \
    CMD curl -f http://localhost:8002/health || exit 1

CMD ["uvicorn", "noa.external_worker.app:create_external_app", "--host", "0.0.0.0", "--port", "8002", "--factory"]
