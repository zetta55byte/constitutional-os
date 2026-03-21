# Constitutional OS — Ecosystem Overview

> One substrate. One API. Multiple clients. A single constitutional continuity chain.

---

## System Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    governed-research-lab                     │
│             reference multi-agent research system           │
│   Scout · Hypothesis · Research · Critique · Synthesis      │
│         React dashboard · SSE streaming · D3 graph          │
└─────────────────────────▲───────────────────────────────────┘
                          │  built with
                          │
┌─────────────────────────┴───────────────────────────────────┐
│                 constitutional-os-langchain                  │
│                   developer SDK + wrappers                   │
│          GovernedTool · GovernedAgent · escalation hooks     │
└─────────────────────────▲───────────────────────────────────┘
                          │  calls runtime API
                          │
┌─────────────────────────┴───────────────────────────────────┐
│                      Constitutional OS                       │
│          formal spec · runtime · invariants · membranes      │
│       continuity chain · delta calculus · Lyapunov · proofs  │
│              CLI · HTTP API · pip install                    │
└─────────────────────────────────────────────────────────────┘
```

This mirrors the architecture of real standards ecosystems:

| Standard | Library | Reference Implementation |
|----------|---------|--------------------------|
| POSIX | libc | reference shell |
| Ethereum Yellow Paper | EVM | Geth |
| Kubernetes API | client-go | kubelet |
| **Constitutional OS** | **constitutional-os-langchain** | **governed-research-lab** |

---

## What Each Layer Is

### 1. Constitutional OS — The Substrate

**Repo:** [constitutional-os](https://github.com/zetta55byte/constitutional-os)
**Install:** `pip install constitutional-os`
**API:** https://constitutional-os-production.up.railway.app
**Paper:** https://zenodo.org/records/19075163

The formal governance runtime. This is the standard. Everything else builds on it.

Implements:
- **Typed, reversible deltas** — every state change is a first-class object with an inverse
- **Invariant engine** — 5 built-in invariants + register your own
- **Four canonical membranes** — M1 Safety, M2 Reversibility, M3 Pluralism, M4 Human Primacy
- **Continuity chain** — append-only log of every ratified delta
- **Governance operator** Φ = G ∘ E — epistemic + governance in a single update
- **Lyapunov stability** — V(Σ) measures distance from constitutional-epistemic equilibrium
- **A-safety theorem** — constructive proof that all recommendations are safe before execution
- **CLI + HTTP/WebSocket API** — run it locally or hit the live endpoint

---

### 2. constitutional-os-langchain — The SDK

**Repo:** [constitutional-os-langchain](https://github.com/zetta55byte/constitutional-os-langchain)

The developer-facing integration layer. Wraps the Constitutional OS runtime into tools any LangChain agent can use in one line.

Provides:
- **`GovernedTool`** — wraps any `BaseTool` with M1–M4 membrane checking
- **`GovernedAgent`** — base class for membrane-aware agents
- **Reversible deltas** — all tool actions logged with delta IDs for rollback
- **Escalation hooks** — M4 Human Primacy triggers surface to the caller
- **Continuity-aware agent workflows** — full chain lineage across multi-step pipelines

```python
from governed.tool import GovernedTool

# One line to govern any LangChain tool
governed = GovernedTool(my_tool, agent_id="my_agent", governor=governor)
result = await governed._arun(query="...")
# membrane-checked → logged → escalated if needed → executed
```

---

### 3. governed-research-lab — The Reference System

**Repo:** [governed-research-lab](https://github.com/zetta55byte/governed-research-lab)

A fully governed, multi-agent research pipeline demonstrating Constitutional OS in production.

| Agent | Role | Primary Membrane |
|-------|------|-----------------|
| Scout | Reconnaissance, source discovery | M1 Safety |
| Hypothesis | Generates 3 diverse testable hypotheses | M3 Pluralism |
| Research | Deep investigation of each hypothesis | M2 Reversibility |
| Critique | Adversarial review, surfaces dissent | M3 Pluralism + M4 |
| Synthesis | Final report integrating all findings | All four |

---

## Quickstart — Run the Full Stack

```bash
# 1. Install the runtime
pip install constitutional-os
constitutional-os boot

# 2. Install the SDK
pip install constitutional-os-langchain

# 3. Run the reference implementation
git clone https://github.com/zetta55byte/governed-research-lab
cd governed-research-lab/backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Frontend
cd ../frontend && npm install && npm start
# → http://localhost:3000
```

---

## How to Extend

| What you want to build | Starting point |
|------------------------|---------------|
| A new governed agent | Extend `BaseGovernedAgent` in governed-research-lab |
| A new LangChain integration | Add a wrapper to constitutional-os-langchain |
| A new membrane | Register in the Constitutional OS invariant engine |
| A new client SDK (JS, Rust, Go) | Implement against the HTTP API spec |
| A new reference system | Fork governed-research-lab, swap the agents |
| A formal extension to the spec | Open an RFC in constitutional-os/rfc/ |

---

## Why This Matters

Autonomous systems fail when governance is bolted on after the fact.
Constitutional OS bakes governance into the substrate:

- **You govern deltas, not thoughts.** Every state change is typed, versioned, and membrane-checked before it executes.
- **You enforce invariants, not vibes.** Formal predicates that must hold at all times.
- **You maintain continuity, not patches.** An append-only chain means every decision is traceable.
- **You get reversibility, not drift.** Every ratified delta has an inverse. You can always go back.
- **You get formal guarantees, not heuristics.** The A-safety theorem proves constructively that all recommendations are safe.

This is how governance scales.

---

## Links

| Resource | URL |
|----------|-----|
| Constitutional OS | https://github.com/zetta55byte/constitutional-os |
| LangChain SDK | https://github.com/zetta55byte/constitutional-os-langchain |
| Reference Implementation | https://github.com/zetta55byte/governed-research-lab |
| Live API | https://constitutional-os-production.up.railway.app |
| PyPI | https://pypi.org/project/constitutional-os |
| Paper (Zenodo) | https://zenodo.org/records/19075163 |
| RFC-0001 | https://github.com/zetta55byte/constitutional-os/blob/main/rfc/RFC-0001-core-spec.md |
