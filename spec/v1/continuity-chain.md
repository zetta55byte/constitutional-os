# Constitutional OS — Continuity Chain Format
## Spec v1.0 | DOI: 10.5281/zenodo.19075163

---

## Overview

The **continuity chain** is the append-only, hash-linked audit log of the
Constitutional OS runtime. It records every governance decision: ratified deltas,
blocked proposals, deferred actions, and rollbacks.

The continuity chain is the "git log for agents" — a tamper-evident, sequential
record of everything the governance system has seen and decided.

---

## Canonical Event Schema

```yaml
seq: integer                # Monotonically increasing, starts at 0
event_id: string            # Unique event identifier (UUID)
event_type: enum            # See event types below
delta_id: string | null     # Reference to associated delta (if any)
delta_type: string | null   # Type of associated delta (if any)
status: enum                # ratified | blocked | deferred | rolled_back
verdict: enum               # PASS | BLOCK | DEFER | ROLLBACK
rationale: string           # Human-readable explanation
author: string              # Who proposed the delta
ts: string                  # ISO 8601 timestamp (UTC)
fingerprint: string         # SHA-256[:32] of canonical delta serialization
prev_hash: string           # SHA-256[:16] of previous entry's canonical form
metadata: object            # Optional event-specific metadata
```

---

## Event Types

| Event Type | Description |
|------------|-------------|
| `system_boot` | Runtime initialized |
| `profile_loaded` | Behavioral profile loaded into Σ_R |
| `profile_updated` | Behavioral profile version updated |
| `eval_completed` | Eval bundle run completed |
| `drift_detected` | Forecast drift detected |
| `action_proposed` | Delta proposed for governance check |
| `action_ratified` | Delta passed all membranes and invariants |
| `action_blocked` | Delta rejected by membrane or invariant |
| `action_deferred` | Delta sent to human veto window |
| `human_approved` | Human approved a deferred delta |
| `human_vetoed` | Human rejected a deferred delta |
| `invariant_violated` | Invariant check failed (post-ratification) |
| `rollback_applied` | Inverse delta applied to restore prior state |
| `membrane_added` | New membrane registered |
| `membrane_removed` | Membrane deregistered (M3 may block this) |

---

## Hash-Linking Rules

Each entry is linked to the previous entry via `prev_hash`:

```
prev_hash(entry_n) = SHA-256(canonical(entry_{n-1}))[:16]
```

The genesis entry (seq=0, event_type=system_boot) has:
```
prev_hash = "genesis"
```

### Canonical form for hashing

```python
import json, hashlib

def canonical(entry: dict) -> str:
    # Exclude prev_hash from the hash computation
    fields = {k: v for k, v in entry.items() if k != 'prev_hash'}
    return json.dumps(fields, sort_keys=True, separators=(',', ':'))

def compute_prev_hash(entry: dict) -> str:
    return hashlib.sha256(canonical(entry).encode()).hexdigest()[:16]
```

---

## Append-Only Guarantee

The continuity chain MUST be append-only. Implementations MUST enforce:

1. **No deletion:** Entries cannot be removed from the chain.
2. **No modification:** Entries cannot be altered after creation.
3. **No insertion:** Entries cannot be inserted between existing entries.
4. **Monotonic sequence:** `seq` values are strictly increasing with no gaps.

---

## Chain Verification

Any party can verify chain integrity by recomputing the hash links:

```python
def verify(chain: list) -> bool:
    for i in range(1, len(chain)):
        expected = compute_prev_hash(chain[i-1])
        if chain[i]['prev_hash'] != expected:
            return False
    return True
```

A failed verification indicates tampering or corruption.

---

## Event Lifecycle

### Proposed delta flow
```
action_proposed
    │
    ├── membrane BLOCK ──→ action_blocked
    ├── membrane DEFER ──→ action_deferred
    │                          │
    │                    human_approved ──→ action_ratified
    │                    human_vetoed   ──→ action_blocked
    │
    └── all membranes PASS ──→ action_ratified
                                    │
                              invariant fail ──→ invariant_violated
                                                      │
                                                rollback_applied
```

---

## How Governance Decisions Produce Events

Every call to the membrane stack produces exactly one continuity chain entry.
The entry captures:

1. What was proposed (`delta_type`, `delta_id`)
2. What the membranes decided (`verdict`, `status`)
3. Why (`rationale` — populated from the blocking/deferring membrane's reason)
4. When (`ts`)
5. Who proposed it (`author`)
6. The cryptographic link to the prior entry (`prev_hash`)

---

## How Deltas Are Embedded

The continuity chain entry references a delta by `delta_id` but does not
embed the full delta payload. The delta payload is stored separately in the
delta store and referenced by ID.

This keeps chain entries small and serializable while maintaining
a complete audit trail.

---

## Retrieval

Implementations MUST support:

```
GET /api/log?n=N           # Last N entries
GET /api/log?seq=S         # Entry at sequence S
GET /api/log?from=T&to=T   # Entries in time range
GET /api/log/verify        # Chain integrity check
```

---

## Retention

Chain entries MUST be retained for at least the configured
`continuity_chain.retention_days` period (default: 90 days).
After retention period, entries MAY be archived but MUST NOT be deleted
if they are referenced by active state.

---

## Versioning

This is spec v1.0. The chain format is stable.
New event types may be added in minor versions.
Changes to hash-linking semantics require a major version bump
and a migration procedure.
