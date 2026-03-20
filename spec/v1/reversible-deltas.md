# Constitutional OS — Reversible Delta Contract
## Spec v1.0 | DOI: 10.5281/zenodo.19075163

---

## Overview

A **delta** is the atomic unit of state change in Constitutional OS.
All state transitions are expressed as typed, reversible deltas.
Deltas are: minimal, deterministic, serializable, schema-validated, and reversible.

The delta calculus forms a **groupoid**: every delta has an inverse,
composition is associative, and the identity delta exists for every state.

---

## Canonical Delta Structure

```yaml
id: string                  # Unique delta identifier (UUID or hash)
delta_type: string          # Type from the registered delta type set
payload: object             # Forward payload (type-specific)
payload_inv: object         # Inverse payload (enables rollback)
author: string              # Who proposed this delta
rationale: string           # Why this delta was proposed
ts: string                  # ISO 8601 timestamp
fingerprint: string         # SHA-256 of canonical serialization
status: enum                # proposed | ratified | blocked | deferred | rolled_back
```

---

## Delta Type Registry

### Core delta types (v1)

| Type | Description | Reversible |
|------|-------------|------------|
| `load_profile` | Load a behavioral profile into Σ_R | Yes — unload_profile |
| `update_profile` | Update an existing profile | Yes — restore prior version |
| `toggle_invariant` | Enable or disable an invariant | Yes — toggle back |
| `toggle_membrane` | Enable or disable a membrane | Yes — toggle back |
| `set_status` | Set system status | Yes — restore prior status |
| `pause_system` | Pause the governance loop | Yes — resume_system |
| `resume_system` | Resume the governance loop | Yes — pause_system |
| `update_config` | Update configuration | Yes — restore prior config |
| `investigate_degradation` | Log a degradation investigation | Yes — close investigation |
| `monitor_volatility` | Log a volatility monitor | Yes — close monitor |
| `note_improvement` | Log an improvement observation | Yes — remove note |

---

## Groupoid Structure

### Identity
For every state Σ, there exists an identity delta `id_Σ` such that:
```
id_Σ(Σ) = Σ
```

### Inverse
For every delta δ, there exists an inverse δ⁻¹ such that:
```
δ⁻¹(δ(Σ)) = Σ
```
The inverse is constructed from `payload_inv` stored in the original delta.

### Composition
If δ₁(Σ) = Σ' and δ₂(Σ') = Σ'', then:
```
(δ₂ ∘ δ₁)(Σ) = Σ''
```

### Associativity
```
(δ₃ ∘ δ₂) ∘ δ₁ = δ₃ ∘ (δ₂ ∘ δ₁)
```

---

## Minimality Requirement

A delta MUST be minimal: it changes only what is necessary to achieve
its stated purpose. A delta that updates field X MUST NOT also update
field Y unless Y is causally required by the change to X.

Minimality enables: precise rollback, clean audit trails,
and compositional reasoning about state transitions.

---

## Determinism Requirement

Applying the same delta to the same state MUST produce the same result:
```
apply(Σ, δ) = apply(Σ, δ)    ∀ Σ, δ
```

No randomness. No timestamps in payload computation.
No external state dependencies during application.

---

## Serialization Rules

Deltas MUST be serializable to JSON with the following constraints:

1. All keys are snake_case strings
2. All values are JSON-native types (string, number, boolean, array, object, null)
3. The canonical serialization is deterministic (sorted keys, no whitespace)
4. The fingerprint is `SHA-256(canonical_json(delta))[:32]`

```python
import json, hashlib

def fingerprint(delta: dict) -> str:
    canonical = json.dumps(delta, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical.encode()).hexdigest()[:32]
```

---

## Delta Lifecycle

```
proposed
    │
    ├── membrane check
    │       │
    │   BLOCK/DEFER ──→ blocked | deferred
    │       │
    │      PASS
    │       │
    ├── invariant check
    │       │
    │    FAIL ──→ blocked
    │       │
    │     PASS
    │       │
    ▼
ratified ──→ applied to state ──→ logged to continuity chain
    │
    └── rollback available via δ⁻¹
```

---

## Membrane Interaction

Before a delta is applied, it is evaluated by all active membranes.
The delta's fields (`autonomy`, `severity`, `reversible`, `scope`)
are the primary inputs to membrane evaluation.

A delta with `reversible: false` will trigger M2 (reversibility membrane)
if `autonomy == autonomous`.

---

## Continuity Chain Interaction

Every ratified delta produces a continuity chain entry:

```yaml
seq: integer                # Monotonically increasing sequence number
delta_id: string            # Reference to the ratified delta
delta_type: string          # Type of the delta
status: ratified            # Final status
ts: string                  # Ratification timestamp
fingerprint: string         # Delta fingerprint
prev_hash: string           # Hash of previous chain entry
```

The chain entry is append-only and hash-linked.
No chain entry can be modified or deleted after creation.

---

## Rollback

To rollback a delta, apply its inverse:

```python
engine = DeltaEngine()
new_state = engine.apply(state, delta)       # forward
old_state = engine.inverse(new_state, delta) # rollback
```

Rollback produces a new delta of type `rollback_{original_type}` with
`payload = original.payload_inv`. The rollback delta is itself ratified
through the membrane stack and logged to the continuity chain.

---

## Versioning

This is spec v1.0. New delta types may be added in minor versions.
Changes to delta semantics or the groupoid structure require a major version.
