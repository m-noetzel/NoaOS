# Noa API container — FastAPI + LangGraph Orchestrator
# Bridges noa-internal and noa-external networks (§7.1)

FROM python:3.11-slim AS base

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
RUN groupadd -r noa && useradd -r -g noa -s /sbin/nologin noa

WORKDIR /app

COPY pyproject.toml ./
COPY src/ ./src/
COPY alembic.ini ./
COPY alembic/ ./alembic/

RUN pip install --no-cache-dir -e ".[api,orchestrator]" && rm -rf /root/.cache

USER noa

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --retries=5 --start-period=30s \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "noa.api.app:create_app", "--host", "0.0.0.0", "--port", "8000", "--factory"]
