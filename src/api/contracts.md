# Noa API Contracts

## Pricing Model

```
GET /api/v1/pricing

Response:
{
  "data": [
    { "provider": "anthropic", "model": "claude-3.5-sonnet", "input_price_per_m": 3.0, "output_price_per_m": 15.0 },
    { "provider": "openai", "model": "gpt-4o", "input_price_per_m": 5.0, "output_price_per_m": 15.0 },
    { "provider": "ollama", "model": "llama-3.1-70b", "input_price_per_m": 0, "output_price_per_m": 0 }
  ]
}
```

## Run with Steps

```
GET /api/v1/runs/{run_id}

Response:
{
  "data": {
    "id": "r1",
    "model": "claude-3.5-sonnet",
    "provider": "anthropic",
    "tokens_in": 1550,
    "tokens_out": 3470,
    "cost_usd": 0.0565,          // MUST equal sum(steps[].cost)
    "status": "completed",
    "status_history": [
      { "status": "queued", "timestamp": "...", "reason": null },
      { "status": "running", "timestamp": "..." },
      { "status": "completed", "timestamp": "..." }
    ],
    "steps": [
      { "step_id": "s1", "name": "Planner", "tokens_in": 80, "tokens_out": 120, "cost": 0.002, "duration_ms": 1200 },
      { "step_id": "s2", "name": "web_search", "tokens_in": 120, "tokens_out": 30, "cost": 0.0009, "duration_ms": 2100 }
    ],
    "replay_of": null
  }
}
```

### Cost Invariant

```
run.cost_usd == sum(run.steps[i].cost)
step.cost == step.tokens_in * pricing.input_price_per_m / 1_000_000
           + step.tokens_out * pricing.output_price_per_m / 1_000_000
```

## Replay

```
POST /api/v1/runs/{run_id}/replay
Body: { "from_node": "s2", "mode": "downstream" }

Modes:
- "full"       → re-execute entire run
- "downstream" → reuse cached outputs before from_node, re-execute from from_node onward
- "tool_only"  → re-execute only the specified tool node

Response:
{
  "data": {
    "id": "r6",
    "replay_of": { "original_run_id": "r1", "from_node": "s2", "mode": "downstream" },
    ...
  }
}
```

### Caching Policy

- For "downstream" mode, the backend persists step outputs/artifacts with stable `step_id`s
- Prior step outputs are loaded from cache
- A new `run_id` is always created for replays

## Run Status State Machine

```
queued → running → completed
                 → failed
                 → cancelled
       → running → waiting_for_approval → running → completed/failed
```

### Lifecycle Events (SSE)

- `run_started`
- `run_waiting_for_approval`
- `run_completed`
- `run_failed`
- `run_cancelled`

## Approvals

```
GET /api/v1/approvals/pending

Response item:
{
  "id": "a1",
  "run_id": "r3",
  "node_id": "n1",
  "risk_tier": "high",
  "tool_name": "db_migrate",
  "tool_args": { "migration": "add_role_column", "target": "production" },
  "preview_text": "Execute database migration on production server",
  "status": "pending",
  "created_at": "...",
  "decided_at": null,
  "decided_by": null
}

POST /api/v1/approvals/{id}/approve
POST /api/v1/approvals/{id}/deny

Response: { "success": true }
```

## Planner Event Payload

```json
{
  "type": "planner_step",
  "data": {
    "step": "Planning request",
    "description": "...",
    "strategy_summary": "Search multiple sources in parallel, then synthesize.",
    "selected_tools": ["web_search", "arxiv_search"],
    "parallel_groups": [
      { "group_id": "search", "tools": ["web_search", "arxiv_search"] }
    ],
    "tokens_in": 80,
    "tokens_out": 120,
    "duration_ms": 1200
  }
}
```
