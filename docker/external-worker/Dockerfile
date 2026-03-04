# External Worker container — LLM APIs + Tool integrations + Coding
# SPEC.md §8.2: Sandboxed, allowlisted egress only
# Network: noa-external only

FROM python:3.11-slim AS base

RUN groupadd -r noa && useradd -r -g noa -s /sbin/nologin noa

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir . && rm -rf /root/.cache

COPY src/ ./src/

USER noa

EXPOSE 8002

CMD ["uvicorn", "noa.workers.external:app", "--host", "0.0.0.0", "--port", "8002"]
