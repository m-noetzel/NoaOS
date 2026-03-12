# Private Worker container — Ollama + Memory/RAG
# SPEC.md §8.1: Sealed enclave, no internet, no shell
# Network: noa-internal only (internal: true)

FROM python:3.11-slim AS base

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
RUN groupadd -r noa && useradd -r -g noa -s /sbin/nologin noa

WORKDIR /app

COPY pyproject.toml ./
COPY src/ ./src/

RUN pip install --no-cache-dir ".[api]" && rm -rf /root/.cache

USER noa

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=60s \
    CMD curl -f http://localhost:8001/health || exit 1

CMD ["uvicorn", "noa.private_worker.app:create_private_app", "--host", "0.0.0.0", "--port", "8001", "--factory"]
