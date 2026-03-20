# Constitutional OS — Governance State Machine
## Spec v1.0 | DOI: 10.5281/zenodo.19075163

---

## Overview

The Constitutional OS runtime is a formal state machine over the
global meta-state Σ = (Σ_R, Σ_C, Σ_X).

The update operator **Φ = G ∘ E** advances the state machine one step:
- **E** (epistemic operator): evaluates reality, produces recommendations
- **G** (governance operator): applies governance lifecycle to recommendations

---

## Global Meta-State

```
Σ = (Σ_R, Σ_C, Σ_X)
```

| Component | Contents |
|-----------|----------|
| `Σ_R` (Reliability OS) | Profile registry P, eval history H, forecast state F |
| `Σ_C` (Constitutional OS) | Invariants I, membranes M, continuity log L, rights R, obligations O |
| `Σ_X` (Reality layer) | Raw observations from the governed system |

All state is **immutable**. Every transition produces a new Σ.
The old state is preserved in the continuity log L.

---

## State Validity

A state Σ is **valid** iff all invariants hold:
```
valid(Σ) ⟺ ∀k. Iₖ(Σ) = true
```

The runtime MUST maintain valid(Σ) at all times.
Any transition that would produce an invalid state MUST be blocked.

---

## The Epistemic Operator E

```
E: Σ → (Σ_R', δ_rec)
```

**Steps:**
1. Load profiles from registry P
2. Run configured eval bundles against Σ_X
3. Update forecast curves in F
4. Classify drift (stable | degrading | improving | volatile)
5. Derive recommended delta δ_rec from forecast state
6. Return updated Σ_R' and δ_rec (may be null if no action warranted)

**Properties:**
- E never modifies Σ_C directly
- E never applies deltas to Σ
- E produces at most one recommended delta per cycle

---

## The Governance Operator G

```
G: (Σ, δ) → Σ_C'
```

**Steps:**
1. Check all invariants: `∀k. Iₖ(Σ)` — if any fail, reject δ
2. Run membrane stack M1 → M2 → M3 → M4
3. On BLOCK: log to continuity chain, return Σ_C unchanged
4. On DEFER: open human veto window, suspend δ, log to chain
5. On PASS: apply δ to Σ, check invariants on δ(Σ)
6. If post-application invariants fail: apply δ⁻¹, log rollback
7. If all pass: log ratification to chain, return updated Σ_C'

**Properties:**
- G never modifies Σ_R directly
- G never skips the membrane stack
- G always logs to the continuity chain

---

## Combined Operator Φ = G ∘ E

```
Φ: Σ → Σ'

Φ(Σ) = G(Σ, E(Σ).δ_rec)
      = (Σ_R', Σ_C', Σ_X)
```

One cycle of Φ is one **epistemic-governance step**.

---

## Constitutional Fixed Points

A **constitutional-epistemic fixed point** is a state Σ* where:
```
Φ(Σ*) = Σ*
```

This occurs when:
- E produces no recommended delta, OR
- All recommended deltas are blocked or deferred by membranes

Fixed points are the **stable attractors** of the governance system.

---

## Governance Energy V(Σ)

The governance energy measures distance from a fixed point:

```
V(Σ) = w_drift    · V_drift(Σ)      # eval scores below threshold
      + w_tension  · V_tension(Σ)    # invariants near violation
      + w_pending  · V_pending(Σ)    # unresolved deferred proposals
```

**Lyapunov Stability Theorem:** V(Σ) is non-increasing under Φ
for any admissible controller. V(Σ) = 0 iff Σ is a fixed point.

---

## Admissible Controller

A controller Φ is **admissible** iff for all ratified deltas δ:

1. δ is well-typed in the delta calculus
2. All invariants hold in Σ and δ(Σ)
3. δ passes all membranes M1–M4
4. All required eval bundles for δ have been run with thresholds satisfied

Any admissible controller inherits Lyapunov stability.
This is the **portability guarantee**: stochastic, learned, or distributed
controllers all inherit stability as long as they implement this protocol.

---

## Governance Basins

The state space is partitioned into four governance basins:

| Basin | Condition | Meaning |
|-------|-----------|---------|
| `stable_governance` | V(Σ) < 0.05 | True attractor, no action needed |
| `drifting_epistemic` | V_drift > 0, V_tension = 0 | Forecast drift, governance intact |
| `governance_pressure` | V_pending > 0 | Deferred proposals accumulating |
| `critical_instability` | Multiple components elevated | Immediate attention required |

---

## Three Integration Hooks

Any agent framework integrating Constitutional OS MUST expose three hooks:

```
propose_plan(plan)      → GovernanceDecision
propose_action(action)  → GovernanceDecision
propose_delta(delta)    → GovernanceDecision
```

| Hook | Layer | Governs |
|------|-------|---------|
| `propose_plan` | Intent | What the agent intends to do |
| `propose_action` | Capability | What the agent tries to invoke |
| `propose_delta` | State-transition | What the agent actually changes |

These three hooks provide complete governance coverage.
They correspond to the three levels of agentic computation:
plan → action → delta.

---

## Interface Event

The two layers communicate through exactly one typed event:

```
ActionRecommended(
    delta_type: string,
    payload: object,
    autonomy: enum,
    severity: enum,
    reversible: boolean,
    rationale: string
)
```

Reliability OS fires `ActionRecommended`.
Constitutional OS catches it and runs the governance lifecycle.
No other cross-layer communication is permitted.

---

## Versioning

This is spec v1.0. The state machine semantics are stable.
Changes to Φ semantics, the energy function, or the three-hook API
require a major version bump.
