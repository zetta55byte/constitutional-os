# Constitutional OS — Membrane Schema
## Spec v1.0 | DOI: 10.5281/zenodo.19075163

---

## Overview

A **membrane** is a typed filter on proposed state transitions.
Every proposed delta must pass through all active membranes before execution.
Membranes are: deterministic, stateless or locally stateful, monotonic, composable,
and invariant-preserving.

The key insight: **you govern deltas, not thoughts.**
Membranes operate on small, typed, reversible, serializable deltas —
not on the agent's world model or plan.

---

## Membrane Function Signature

```
membrane(state: ConstitutionalState, delta: ProposedDelta) → MembraneResult
```

### Inputs

| Field | Type | Description |
|-------|------|-------------|
| `state` | `ConstitutionalState` | Current constitutional state Σ_C |
| `delta` | `ProposedDelta` | The proposed state transition |

### ProposedDelta Schema

```yaml
delta_type: string          # Type identifier (e.g. "update_config", "tool_call")
payload: object             # Delta-type-specific payload
autonomy: enum              # autonomous | assisted | human-directed
severity: enum              # trivial | normal | significant | critical
reversible: boolean         # Whether the delta can be undone
scope: enum                 # local | global | constitutional
author: string              # Who proposed this delta
rationale: string           # Why this delta is proposed
```

---

## Membrane Result Schema

```yaml
membrane_id: string         # Unique membrane identifier
verdict: enum               # PASS | BLOCK | DEFER
reason: string              # Human-readable explanation
delta: object | null        # Reversible delta (if BLOCK or DEFER)
continuity_event_id: string # Chain entry ID for this decision
metadata: object            # Optional membrane-specific metadata
```

### Verdict Semantics

| Verdict | Meaning | Action |
|---------|---------|--------|
| `PASS` | Delta satisfies membrane constraints | Proceed to next membrane |
| `BLOCK` | Delta violates membrane constraints | Reject delta, log to chain |
| `DEFER` | Delta requires human review | Open veto window, suspend execution |

---

## Evaluation Contract

### Determinism
A membrane MUST return the same verdict for the same (state, delta) pair.
No randomness. No external calls. No side effects during evaluation.

### Ordering
Membranes are evaluated in registration order: M1 → M2 → M3 → M4.
A BLOCK from any membrane stops evaluation — subsequent membranes are skipped.
A DEFER from any membrane continues evaluation but marks the delta as deferred.

### Composition Rule
The final verdict is the most restrictive across all membranes:
```
BLOCK > DEFER > PASS
```

### Error Handling
A membrane that throws an exception MUST be treated as BLOCK with reason:
`"Membrane evaluation error: {exception}"`. Errors never silently pass.

---

## The Four Canonical Membranes

### M1 — Safety Membrane
**Governs:** Irreversible harm, destructive actions.
**Why it scales:** Monotonic — "never allow X" is stable under composition.

```yaml
id: M1_safety
policy: S1_invariant_preservation
blocks_when:
  - severity == critical AND autonomy == autonomous
  - scope == constitutional AND autonomy != human-directed
```

### M2 — Reversibility Membrane
**Governs:** State transitions that can't be undone.
**Why it scales:** Reversibility is a local property of deltas.

```yaml
id: M2_reversibility
policy: R1_no_irreversible_pending
defers_when:
  - reversible == false AND autonomy == autonomous
```

### M3 — Pluralism Membrane
**Governs:** Value-conflict minimization, option-space preservation.
**Why it scales:** It's a tension metric, not a rule list.

```yaml
id: M3_pluralism
policy: P1_no_net_tension_increase
blocks_when:
  - delta_type IN [remove_membrane, disable_invariant,
                   revoke_human_primacy, seal_state]
  - tension_sum(Σ') > tension_sum(Σ)
```

### M4 — Human Primacy Membrane
**Governs:** Human override, ratification of significant changes.
**Why it scales:** It's a meta-membrane gating the others.

```yaml
id: M4_human_primacy
policy: H1_bounded_pending_proposals
defers_when:
  - (severity IN [significant, critical]
     OR scope IN [global, constitutional]
     OR reversible == false)
    AND autonomy == autonomous
```

---

## Membrane Stack Evaluation Model

```
ProposedDelta
     │
     ▼
┌─────────────┐
│  M1 Safety  │──BLOCK──→ Rejected + logged to chain
└──────┬──────┘
       │ PASS
       ▼
┌──────────────────┐
│ M2 Reversibility │──DEFER──→ Human veto window opened
└──────┬───────────┘
       │ PASS
       ▼
┌───────────────┐
│ M3 Pluralism  │──BLOCK──→ Rejected + logged to chain
└──────┬────────┘
       │ PASS
       ▼
┌──────────────────┐
│ M4 Human Primacy │──DEFER──→ Human veto window opened
└──────┬───────────┘
       │ PASS
       ▼
   Ratified ──→ Applied to state + logged to chain
```

---

## Invariant Interaction

Membranes interact with invariants in two ways:

1. **Pre-check:** M1 evaluates whether applying the delta would violate any invariant.
   If yes → BLOCK.

2. **Post-check:** After ratification, all invariants are re-evaluated.
   If any invariant fails → rollback via inverse delta.

---

## Custom Membrane Registration

Any implementation may register additional membranes beyond M1–M4:

```python
custom_membrane = Membrane(
    id          = "custom.no_external_writes",
    name        = "No External Writes",
    description = "Block all writes to external systems",
    fn          = lambda state, delta: MembraneResult(
        verdict = "BLOCK" if delta.delta_type == "external_write" else "PASS",
        reason  = "External writes not permitted in this context",
    ),
    severity    = MembraneVerdictSeverity.BLOCK,
)
```

Custom membranes are evaluated after M1–M4 in registration order.

---

## Versioning

This is spec v1.0. Changes to membrane semantics require a new spec version.
Implementations MUST declare which spec version they implement.

```yaml
constitutional_os_spec: "1.0"
```
