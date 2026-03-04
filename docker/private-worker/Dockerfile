# Private Worker container — Ollama + Memory/RAG
# SPEC.md §8.1: Sealed enclave, no internet, no shell
# Network: noa-internal only (internal: true)

FROM python:3.11-slim AS base

RUN groupadd -r noa && useradd -r -g noa -s /sbin/nologin noa

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir . && rm -rf /root/.cache

COPY src/ ./src/

USER noa

EXPOSE 8001

CMD ["uvicorn", "noa.workers.private:app", "--host", "0.0.0.0", "--port", "8001"]
