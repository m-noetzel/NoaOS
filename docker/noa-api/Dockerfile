# Noa API container — FastAPI + LangGraph Orchestrator
# Bridges noa-internal and noa-external networks (§7.1)

FROM python:3.11-slim AS base

RUN groupadd -r noa && useradd -r -g noa -s /sbin/nologin noa

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir . && rm -rf /root/.cache

COPY src/ ./src/

USER noa

EXPOSE 8000

CMD ["uvicorn", "noa.api.app:create_app", "--host", "0.0.0.0", "--port", "8000", "--factory"]
