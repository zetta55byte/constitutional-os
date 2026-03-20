# RFC-0003: Reversible Delta Contract
**Status:** DRAFT  
**Created:** March 2026  
**Authors:** Zetta Byte  
**DOI:** 10.5281/zenodo.19075163

---

## Abstract

This RFC defines the formal contract for reversible deltas in Constitutional OS —
the atomic, typed, invertible units of state change. It specifies the delta
structure, groupoid semantics, minimality and determinism requirements,
serialization rules, and lifecycle.

---

## 1. Motivation

All state changes in Constitutional OS are expressed as typed, reversible deltas.
This RFC formalizes the delta contract so that:

1. Third-party implementations can build compatible delta engines
2. Delta groupoid semantics are precisely specified
3. Rollback is guaranteed by construction
4. The continuity chain can reference deltas unambiguously

---

## 2. Canonical Delta Structure

```json
{
  "id":           "string (UUID or SHA-256 prefix)",
  "delta_type":   "string (from registered type set)",
  "payload":      "object (forward — type-specific)",
  "payload_inv":  "object (inverse — enables rollback)",
  "author":       "string",
  "rationale":    "string",
  "ts":           "string (ISO 8601 UTC)",
  "fingerprint":  "string (SHA-256[:32] of canonical serialization)",
  "status":       "proposed | ratified | blocked | deferred | rolled_back"
}
```

### Required fields
All fields are required. A delta missing any field MUST be rejected as malformed.

### Field constraints

| Field | Constraint |
|-------|-----------|
| `id` | Globally unique. Implementations SHOULD use UUID v4. |
| `delta_type` | MUST be registered in the delta type registry. |
| `payload` | MUST be a valid JSON object. |
| `payload_inv` | MUST be a valid JSON object sufficient to reverse `payload`. |
| `ts` | MUST be UTC. Format: `YYYY-MM-DDTHH:MM:SS.sssZ`. |
| `fingerprint` | MUST be `SHA-256(canonical_json(delta))[:32]`. |
| `status` | MUST be one of the five valid statuses. |

---

## 3. Delta Type Registry (v1.0)

| Type | Description | Inverse Type |
|------|-------------|--------------|
| `load_profile` | Load a behavioral profile | `unload_profile` |
| `update_profile` | Update an existing profile | `restore_profile` |
| `toggle_invariant` | Enable/disable an invariant | `toggle_invariant` (opposite state) |
| `toggle_membrane` | Enable/disable a membrane | `toggle_membrane` (opposite state) |
| `set_status` | Set system status | `restore_status` |
| `pause_system` | Pause governance loop | `resume_system` |
| `resume_system` | Resume governance loop | `pause_system` |
| `update_config` | Update configuration | `restore_config` |
| `investigate_degradation` | Log investigation | `close_investigation` |
| `monitor_volatility` | Log monitor | `close_monitor` |
| `note_improvement` | Log observation | `remove_note` |
| `rollback_*` | Rollback of any type | `re_apply_*` |

New types MAY be added in minor spec versions.
Removing types requires a major version bump.

---

## 4. Groupoid Structure

The set of deltas ∆_C forms a groupoid under composition.

### 4.1 Identity
For every state Σ, there exists an identity delta id_Σ ∈ ∆_C such that:
```
apply(Σ, id_Σ) = Σ
```

### 4.2 Inverse
For every delta δ, there exists an inverse δ⁻¹ ∈ ∆_C such that:
```
apply(apply(Σ, δ), δ⁻¹) = Σ
```
The inverse is constructed from `payload_inv`.

### 4.3 Composition
For deltas δ₁, δ₂ where δ₁(Σ) = Σ':
```
apply(Σ, δ₂ ∘ δ₁) = apply(apply(Σ, δ₁), δ₂)
```

### 4.4 Associativity
```
(δ₃ ∘ δ₂) ∘ δ₁ = δ₃ ∘ (δ₂ ∘ δ₁)
```

### 4.5 Rollback guarantee
The groupoid structure guarantees that any sequence of ratified deltas
can be undone by applying their inverses in reverse order:
```
apply(apply(...apply(Σ, δ₁)..., δₙ), δₙ⁻¹)...δ₁⁻¹) = Σ
```

---

## 5. Minimality Requirement

A delta MUST be minimal: it changes only what is necessary.

A delta that updates field X MUST NOT also update field Y unless Y is
causally required by the change to X.

**Why:** Minimality enables precise rollback, clean audit trails,
and compositional reasoning. A non-minimal delta makes it impossible
to undo exactly one change without also undoing others.

---

## 6. Determinism Requirement

Applying the same delta to the same state MUST produce the same result:
```
apply(Σ, δ) = apply(Σ, δ)  ∀ Σ, δ
```

No randomness. No timestamps in payload computation.
No external state dependencies during application.

---

## 7. Serialization Rules

Deltas MUST serialize to JSON with these constraints:

1. All keys are `snake_case` strings
2. All values are JSON-native types
3. Canonical serialization uses sorted keys, no whitespace
4. Fingerprint is `SHA-256(canonical_json(delta))[:32]`

```python
import json, hashlib

def canonical_json(delta: dict) -> str:
    return json.dumps(delta, sort_keys=True, separators=(',', ':'))

def fingerprint(delta: dict) -> str:
    return hashlib.sha256(
        canonical_json(delta).encode()
    ).hexdigest()[:32]
```

---

## 8. Delta Lifecycle

```
proposed
    │
    ├── malformed check ──fail──→ rejected (not logged)
    │
    ├── membrane stack
    │   ├── BLOCK ──→ blocked (logged to chain)
    │   └── DEFER ──→ deferred (logged, veto window opened)
    │       ├── human vetoed  ──→ blocked (logged)
    │       └── human approved ──→ continue
    │
    ├── invariant pre-check
    │   └── fail ──→ blocked (logged)
    │
    ▼
ratified ──→ applied to Σ ──→ logged to chain
    │
    └── invariant post-check
        └── fail ──→ rollback δ⁻¹ applied ──→ logged
```

---

## 9. Membrane Interaction

The delta's typed fields are the primary inputs to membrane evaluation:

| Delta field | Membrane | Policy |
|------------|----------|--------|
| `severity == critical` + `autonomy == autonomous` | M1 | S1 |
| `reversible == false` + `autonomy == autonomous` | M2 | R1 |
| `delta_type` in lock-in set | M3 | P1 |
| `severity in [significant, critical]` + `autonomy == autonomous` | M4 | H1 |

---

## 10. Continuity Chain Interaction

Every ratified delta produces exactly one chain entry (see RFC-0004).
The chain entry references the delta by `delta_id` and `fingerprint`.

Rollback deltas also produce chain entries, creating a complete
audit trail of both forward and reverse operations.

---

## 11. Versioning

The delta contract is frozen at v1.0.
New delta types may be added in minor versions.
Changes to groupoid semantics or the canonical structure require a major version.

---

## References

- RFC-0001: Core Specification
- RFC-0002: Membrane Schema
- `spec/v1/reversible-deltas.md`
- DOI: 10.5281/zenodo.19075163
