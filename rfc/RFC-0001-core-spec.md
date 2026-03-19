# RFC-0001: Constitutional OS Core Specification

**Status:** Draft  
**Version:** 1.0.0  
**Date:** March 2026  
**Author:** Zetta Byte  
**Repository:** https://github.com/zetta55byte/constitutional-os

---

## Abstract

This document specifies the core contracts of Constitutional OS: a formal
epistemic-governance substrate for AI systems. It defines the global
meta-state, the governance-check API, the four canonical membranes, the
reversible delta contract, the continuity chain format, and the invariants
model. Implementations that conform to this specification are
**Constitutional OS-compatible** and inherit the Lyapunov stability
guarantee proven in the companion paper (Zenodo: 10.5281/zenodo.19075163).

---

## 1. Motivation

AI agent frameworks lack a standard substrate for governance. Every team
reinvents logging, audit trails, reversibility, and human oversight from
scratch — inconsistently, incompletely, and without formal guarantees.

Constitutional OS provides:

- A **typed, reversible delta calculus** so every state change can be undone
- **Four canonical membranes** that gate actions before execution
- An **append-only continuity chain** for tamper-evident audit trails
- A **governance-check API** that any agent framework can call
- **Formal safety guarantees** proven in the companion paper

This RFC defines the contracts. The reference implementation is
`pip install constitutional-os`.

---

## 2. Terminology

| Term | Definition |
|------|------------|
| **Delta** | A typed, reversible state change |
| **Membrane** | A filter on proposed deltas: pass / block / defer |
| **Invariant** | A predicate that must hold at all times |
| **Profile** | A versioned behavioral specification |
| **Continuity chain** | An append-only, hash-chained log of ratified deltas |
| **Governance check** | The act of submitting a proposed action for evaluation |
| **Ratified delta** | A delta that passed all invariants and membranes |
| **Fixed point** | A state where no admissible delta is recommended |
| **Admissible controller** | A Φ that only ratifies constitutionally valid deltas |

---

## 3. Global Meta-State

The complete state of a Constitutional OS runtime is:

```
Σ = (Σ_R, Σ_C, Σ_X)
```

Where:

- **Σ_R** = Reliability state: `(profiles P, eval_history H, forecasts F)`
- **Σ_C** = Constitutional state: `(invariants I, membranes M, log L, rights R, obligations O)`
- **Σ_X** = Reality layer: raw observations from the governed system

### 3.1 State Immutability

All state transitions produce a new Σ. The old state is preserved in the
continuity chain. This enables:

- Rollback to any prior state
- Deterministic replay from the log
- Full audit trail

### 3.2 State Version

Every Σ carries a monotonically increasing integer version. Versions never
decrease. This is enforced by invariant I1.

---

## 4. The Governance Check API

### 4.1 Endpoint

```
POST /governance/check
Authorization: Bearer <api_key>
Content-Type: application/json
```

### 4.2 Request Schema

```json
{
  "action_id": "string (required) — unique ID for this proposed action",
  "delta_type": "string (required) — type of change being proposed",
  "payload": "object (required) — the change parameters",
  "autonomy": "string (required) — autonomous | assisted | human-directed",
  "severity": "string (required) — trivial | normal | significant | critical",
  "reversible": "boolean (required) — can this change be undone?",
  "scope": "string (required) — local | global | constitutional",
  "requester": "string (optional) — identifier of the requesting agent",
  "profile_id": "string (optional) — constitutional profile to evaluate against",
  "context": "object (optional) — additional context for membrane evaluation"
}
```

### 4.3 Response Schema

```json
{
  "check_id": "string — unique ID for this governance check",
  "verdict": "string — pass | block | defer",
  "rationale": "string — human-readable explanation of the verdict",
  "membrane_results": [
    {
      "membrane_id": "string",
      "verdict": "string — pass | block | defer",
      "reason": "string"
    }
  ],
  "invariant_results": [
    {
      "invariant_id": "string",
      "passed": "boolean",
      "reason": "string"
    }
  ],
  "continuity_entry": {
    "seq": "integer",
    "fingerprint": "string",
    "prev_hash": "string",
    "ts": "string (ISO 8601)"
  },
  "requires_human_approval": "boolean",
  "rollback_available": "boolean",
  "ts": "string (ISO 8601)"
}
```

### 4.4 Verdict Semantics

| Verdict | Meaning | Agent should |
|---------|---------|--------------|
| `pass` | Action cleared all checks | Execute the action |
| `block` | Action violates a membrane or invariant | Do not execute; log the block |
| `defer` | Action requires human review | Pause and wait for human approval |

### 4.5 Example

```python
import requests

response = requests.post(
    "https://constitutional-os-production.up.railway.app/governance/check",
    headers={"Authorization": "Bearer <api_key>"},
    json={
        "action_id": "act_001",
        "delta_type": "external_api_call",
        "payload": {"url": "https://api.example.com/delete", "method": "DELETE"},
        "autonomy": "autonomous",
        "severity": "significant",
        "reversible": False,
        "scope": "local",
        "requester": "my-agent-v1"
    }
)

decision = response.json()
if decision["verdict"] == "pass":
    execute_action()
elif decision["verdict"] == "block":
    log_block(decision["rationale"])
elif decision["verdict"] == "defer":
    await_human_approval(decision["check_id"])
```

---

## 5. The Four Canonical Membranes

Every governance check passes through four membranes in order. A single
block stops the chain. A defer escalates to human review.

### M1 — Safety Membrane

**Purpose:** Prevent critical autonomous changes and constitutional-scope
changes without human direction.

**Blocks if:**
```
(severity == "critical" AND autonomy == "autonomous")
OR
(scope == "constitutional" AND autonomy != "human-directed")
```

**Effect on V(Σ):** Ensures V_tension is non-increasing.

### M2 — Reversibility Membrane

**Purpose:** Prevent irreversible autonomous changes without human review.

**Defers if:**
```
reversible == false AND autonomy == "autonomous"
```

**Effect on V(Σ):** Prevents irreversible growth of pending obligations.

### M3 — Pluralism Membrane

**Purpose:** Prevent changes that eliminate future option space.

**Blocks if:**
```
delta_type IN [
  "remove_membrane",
  "disable_invariant",
  "revoke_human_primacy",
  "seal_state"
]
```

**Effect on V(Σ):** Enforces V_tension(Σ') ≤ V_tension(Σ).

### M4 — Human Primacy Membrane

**Purpose:** Ensure significant changes require human approval.

**Defers if:**
```
(severity IN ["significant", "critical"]
 OR scope IN ["global", "constitutional"]
 OR reversible == false)
AND autonomy == "autonomous"
```

**Effect on V(Σ):** Ensures V_pending(Σ') ≤ V_pending(Σ).

### 5.1 Membrane Evaluation Order

```
M1 (Safety) → M2 (Reversibility) → M3 (Pluralism) → M4 (Human Primacy)
```

A block at any membrane stops evaluation. All four must pass for verdict
`pass`. Any defer produces verdict `defer`.

---

## 6. The Reversible Delta Contract

### 6.1 Delta Schema

```json
{
  "id": "string — unique delta identifier",
  "delta_type": "string — type from the delta type registry",
  "payload": "object — forward transformation parameters",
  "payload_inv": "object — inverse transformation parameters (for rollback)",
  "author": "string — who proposed this delta",
  "rationale": "string — why this delta was proposed",
  "created_at": "string (ISO 8601)",
  "proposal_id": "string — governance check ID that ratified this delta",
  "fingerprint": "string — SHA-256[:12] of canonical(delta_type + payload + created_at)"
}
```

### 6.2 Delta Type Registry

| Type | Description | Reversible |
|------|-------------|------------|
| `load_profile` | Load a behavioral profile | Yes — unload |
| `update_profile` | Update a profile version | Yes — revert |
| `toggle_invariant` | Enable/disable an invariant | Yes — toggle back |
| `toggle_membrane` | Enable/disable a membrane | Yes — toggle back |
| `set_status` | Set runtime status | Yes — revert status |
| `pause_system` | Pause the runtime | Yes — resume |
| `resume_system` | Resume the runtime | Yes — pause |
| `update_config` | Update configuration | Yes — revert config |
| `investigate_degradation` | Epistemic recommendation | Yes — no-op |
| `monitor_volatility` | Epistemic recommendation | Yes — no-op |
| `note_improvement` | Epistemic recommendation | Yes — no-op |

### 6.3 Groupoid Structure

The delta set Δ_C forms a groupoid:

1. **Identity:** ∀Σ, ∃ id_Σ ∈ Δ_C such that id_Σ(Σ) = Σ
2. **Inverse:** ∀δ, ∃ δ⁻¹ ∈ Δ_C such that δ⁻¹(δ(Σ)) = Σ
3. **Composition:** (δ₂ ∘ δ₁)(Σ) = δ₂(δ₁(Σ))
4. **Associativity:** (δ₃ ∘ δ₂) ∘ δ₁ = δ₃ ∘ (δ₂ ∘ δ₁)

Any sequence of ratified deltas can be undone by applying inverses in
reverse order.

---

## 7. The Continuity Chain Format

### 7.1 Log Entry Schema

```json
{
  "seq": "integer — monotonically increasing sequence number",
  "delta_id": "string — ID of the delta applied",
  "delta_type": "string — type of the delta",
  "fingerprint": "string — delta fingerprint",
  "state_version": "integer — Σ version after this delta",
  "proposal_id": "string — governance check ID",
  "status": "string — proposed | ratified | executed | blocked | deferred",
  "author": "string — who proposed the delta",
  "rationale": "string — why the delta was applied",
  "prev_hash": "string — SHA-256[:16] of canonical(previous entry)",
  "ts": "string (ISO 8601)"
}
```

### 7.2 Chain Integrity

The genesis entry has `prev_hash = "genesis"`. Every subsequent entry
includes the SHA-256 hash of the previous entry's canonical JSON
serialization (keys sorted, no whitespace).

Chain integrity can be verified at any time:

```python
log.verify()  # True if intact, False if tampered
```

### 7.3 Append-Only Guarantee

Entries are never modified or deleted. The log is append-only. Any
retroactive modification is detectable via hash chain verification and
is reported as a violation of invariant I3.

---

## 8. The Invariants Model

### 8.1 Invariant Schema

```json
{
  "id": "string — unique invariant identifier",
  "name": "string — human-readable name",
  "description": "string — what this invariant enforces",
  "severity": "string — warning | error | fatal",
  "enabled": "boolean",
  "tags": ["string"]
}
```

### 8.2 Built-in Invariants

| ID | Name | Severity | Description |
|----|------|----------|-------------|
| `I1_version_monotonic` | Version Monotonicity | fatal | State version never decreases |
| `I2_profiles_initialized` | Profiles Initialized | warning | Profile registry accessible |
| `I3_log_append_only` | Log Append-Only | fatal | Continuity log not retroactively modified |
| `I4_human_primacy` | Human Primacy | fatal | No fatal autonomous actions without human approval |
| `I5_eval_integrity` | Eval Integrity | error | Eval history not tampered |

### 8.3 Invariant Evaluation

All invariants are checked before ratifying any delta. A fatal invariant
failure blocks the delta and may halt the system. An error blocks the delta.
A warning logs but allows.

### 8.4 Custom Invariants

Implementations may register additional invariants:

```python
from constitutional_os import Invariant, InvariantSeverity, InvariantResult

my_invariant = Invariant(
    id          = "custom.my_check",
    name        = "My Custom Check",
    description = "Enforces my custom constraint",
    fn          = lambda state: InvariantResult(
        "custom.my_check",
        my_condition(state),
        reason = "Condition failed"
    ),
    severity    = InvariantSeverity.ERROR,
)
store.current.invariants.register(my_invariant)
```

---

## 9. Constitutional Profile Schema

A profile specifies expected behavior for a system component:

```json
{
  "id": "string",
  "name": "string",
  "version": "string (semver)",
  "description": "string",
  "tags": ["string"],
  "metrics": [
    {
      "name": "string",
      "description": "string",
      "unit": "string",
      "threshold": "number",
      "baseline": "number",
      "direction": "higher_is_better | lower_is_better | target"
    }
  ],
  "evals": [
    {
      "bundle_id": "string",
      "required": "boolean",
      "weight": "number"
    }
  ],
  "actions": [
    {
      "action_id": "string",
      "delta_type": "string",
      "description": "string",
      "auto_propose": "boolean"
    }
  ],
  "config": "object"
}
```

---

## 10. Versioning

This specification follows semantic versioning.

- **Patch** (1.0.x): clarifications, typo fixes, non-breaking additions
- **Minor** (1.x.0): new optional fields, new delta types, new built-in membranes
- **Major** (x.0.0): breaking changes to API contracts or core schemas

Implementations must declare the RFC version they conform to:

```python
constitutional_os.__rfc_version__ = "RFC-0001-1.0.0"
```

---

## 11. Conformance

An implementation is **Constitutional OS-compatible** if it:

1. Implements the governance-check API (Section 4)
2. Enforces all four canonical membranes in order (Section 5)
3. Uses the reversible delta contract (Section 6)
4. Maintains an append-only continuity chain (Section 7)
5. Checks all registered invariants before ratifying deltas (Section 8)

Conformant implementations inherit the Lyapunov stability guarantee:
V(Σ) is non-increasing under any sequence of ratified deltas.

---

## 12. References

- Companion paper: https://zenodo.org/records/19075163
- Reference implementation: https://github.com/zetta55byte/constitutional-os
- PyPI: https://pypi.org/project/constitutional-os/
- Live API: https://constitutional-os-production.up.railway.app/

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | March 2026 | Initial specification |
