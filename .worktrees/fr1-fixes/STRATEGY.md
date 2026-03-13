# STRATEGY.md
## Noa + TheCoach — Unified Strategy & System Design Alignment
### Version: 1.1
### Date: 2026-02-24

---

# 1. Executive Summary

## Core Strategy

We are building a **two-layer system**:

- **TheCoach** → A vertical, domain-specific decision engine for endurance training.
- **Noa** → A governed orchestration layer that coordinates tools, enforces policy, and composes cross-domain decisions.

They are separate products with different target audiences, but architected to integrate cleanly.

> TheCoach optimizes training decisions.
> Noa optimizes life decisions.
> Noa can call TheCoach as a tool.
> TheCoach must work independently of Noa.

---

# 2. Strategic Positioning

## 2.1 TheCoach (Vertical Product)

**Category:** A decision engine that helps you think like a great coach
**Target:** Serious endurance athletes (triathlon, cycling, running)
**Primary loop:** Evaluate → What-if → Insight → Next action

### Differentiation

1. **Learning Artifact** (core identity)
   - Cumulative athletic knowledge profile built from every training block
   - Structured conclusions about the athlete: what works, what fails, what adapts
   - Shareable cards, exportable personal athletic model
   - History across seasons — switching cost that no competitor offers
   - *"The only system that tells you what you've learned about yourself."*

2. **Evaluation Ritual** (retention driver)
   - Post-session: push notification → 15-second feedback → evaluation summary
   - Updated weekly impact preview after each evaluation
   - Daily habit → retention → revenue
   - This is *the* product loop, not a feature

3. **Subjective Input** (coaching intuition)
   - Perceived effort: easier / as expected / harder
   - Energy: low / medium / high
   - Moves from load math (commodity) to coaching intuition (differentiation)
   - Two fields, massive signal gain, low implementation cost

4. **Deterministic State Models**
   - Capacity, freshness, adherence — transparent, evidence-backed
   - No black-box plan mutation

5. **What-if Simulation Engine**
   - Decision support before action

6. **Experiment-based Learning Blocks**
   - Structured hypothesis → protocol → conclusion

7. **Evidence + Confidence Contract**
   - Every recommendation shows sources, confidence level, data completeness

### Strategic Goal

Achieve product-market fit and market share in the serious endurance niche.

> TheCoach is the growth engine.

### Competitive Landscape

| Capability | TheCoach | TrainingPeaks | Intervals.icu | AI Plan Generators (EndurCo, Humango) |
|------------|----------|---------------|---------------|---------------------------------------|
| **Plan generation** | No (not the product) | Yes (coach-authored) | No (analytics only) | Yes (core feature) |
| **Session evaluation** | Yes — push → 15s feedback → summary | Manual (coach notes) | Manual (notes field) | Limited / post-hoc |
| **Subjective input** | Yes — perceived effort + energy | No | No | Rarely |
| **What-if simulation** | Yes — before you act | No | No | No |
| **Learning artifacts** | Yes — cumulative across seasons | No | No | No |
| **Evidence + confidence** | Yes — every recommendation sourced | No | Partial (charts) | No (black box) |
| **Experiment blocks** | Yes — hypothesis → protocol → conclusion | No | No | No |
| **Switching cost** | High (learning artifact history) | Medium (plan library) | Low (data is importable) | Low (plans are generic) |
| **Pricing** | Free tier + paid | $120/yr or coach fee | Free / donation | $10–30/month |

**Key takeaway:** No competitor combines evaluation ritual + what-if + learning artifacts. Plan generators compete on a commodity axis (generate plans). TheCoach competes on a differentiation axis (understand yourself as an athlete).

> The competitive gap is not feature count — it is the feedback loop that builds cumulative knowledge.

---

## 2.2 Noa (Platform Product)

**Category:** Governed personal AI agent
**Target:** Technical owner-operators / power users
**Primary loop:** Interpret → Route → Govern → Execute

### Differentiation

- Deterministic outer shell (LangGraph orchestration)
- Strict domain isolation (private vs external) — container-based initially, physical machine isolation as upgrade
- API-first architecture with unified Run/Event model
- Approval-based side effects
- Tool governance + cost control
- Full auditability

### Strategic Goal

Serve as a privacy-first orchestration platform and high-trust decision layer.

> Noa is the orchestration platform, not the growth wedge.

### Growth Model

Noa's governance core is stable. The tool surface grows incrementally.
New tools are added over time — TheCoach is the first domain-specific tool, not the last.
The backbone must be robust enough to support future tools without rewrites.

### MVP Tool Surface

Noa ships with native tools for personal productivity orchestration:

| Tool | Domain | Strategic Role |
|------|--------|----------------|
| Google Calendar | External | Schedule awareness, event creation/management |
| Gmail | External | Communication orchestration (search, read, send, draft) |
| Notion | External | Knowledge base and project management |
| Web Search (Tavily) | External | Real-time information retrieval |
| Memory | Private | Long-term fact storage + semantic recall |
| RAG | Private | Personal document ingestion + question answering |
| Coding Worker | External | Git repos, test execution, diff generation |

> 5 tools, 14 functions at MVP. TheCoach is the first domain-specific tool added to this registry.

### Platform Capabilities

| Capability | Strategic Purpose |
|------------|-------------------|
| Multi-model routing | Ollama (local/free), Anthropic, OpenAI — cheapest sufficient model per task |
| Privacy routing | Automatic classification; fail-safe to private on low confidence |
| Risk-tiered approvals | Low (auto), Medium (preview), High (mobile + step-up auth) |
| Dual-domain execution | Private enclave + external domain (container-isolated Phase 1, physically isolated Phase 2) |
| Coding sandbox | Containerized shell execution, workspace-scoped, resource-capped |
| Cost control | Per-task, daily, monthly token caps — hard limits, not guidelines |
| Immutable audit log | Hash-chain integrity, full traceability of every action |
| Durable task queue | Private tasks queue when MacBook Pro is unavailable, drains on wake |
| Conversation memory | Per-thread short-term memory via LangGraph checkpointer |
| Long-term memory | User-controlled fact store with auto-extraction guardrails and audit UI |

### Future Tool Expansion

Post-MVP tools under consideration:

- Slack
- GitHub Issues
- Jira
- File management
- Voice interface
- CI integration for PR validation

Domain-specific tools (like TheCoach) are added via the versioned tool contract (Section 6).
Generic productivity tools are added natively to the orchestration layer.

---

# 3. Relationship Between Projects

## 3.1 Architectural Relationship

TheCoach is one tool in Noa's growing tool registry. Additional domain tools will be added over time.

```
User → Noa (orchestrator) → TheCoach (training engine)
                           → [future tools]
```

Noa:
- Owns conversation state
- Routes intent
- Enforces approval policies
- Logs audit trail
- Manages tool registry

TheCoach:
- Owns training domain logic
- Maintains athlete state
- Computes evaluations, simulations, insights
- Returns structured responses

Domain tools must never depend on Noa.

Noa may depend on domain tools.

> Dependency direction is strictly one-way. Every tool is independently viable.

---

## 3.2 Design Invariants

1. TheCoach must be fully functional without Noa.
2. Noa must treat TheCoach as a versioned external tool.
3. No duplication of domain intelligence in Noa.
4. No duplication of orchestration logic in TheCoach.
5. All write actions use propose → preview → approve → apply.
6. All responses include confidence + evidence references.

---

# 4. Product Packaging Strategy

## 4.1 TheCoach Distribution Model

**Cloud-first for mainstream adoption.**

- Hosted backend (managed DB + queue)
- Mobile app (primary interface)
- Web dashboard
- Intervals.icu integration as wedge

Optional:
- Local-only mode (advanced users)

> Market share requires cloud delivery and mobile UX.

### Phase 1 Scope Constraint

For the first 100 users, ship only what drives daily usage:
- Evaluation ritual (core loop)
- What-if simulation
- Insights
- Clear dashboard

Do NOT ship yet:
- Multi-platform sync (Garmin, Strava)
- Full robustness model
- Experiment evaluation statistics
- Perfect freshness modeling

This cut list applies to *user-facing features*, not infrastructure quality.
Backend robustness and clean architecture are retained — they enable velocity, not vanity.

---

## 4.2 Noa Distribution Model

**Local-first orchestration platform.**

- Single-machine start with container-based domain isolation (scales to dual-machine physical isolation)
- API-first architecture with Postgres, OpenAPI, and unified Run/Event model
- Privacy-first architecture
- Advanced multi-tool orchestration
- Web + Mobile clients (PWA initially, native iOS later)

Noa integrates TheCoach via API token.

> Noa enhances value but is not required for TheCoach adoption.

---

# 5. Strategic Moats

## 5.1 TheCoach Moats

1. **Daily Evaluation Loop**
   - "How was my session?"
   - High-frequency habit driver

2. **What-if Simulation Engine**
   - Decision support before action

3. **Learning Artifacts**
   - Block-level conclusions about the athlete
   - Long-term personal athletic knowledge base

4. **Evidence + Confidence Contract**
   - Every recommendation shows:
     - Evidence sources
     - Confidence level
     - Data completeness

> Trust is the moat.

### Emotional Retention Layer

Functional moats retain users rationally. Emotional moats retain users viscerally. TheCoach needs both.

**How does it feel to use daily?**

- Post-session evaluation should feel like *closing a loop*, not filling a form. The athlete finishes a session, gets a push notification, taps twice, and sees an immediate reflection of what that session meant. The feeling: "I've been seen."
- The weekly impact preview should feel like *progress made visible*. Not a dashboard of charts — a narrative: "This week moved your threshold estimate up. Your fatigue is clearing faster than last block."

**What identity does it reinforce?**

- TheCoach reinforces the identity of *the self-aware athlete* — someone who doesn't just train hard, but trains smart and understands why.
- The learning artifact is a mirror: "Here is what you've learned about yourself across 3 years of training." No other tool does this. The athlete becomes someone with a documented athletic self-knowledge base.
- The target emotion on every interaction: *"I understand myself better now."*

**What story does it tell the athlete?**

- Not "I followed the plan." → That's compliance.
- Not "The AI told me what to do." → That's dependency.
- Instead: *"I made a better decision because I understood the trade-off."*
- TheCoach is the tool that makes the athlete the protagonist of their own coaching narrative.

**Design implications:**

- Evaluation summaries must use the athlete's own language and context, not generic metrics
- Insights must reference prior blocks ("Last time you tapered this way, you peaked 4 days later")
- Learning artifact cards must be sharable — athletes want to tell their story to peers and coaches
- Tone: respectful, concise, never patronizing. Think trusted advisor, not motivational app.

> The moat is not the feature set. The moat is the feeling: *"This knows me."*

---

## 5.2 Noa Moats

1. Governed execution (deterministic orchestration)
2. Domain isolation (container-based → physical)
3. Strict policy enforcement
4. Full audit trail
5. Modular tool architecture
6. API-first with unified Run/Event model

> Governance + safety is the moat.

---

## 5.3 Distribution Strategy

### Community Wedge: Intervals.icu

- Public build-in-public thread in Intervals.icu forum
- Weekly insight screenshots showing real training conclusions
- Transparent learning artifact examples
- Beta cohort with feedback loops

> First 200 users come from here.

### Positioning

Do not sell "AI plan generator."

Sell: *"A decision engine that helps you think like a great coach."*

The difference: plan generators are commodities. Decision engines build trust.

### Distribution Model & Funnel Math

**Funnel assumptions (Intervals.icu wedge):**

| Stage | Metric | Assumption |
|-------|--------|------------|
| Awareness | Forum thread views / month | ~2,000 (active forum, niche topic) |
| Interest | Click-through to landing page | 10–15% → 200–300 visits/month |
| Signup | Free tier conversion | 15–20% → 30–60 signups/month |
| Activation | Complete first evaluation | 50–60% of signups → 15–36 activated/month |
| Retention (D7) | Return after 7 days | Target > 40% of activated |

**Time-to-200 users:**

- Conservative (30 signups/month): ~7 months
- Moderate (45 signups/month): ~5 months
- With referral loop (1.2x organic): ~4 months

**Required traffic to hit 200 activated users in 6 months:**

- 200 activated ÷ 0.55 activation rate = ~364 signups needed
- 364 signups ÷ 0.17 conversion rate = ~2,140 landing page visits needed
- 2,140 visits ÷ 6 months = ~357 visits/month

**Referral multiplier assumption:** Each retained user shares 1 insight card per month. If 10% of recipients visit → +0.1x organic growth per retained user. This compounds slowly but meaningfully after month 3.

**Fallback channels if Intervals.icu underperforms:**

- Reddit r/triathlon, r/Velo, r/running (build-in-public posts, not ads)
- Strava clubs with engaged members
- Endurance coaching communities (TrainingPeaks forums, coaching certification groups)
- Direct outreach to 20–30 beta testers from personal network

> Distribution is the highest-risk assumption. Validate funnel by month 2. If landing page conversion < 10%, redesign positioning before scaling content.

---

## 5.4 Pricing Strategy

**Free tier:** Evaluation only, limited insights
**Paid tier:** Experiments + learning artifact + multi-platform intelligence

Price anchor: 1/5 of a real coach.

> Free tier proves the habit. Paid tier unlocks the moat.

---

# 6. Integration Model

## 6.1 TheCoach Tool Contract (v1)

Noa may call:

- `thecoach.get_dashboard`
- `thecoach.get_strengths`
- `thecoach.get_top_insights`
- `thecoach.evaluate_today_session`
- `thecoach.simulate_today_impact`
- `thecoach.propose_plan_change`
- `thecoach.apply_plan_change`

All tool responses must:

- Be schema-bound
- Include confidence
- Include evidence IDs
- Be size-limited

All write actions must:
- Return a proposal first
- Require explicit approval
- Log side effects

---

## 6.2 Auth Model

- TheCoach owns identity.
- Noa stores a scoped API token.
- Scopes:
  - read_training_data
  - evaluate_sessions
  - simulate
  - propose_plan_changes
  - apply_plan_changes

Noa cannot access raw training DB.

---

# 7. Strategic Priorities (Next 12 Months)

## 7.0 Focus Rule

At any given time, only one product receives feature expansion.
The other product receives maintenance and stability work only.

**Investment modes:**
- **TheCoach** = feature velocity (new capabilities, user-facing iteration)
- **Noa** = infrastructure stability + incremental tool additions

This is not a rigid percentage split. It is a discipline: do not fragment attention across two feature roadmaps simultaneously.

---

## Phase 1 — Prove TheCoach Retention

Ship:
- Intervals import
- Session evaluation (with push notification → 15-sec feedback → summary ritual)
- What-if simulation
- Capacity + freshness models
- 1–2 weekly insights
- Subjective input: perceived effort + energy (2 fields)

### Kill Metrics (evaluate before Phase 2)

| Metric | Threshold | Action if missed |
|--------|-----------|------------------|
| D7 retention | > 40% | Stop feature expansion, diagnose loop |
| Sessions evaluated | > 60% of completed sessions | Evaluation UX is broken — fix before adding |
| What-if weekly usage | > 50% of active users | Feature may not deliver value — reconsider |

### Pre-Commit Gate

**If D7 retention < 30%, the evaluation ritual is fundamentally broken.**

Action: Stop all feature work. Redesign the evaluation ritual from scratch before adding anything else. No exceptions. This is not a "diagnose and patch" scenario — it means the core loop does not create a habit, and no amount of additional features will compensate.

> Do not overbuild orchestration before retention is proven.

---

## Phase 2 — Strengthen Differentiation

Add:
- Learning artifacts (shareable cards, cumulative profile, exportable model)
- Cross-platform sync (Garmin, Strava)
- Improved freshness model

### Kill Metrics (evaluate before Phase 3)

| Metric | Threshold | Action if missed |
|--------|-----------|------------------|
| Learning artifact engagement | > 30% of users view/share | Artifact format needs redesign |
| D30 retention | > 25% | Core loop isn't sticky enough |

---

## Phase 3 — Ecosystem Expansion

- Integrate with Noa
- Cross-domain automation (calendar + training)
- Coach-market integrations (TrainingPeaks import)
- API exposure for partners

---

# 8. KPIs

## TheCoach KPIs (North Star)

1. Weekly Active Evaluation Rate
2. % Sessions Evaluated
3. What-if Usage Rate
4. Insight Acceptance / Follow-through Rate
5. D7 and D30 retention
6. Plan change approval rate

---

## Noa KPIs

1. Tool usage diversity
2. Approval success rate
3. Cost per session
4. Policy violation rate (target near zero)
5. Private routing accuracy

---

# 9. Technical Alignment Rules

## 9.1 Modular Boundaries

- TheCoach = API-first service
- Noa = Orchestration + policy
- Tool contracts versioned
- No shared database
- No cross-domain implicit data access

---

## 9.2 Determinism & Trust

- Deterministic domain models
- Deterministic orchestration
- LLMs only for bounded reasoning/explanation
- Never allow LLM to mutate state directly

---

## 9.3 Migration Readiness

TheCoach must be:

- Containerized
- Stateless API
- Managed DB compatible
- Cloud-deployable without rewrite

Noa must remain:

- Local-first
- Governed
- Domain-isolated (container-based initially, machine-isolated in Phase 2)

---

# 10. Risk Register

## 10.1 Over-Engineering

Risk:
Building platform complexity before retention is proven.

Mitigation:
Focus on TheCoach daily loop first.

---

## 10.2 Dual-Brain Confusion

Risk:
Two competing agent layers.

Mitigation:
Noa orchestrates.
TheCoach computes domain truth.

---

## 10.3 Distribution Constraint

Risk:
Local-only architecture limits growth.

Mitigation:
Cloud-first TheCoach.

---

## 10.4 Distribution Gap

Risk:
Architecture quality is ahead of market proof. Distribution and retention are untested.
The system could be 9/10 technically and 0/10 in proven daily usage.

Mitigation:
Phase 1 kill metrics gate all further investment.
Do not add Phase 2 features until retention thresholds are met.
Prioritize community presence (Intervals.icu) and build-in-public from day one.

---

# 11. Long-Term Vision

## 11.1 TheCoach

Become the trusted AI training intelligence layer for serious endurance athletes.

- Daily coach
- Evidence-backed
- Transparent
- Adaptive
- High-trust

---

## 11.2 Noa

Become a governed decision operating system.

- Secure
- Deterministic
- Modular
- Privacy-first
- Tool-extensible

---

# 12. Strategic Principle

We optimize for:

- Trust over novelty
- Determinism over magic
- Evidence over claims
- Governance over autonomy
- Retention over feature count
- Distribution over architecture purity

---

# 13. Final Alignment Statement

TheCoach builds depth.
Noa builds breadth.

TheCoach wins market share.
Noa wins trust and orchestration power.

They share philosophy:
- Bounded autonomy
- Explicit contracts
- Evidence-backed decisions
- Modular extensibility

But they must remain independently viable.
Build TheCoach to win the niche.
Build Noa to orchestrate the world.
Integrate them through contracts, not coupling.