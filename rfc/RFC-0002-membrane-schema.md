# RFC-0002: Membrane Schema
**Status:** DRAFT  
**Created:** March 2026  
**Authors:** Zetta Byte  
**DOI:** 10.5281/zenodo.19075163

---

## Abstract

This RFC defines the formal schema for Constitutional OS membranes —
the typed governance filters that evaluate proposed state transitions
before execution. It specifies the membrane function signature,
evaluation contract, result schema, composition rules, and the
four canonical membrane policies required for Lyapunov stability.

---

## 1. Motivation

RFC-0001 introduced the concept of membranes as the governance layer
of Constitutional OS. This RFC formalizes the membrane schema so that:

1. Third-party implementations can build compatible membrane engines
2. Custom membranes can be validated against a known schema
3. The four canonical membranes (M1–M4) have a precise, versioned specification
4. The relationship between membrane policies and Lyapunov stability is explicit

---

## 2. Membrane Function

A membrane is a pure function:

```
membrane: (ConstitutionalState × ProposedDelta) → MembraneResult
```

### 2.1 ProposedDelta Schema

```json
{
  "delta_type":  "string",
  "payload":     "object",
  "autonomy":    "autonomous | assisted | human-directed",
  "severity":    "trivial | normal | significant | critical",
  "reversible":  "boolean",
  "scope":       "local | global | constitutional",
  "author":      "string",
  "rationale":   "string"
}
```

### 2.2 MembraneResult Schema

```json
{
  "membrane_id":          "string",
  "verdict":              "PASS | BLOCK | DEFER",
  "reason":               "string",
  "delta":                "object | null",
  "continuity_event_id":  "string",
  "metadata":             "object"
}
```

### 2.3 Verdict Semantics

| Verdict | Meaning | Effect |
|---------|---------|--------|
| `PASS` | Constraints satisfied | Proceed to next membrane |
| `BLOCK` | Constraints violated | Reject delta permanently |
| `DEFER` | Human review required | Open veto window, suspend execution |

---

## 3. Evaluation Contract

### 3.1 Determinism
A membrane MUST return the same verdict for identical `(state, delta)` pairs.
No randomness, no external I/O, no side effects during evaluation.

### 3.2 Evaluation Order
Membranes evaluate in registration order: M1 → M2 → M3 → M4 → custom.

### 3.3 Short-Circuit Rule
A `BLOCK` verdict from any membrane immediately stops evaluation.
Subsequent membranes are not called.

### 3.4 Composition Rule
The final verdict is the most restrictive across all non-skipped membranes:
```
BLOCK > DEFER > PASS
```

### 3.5 Error Contract
A membrane that throws an exception MUST be treated as `BLOCK`:
```
verdict  = "BLOCK"
reason   = "Membrane evaluation error: {exception_message}"
```
Errors never silently pass.

---

## 4. The Four Canonical Membranes

### 4.1 M1 — Safety Membrane

**Policy S1 — Invariant Preservation**

Formally blocks δ when:
```
(severity(δ) = "critical" ∧ autonomy(δ) = "autonomous")
∨
(scope(δ) = "constitutional" ∧ autonomy(δ) ≠ "human-directed")
∨
(∃ i ∈ I. I_i(δ(Σ)) = false)
```

Effect on V(Σ): Ensures V_tension is non-increasing.

### 4.2 M2 — Reversibility Membrane

**Policy R1 — No Irreversible Pending Obligations**

Formally defers δ when:
```
reversible(δ) = false ∧ autonomy(δ) = "autonomous"
```

Effect on V(Σ): Prevents irreversible growth of |P(Σ)|, supports V_pending monotonicity.

### 4.3 M3 — Pluralism Membrane

**Policy P1 — No Net Increase in Invariant Tension**

Formally blocks δ when:
```
delta_type(δ) ∈ {remove_membrane, disable_invariant,
                  revoke_human_primacy, seal_state}
∨
∑_i α_i · v_i(δ(Σ)) > ∑_i α_i · v_i(Σ)
```

Effect on V(Σ): Enforces V_tension(δ(Σ)) ≤ V_tension(Σ).

### 4.4 M4 — Human Primacy Membrane

**Policy H1 — Bounded Growth of Pending Proposals**

Formally defers δ when:
```
autonomy(δ) = "autonomous"
∧
(severity(δ) ∈ {"significant", "critical"}
 ∨ scope(δ) ∈ {"global", "constitutional"}
 ∨ reversible(δ) = false)
```

Additionally blocks δ when:
```
|P(δ(Σ))| > B_pending
```
where B_pending is the configured upper bound on pending proposals.

Effect on V(Σ): Ensures |P(Σ)| cannot increase without human ratification.

---

## 5. Membrane Stack Evaluation Model

```
ProposedDelta
     │
     ▼
┌─────────────┐
│  M1 Safety  │──BLOCK──→ Rejected + chain entry
└──────┬──────┘
       │ PASS
       ▼
┌──────────────────┐
│ M2 Reversibility │──DEFER──→ Veto window + chain entry
└──────┬───────────┘
       │ PASS
       ▼
┌───────────────┐
│ M3 Pluralism  │──BLOCK──→ Rejected + chain entry
└──────┬────────┘
       │ PASS
       ▼
┌──────────────────┐
│ M4 Human Primacy │──DEFER──→ Veto window + chain entry
└──────┬───────────┘
       │ PASS
       ▼
  [Custom membranes...]
       │
       ▼
   Ratified ──→ Applied to Σ + chain entry
```

---

## 6. Custom Membrane Registration

Implementations MAY register additional membranes beyond M1–M4.
Custom membranes MUST:

1. Implement the membrane function signature (§2)
2. Satisfy the evaluation contract (§3)
3. Be registered with a unique `membrane_id`
4. Declare their verdict type (BLOCK or DEFER)

Custom membranes are evaluated after M1–M4 in registration order.

---

## 7. Membrane Policy Schema (constitution.yaml)

```yaml
membranes:
  - id: M1_safety
    enabled: true
    policy: S1_invariant_preservation

  - id: M2_reversibility
    enabled: true
    policy: R1_no_irreversible_pending

  - id: M3_pluralism
    enabled: true
    policy: P1_no_net_tension_increase

  - id: M4_human_primacy
    enabled: true
    policy: H1_bounded_pending_proposals
    max_pending: 5

  # Custom example
  - id: custom.no_external_writes
    enabled: true
    verdict: BLOCK
    rule: "delta_type != 'external_write'"
    reason: "External writes not permitted"
```

---

## 8. Relationship to Lyapunov Stability

The four canonical policies (S1, R1, P1, H1) are precisely the conditions
required to prove Theorem 3 (Lyapunov Stability) from the companion paper.

Together they guarantee:
```
V(δ(Σ)) ≤ V(Σ)  for any ratified δ
```

Any implementation that correctly implements M1–M4 with policies S1–H1
inherits this stability guarantee. See `spec/v1/state-machine.md` §8.

---

## 9. Versioning

This RFC is versioned independently from the runtime library.
Changes to membrane semantics require a new RFC version.
The current membrane schema is frozen at v1.0.

---

## References

- RFC-0001: Core Specification
- `spec/v1/membranes.md`: Membrane Schema Specification
- `spec/v1/state-machine.md`: Governance State Machine
- DOI: 10.5281/zenodo.19075163
