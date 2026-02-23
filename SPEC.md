# SPEC.md
## Noa — Personal Agent for Decision & Execution
### Version: 1.1
### Date: 2026-02-23

---

# 1. Purpose

Noa is a **secure, dual-domain personal AI agent** running on macOS. Noa owns the decision layer — it interprets intent, routes tasks, enforces policy, and orchestrates execution across two strictly isolated domains:

- A **Private Domain** (local-only, no external LLM access)
- An **External Domain** (Claude Code container with internet access)

Noa operates through:

- A **LangGraph-based Orchestrator** as the deterministic control plane
- A secure mobile approval interface
- Strict cost, security, and policy enforcement

The system must provide:

- Local private task management using only local models
- Controlled external coding workflows using Claude Code
- Explicit data boundary enforcement
- Auditable, policy-driven execution
- Deterministic cost control

---

# 2. Agent Identity

**Noa** is the user-facing agent. All interactions — mobile, CLI, or API — are mediated through Noa. Noa is not a wrapper around a single model; it is the orchestration identity that decides *which* model, *which* domain, and *which* policy applies to every request.

Key principles:

- Noa **decides**, workers **execute**
- Noa never exposes internal routing to the user
- Noa presents a single coherent agent persona regardless of which backend fulfilled the task
- Noa owns the conversation state, task history, and approval context

---

# 3. Core Design Principles

## 3.1 Separation of Concerns

| Component | Responsibility |
|---|---|
| Noa (LangGraph Orchestrator) | Decision authority, routing, policy enforcement |
| Private Domain | Local-only AI + private data processing |
| Claude Code Worker | Coding execution + testing |
| Policy Engine | Authorization + routing rules |
| Mobile App | Approvals + monitoring |

Claude Code is a **tool** that Noa invokes. It is not an orchestrator.

---

## 3.2 Dual-Domain Architecture

### Domain A: Private (Local-Only)

**Hard requirements:**

- No external LLM calls
- No internet egress to LLM providers
- All inference via local model runtime (Ollama or equivalent)
- Private data never enters external container

Capabilities:

- Todo management
- Note processing
- Local semantic search
- Planning & summarization
- Local RAG

### Domain B: External (Claude Code)

Allowed:

- Internet access
- Access to coding repositories
- Running tests and CI commands
- Generating patches and diffs

Not allowed:

- Access to private todo database
- Access to private data volumes
- Unrestricted filesystem access

---

# 4. System Architecture

```
User (iPhone / CLI)
       ↓
   Noa Control Plane API (Mac Mini)
       ↓
   Noa Orchestrator (LangGraph)
       ├── Private Worker (Local Container/VM)
       └── Claude Code Worker (Internet Container)
```

---

# 5. Container Architecture

## 5.1 Private Container

### Must:

- Run local LLM runtime (Ollama or equivalent)
- Bind only to localhost or LAN
- Have internet egress blocked or strictly allowlisted
- Use dedicated encrypted volume
- Store private todo database
- Store embeddings locally

### May:

- Use CPU and RAM flexibly
- Use GPU acceleration if supported securely

### Must NOT:

- Reach api.anthropic.com
- Reach OpenAI endpoints
- Reach any external LLM provider
- Mount external container volumes

---

## 5.2 Claude Code Container

### Must:

- Have internet access
- Be sandboxed (Docker or VM)
- Have limited filesystem mounts
- Enforce workspace root path
- Produce structured outputs

### Must NOT:

- Mount private data volume
- Modify system files outside workspace
- Access secrets beyond scoped credentials

---

# 6. Coding Task Contract

Every coding task Noa dispatches must follow this schema:

```json
{
  "repo": "string",
  "base_commit": "sha",
  "objective": "string",
  "constraints": {
    "language": "string",
    "style": "string",
    "performance": "string"
  },
  "acceptance_criteria": ["list"],
  "test_command": "string",
  "risk_tier": "low|medium|high",
  "max_iterations": 3
}
```

### Required Output From Claude Code Worker

- Git diff / patch
- Test output (raw logs + exit code)
- Lint/typecheck results
- Dependency diff (if applicable)
- Structured JSON summary:

```json
{
  "status": "success|failure",
  "files_modified": [],
  "tests_passed": true,
  "summary": "short description"
}
```

---

# 7. Privacy Routing Rules

All tasks Noa processes must include:

```json
{
  "privacy_mode": "local_only | cloud_ok"
}
```

### Routing Logic

- `local_only` → Private container only
- `cloud_ok` → Claude Code allowed

Private-tagged content must never be sent to external domain.

### Hard Enforcement

- Policy engine blocks invalid routing
- Network layer blocks accidental egress
- Logs record all routing decisions

---

# 8. Policy & Approval Framework

## Risk Tiers

### Low

- Local summarization
- Draft generation
- Read-only queries

### Medium

- Sending email
- Creating calendar events
- Non-critical repo modifications

### High

- Dependency changes
- System file modification
- Financial transactions
- Merging to main branch

## Approval Rules

| Risk Tier | Requires Mobile Approval |
|---|---|
| Low | No |
| Medium | Yes |
| High | Yes + Step-up Auth |

### Step-up Auth

- Biometric confirmation
- Re-authentication
- Device binding verification

---

# 9. Cost Control

## Global Controls

- Monthly token cap
- Daily token cap
- Per-task token limit
- Max iterations per coding task
- Max tool calls per workflow

## Model Routing

Noa uses the cheapest sufficient model:

- Use local model when possible
- Escalate to Claude only when:
  - Coding complexity exceeds local model threshold
  - Local model fails verification

---

# 10. Security Controls

## Required

- VPN-only remote access
- No port forwarding
- Encrypted volumes
- Audit logging for all tool invocations
- Secrets manager (scoped credentials)
- Separate Docker networks per domain

## Strongly Recommended

- VM for private domain if strict privacy required
- Daily automated egress test for private container
- Dependency scanning in coding workflow
- Immutable audit log

---

# 11. Logging & Observability

Every tool invocation Noa triggers must log:

- Timestamp
- User ID
- Device ID
- Domain used
- Token usage
- Cost estimate
- Side effects

Private logs must never leave the local machine.

---

# 12. Resource Management

## Private Domain

- Prefer high RAM allocation
- Avoid swap usage
- Allow CPU burst
- Ensure no starvation from Claude container

## External Domain

- Apply CPU/RAM caps
- Prevent runaway loops
- Limit max concurrent jobs

---

# 13. Failure Handling

## Private Domain Failure

- Fail closed
- Do not fallback to external LLM
- Notify user via Noa

## Claude Code Failure

- Retry up to `max_iterations`
- Escalate to manual review
- Do not auto-merge failed patch

---

# 14. Non-Goals

Noa does **not**:

- Allow uncontrolled agent autonomy
- Allow cross-domain implicit data transfer
- Permit skill marketplace plugins
- Permit direct shell execution without sandbox

---

# 15. Testing Requirements

Before deployment:

- Validate privacy routing
- Validate egress block on private container
- Run simulated malicious prompt injection
- Verify no private data appears in Claude Code logs
- Stress test coding iteration caps

---

# 16. Future Extensions

- CI integration for PR validation
- Encrypted remote backup for private domain
- Advanced anomaly detection on tool calls
- Automatic red-team simulations
- Model fallback strategies

---

# 17. Definition of Done

The system is complete when:

- Private tasks are processed locally only
- Claude Code executes coding tasks in sandbox
- No cross-domain leakage occurs
- Cost limits are enforced
- All actions are auditable
- Mobile approval works with risk tiers
- Network isolation verified

---

# 18. Architectural Philosophy

Noa embodies:

- **Deterministic orchestration** — no probabilistic routing
- **Strict domain isolation** — privacy enforced at network level
- **Explicit approval governance** — risk-tiered human-in-the-loop
- **Modular extensibility** — workers are pluggable
- **Defense in depth** — layered security at every boundary
- **Replaceable model backends** — no vendor lock-in

```
Noa decides.
Workers execute.
Privacy is enforced at network level.
Cost is enforced at policy level.
Execution is sandboxed.
```

End of Specification.
