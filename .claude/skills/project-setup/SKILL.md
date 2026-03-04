---
name: project-setup
description: Bootstrap a new Python project with SPECS.md, CLAUDE.md, MASTER_PLAN.md, test infrastructure, and git. Sets up test-first workflow from day one.
argument-hint: [project-name] [short-description]
disable-model-invocation: true
---

# /project-setup — New Project Bootstrap

Create a complete Python project skeleton with test-first infrastructure.

**Project name:** `$0`
**Description:** `$1`

---

## What You Create

Generate the following files in the CURRENT working directory. Do NOT create a subdirectory — the user has already `cd`'d into the project root.

### 1. `SPECS.md` — Product Specification

The product contract. Humans write this, agents read it. Create a skeleton that the user fills in:

```markdown
# {Project Name} — Product Specification

## §1 Purpose & Philosophy
<!-- What problem does this solve? What are the core design principles? -->

## §2 Scope & Phasing
<!-- What's in v1? What's deferred? -->

## §3 Architecture
<!-- High-level components, data flow, tech stack -->

## §4 Data Model
<!-- Core entities, their fields, relationships -->

## §5 Core Workflow
<!-- Main user workflows, step by step -->

## §6 API & Interfaces
<!-- External APIs, CLI commands, UI pages -->

## §7 Security & Constraints
<!-- Auth, rate limits, input validation, non-functional requirements -->

## §8 Glossary
<!-- Domain terms and their definitions -->

## §9 Definition of Done
<!-- Acceptance criteria checklist for v1 -->
```

### 2. `CLAUDE.md` — Agent Instructions

Rules for any AI agent working on this project:

```markdown
# {Project Name} — Claude Context

## AGENT INSTRUCTIONS (READ FIRST)

**Before starting ANY work:**
1. Read this entire file
2. Read `SPECS.md` — the product contract. Never deviate without user approval.
3. Read `Plan/MASTER_PLAN.md` — check current phase status
4. Skip completed phases (marked with checkmarks)

**Before starting ANY phase:**
- Note the start time (for duration tracking)
- Run `/write-tests` to create tests BEFORE writing implementation code

**Before finishing ANY phase:**
1. All tests from `/write-tests` must pass
2. Mark phase complete in MASTER_PLAN.md with timestamp
3. Commit changes

**NEVER DO:**
- NEVER read `.env` files (they contain secrets)
- NEVER modify SPECS.md (human-only)
- NEVER deviate from SPECS.md without explicit user approval
- NEVER skip test gates
- NEVER write implementation before tests exist

**ALWAYS DO:**
- CHECK SPECS.md before starting any work
- Write tests FIRST using `/write-tests`
- Update MASTER_PLAN.md before and after each phase
- Mock only external boundaries (LLM, network, filesystem) in tests

## Running Tests

\`\`\`bash
# During development: targeted tests
pytest tests/unit/test_foo.py -v

# Before commit: full suite
pytest tests/ -v

# By phase marker
pytest tests/ -m "phase1"
\`\`\`

## Project Layout

\`\`\`
src/                 # Application code
tests/
├── unit/            # Fast, no external calls
├── integration/     # DB, may mock LLM
└── conftest.py      # Shared fixtures
Plan/
├── MASTER_PLAN.md   # Phase tracking
SPECS.md             # Product spec (READ-ONLY)
CLAUDE.md            # This file
\`\`\`
```

### 3. `Plan/MASTER_PLAN.md` — Phase Tracking

```markdown
# {Project Name} — Master Plan

## Phase Status Summary

| Phase | Name | Status | Tests | Completed | Est. Duration | Actual Duration |
|-------|------|--------|-------|-----------|---------------|-----------------|

**Status Legend:** Pending | In Progress | Complete | Blocked

---

## Phase Details

<!-- Use /phase-planning to add phases here -->

---

## Changelog

| Date | Phase | Action | Notes |
|------|-------|--------|-------|
```

### 4. `tests/conftest.py` — Test Infrastructure

```python
"""Shared test fixtures.

Available fixtures:
- db_engine: Fresh in-memory SQLite with StaticPool
- db_session: Session bound to in-memory engine
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def db_engine():
    """Fresh in-memory SQLite.

    StaticPool ensures the same connection is reused across
    the test — mandatory for in-memory SQLite where each
    connection gets its own empty database.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    # TODO: Call your init_database(engine) here once models exist
    return engine


@pytest.fixture
def db_session(db_engine):
    """Session bound to the in-memory database."""
    Session = sessionmaker(bind=db_engine)
    session = Session()
    yield session
    session.close()
```

### 5. `tests/__init__.py` — Empty

### 6. `src/__init__.py` — Empty

### 7. `pyproject.toml` — Project Config

```toml
[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.backends._legacy:_Backend"

[project]
name = "{project-name-kebab}"
version = "0.1.0"
description = "{description}"
requires-python = ">=3.11"
dependencies = [
    "sqlalchemy>=2.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4",
    "pytest-cov>=4.1",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "phase1: Phase 1 tests",
    "phase2: Phase 2 tests",
    "phase3: Phase 3 tests",
]
```

### 8. `.gitignore`

```
# Python
__pycache__/
*.py[cod]
*.egg-info/
dist/
build/
.eggs/

# Environment
.env
.env.*
.venv/
venv/

# Data
data/

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db

# Coverage
htmlcov/
.coverage
```

---

## After Creating Files

1. Create directories: `mkdir -p src tests/unit tests/integration Plan`
2. Write all files listed above
3. Initialize git: `git init`
4. Stage and commit: `git add -A && git commit -m "Initial project setup with test-first infrastructure"`
5. Tell the user what was created and suggest next steps:
   - "Fill in SPECS.md with your product requirements"
   - "Run `/phase-planning` to plan your first phase"
   - "Run `/write-tests` before writing any code"
