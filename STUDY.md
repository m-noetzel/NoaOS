# Learning Roadmap — NoaOS Tech Stack

Use NoaOS as a hands-on playground to learn the frameworks and techniques it's built on.

---

## Tier 1: Foundations (Learn These First)

### 1. Python Async Programming

- The entire codebase is `async/await`-based. Understanding this unlocks everything else.
- Study: `src/noa/api/app.py` (lifespan), `src/noa/db/` (async sessions)
- Practice: Write a simple async function, understand `asyncio.gather`, event loops
- Resource: Python docs on `asyncio`

### 2. Docker & Docker Compose

- This is the project's **core isolation mechanism** — private vs external domain
- Study: `Dockerfile.dev`, `docker-compose.yml`, `docker-compose.dev.yml`
- Key concepts: networks (`internal: true`), volumes, multi-container apps, build stages
- Practice: Run `docker compose up`, inspect networks with `docker network ls`, `docker exec` into containers
- Learn: `docker build`, layer caching, `docker compose logs -f`

### 3. Bash / Shell Essentials

- Used everywhere: Dockerfile `RUN` commands, CI gates, test scripts, git workflow
- Key commands to master: `grep`, `find`, `curl`, `jq`, pipes (`|`), exit codes, `set -e`
- Practice: Read the Makefile, understand `ruff check && mypy src/ && pytest` chains
- Study: The shell hooks, git workflow commands in CLAUDE.md

---

## Tier 2: Core Frameworks (The Main Stack)

### 4. FastAPI

- The entire API layer. Async-native web framework.
- Study: `src/noa/api/app.py` (app factory), `src/noa/api/v1/auth.py` (endpoints)
- Key concepts: dependency injection (`Depends`), middleware, lifespan events, Pydantic request/response models
- Practice: Add a simple endpoint, hit it with `curl` or `httpx`

### 5. SQLAlchemy 2.0 + Alembic

- The database ORM and migration system
- Study: `src/noa/db/models/` (ORM models), `alembic/` (migrations)
- Key concepts: declarative models, async sessions, `select()` query API, migration up/down
- Practice: Read a model like `user.py`, trace how it maps to SQL. Run `alembic history`

### 6. Pydantic

- Used at **every boundary**: API schemas, settings, RPC contracts
- Study: `src/noa/settings/models.py`, `src/noa/api/schemas/`
- Key concepts: `BaseModel`, validators, `model_dump()`, `pydantic-settings` for env vars
- Practice: Modify a schema, see what validation errors look like

---

## Tier 3: AI & Orchestration (The Unique Part)

### 7. LangGraph

- The AI orchestrator — the brain of Noa
- Study: `src/noa/orchestrator/graph.py` (state machine), `src/noa/orchestrator/state.py`, `src/noa/orchestrator/nodes/`
- Key concepts: `StateGraph`, nodes, edges, conditional routing, `AgentState` TypedDict
- This is the hardest part — understand the flow: `router -> agent -> tools -> responder`
- Practice: Trace a request through the graph. Draw it on paper.

### 8. LangChain Core

- Used under LangGraph for message types, tool abstractions
- Key concepts: `HumanMessage`/`AIMessage`, tool schemas, prompt templates
- Study alongside LangGraph — don't learn LangChain separately

---

## Tier 4: Supporting Skills

### 9. pytest (Testing)

- Study: `tests/unit/`, `tests/conftest.py`
- Key concepts: fixtures, markers (`-m f1`), `pytest-asyncio`, mocking
- Practice: Run `pytest -m f1 -v`, read what each test asserts

### 10. Security Patterns

- JWT auth flow: `src/noa/auth/jwt.py`, `src/noa/auth/middleware.py`
- Password hashing: bcrypt in `src/noa/auth/password.py`
- Audit hash chain: `src/noa/audit/service.py`
- Container hardening: read-only FS, dropped capabilities, non-root user

### 11. Code Quality Tools

- `ruff` (linter/formatter), `mypy` (type checker)
- Practice: Introduce a type error, see mypy catch it. Write a bare `except:`, see ruff flag it.

---

## Suggested Learning Order

```
Week 1-2:  Python async + Bash basics + Docker fundamentals
Week 3-4:  FastAPI + Pydantic (build/modify endpoints)
Week 5-6:  SQLAlchemy + Alembic (understand the data layer)
Week 7-8:  LangGraph + LangChain Core (the AI pipeline)
Ongoing:   pytest, security, ruff/mypy (learn by doing)
```

---

## How to Practice With NoaOS

| Goal | Action |
|------|--------|
| Understand Docker networking | `docker network inspect noa-internal` — see which containers are attached |
| Understand the API | `pytest -m f3 -v` — run the FastAPI tests, read what they test |
| Understand LangGraph | Read `src/noa/orchestrator/graph.py` top to bottom, then each node file |
| Understand auth | Read `tests/unit/test_mr1_auth.py` — tests tell the story |
| Understand DB models | Pick any model in `src/noa/db/models/`, trace it to its migration |
