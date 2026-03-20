# RFC-0004: Continuity Chain Format
**Status:** DRAFT  
**Created:** March 2026  
**Authors:** Zetta Byte  
**DOI:** 10.5281/zenodo.19075163

---

## Abstract

This RFC defines the format of the Constitutional OS continuity chain —
the append-only, hash-linked audit log that records every governance
decision. It specifies the canonical event schema, hash-linking rules,
append-only guarantees, event lifecycle, and retrieval API.

The continuity chain is the "git log for agents": a tamper-evident,
sequential record of everything the governance system has seen and decided.

---

## 1. Motivation

The continuity chain is the identity layer of Constitutional OS.
It provides:

1. A tamper-evident audit trail of all governance decisions
2. The ability to verify system integrity at any point
3. The data needed for rollback to any prior state
4. A complete record for compliance and debugging

This RFC formalizes the chain format so that:
- Third-party implementations produce compatible chains
- Chain verification is deterministic across implementations
- The chain can be used as evidence in compliance audits

---

## 2. Canonical Event Schema

```json
{
  "seq":                  "integer (monotonically increasing from 0)",
  "event_id":             "string (UUID v4)",
  "event_type":           "string (from event type registry)",
  "delta_id":             "string | null",
  "delta_type":           "string | null",
  "status":               "ratified | blocked | deferred | rolled_back",
  "verdict":              "PASS | BLOCK | DEFER | ROLLBACK",
  "rationale":            "string",
  "author":               "string",
  "ts":                   "string (ISO 8601 UTC)",
  "fingerprint":          "string (SHA-256[:32] of delta, or 'system' for non-delta events)",
  "prev_hash":            "string (SHA-256[:16] of previous entry)",
  "metadata":             "object (optional, event-type-specific)"
}
```

### Required fields
All fields except `metadata`, `delta_id`, and `delta_type` are required.
`delta_id` and `delta_type` are null for system events (boot, membrane changes, etc).

---

## 3. Event Type Registry (v1.0)

| Event Type | Delta? | Description |
|------------|--------|-------------|
| `system_boot` | No | Runtime initialized |
| `profile_loaded` | Yes | Behavioral profile loaded |
| `profile_updated` | Yes | Profile version updated |
| `eval_completed` | No | Eval bundle run completed |
| `drift_detected` | No | Forecast drift detected |
| `action_proposed` | Yes | Delta proposed for governance |
| `action_ratified` | Yes | Delta passed all checks |
| `action_blocked` | Yes | Delta rejected by membrane/invariant |
| `action_deferred` | Yes | Delta sent to human veto window |
| `human_approved` | Yes | Human approved deferred delta |
| `human_vetoed` | Yes | Human rejected deferred delta |
| `invariant_violated` | Yes | Post-ratification invariant failure |
| `rollback_applied` | Yes | Inverse delta applied |
| `membrane_added` | No | New membrane registered |
| `membrane_removed` | No | Membrane deregistered |

---

## 4. Hash-Linking Rules

Each entry is linked to the previous entry:

```
entry[n].prev_hash = SHA-256(canonical(entry[n-1]))[:16]
```

### 4.1 Canonical form for hashing

The canonical form excludes `prev_hash` itself:

```python
import json, hashlib

def canonical(entry: dict) -> str:
    fields = {k: v for k, v in entry.items() if k != 'prev_hash'}
    return json.dumps(fields, sort_keys=True, separators=(',', ':'))

def compute_prev_hash(entry: dict) -> str:
    return hashlib.sha256(
        canonical(entry).encode()
    ).hexdigest()[:16]
```

### 4.2 Genesis entry

The first entry (seq=0, event_type=system_boot) has:
```json
{ "prev_hash": "genesis" }
```

### 4.3 Hash chain invariant

For all n ≥ 1:
```
entry[n].prev_hash == SHA-256(canonical(entry[n-1]))[:16]
```

A chain that violates this invariant has been tampered with.

---

## 5. Append-Only Guarantee

Implementations MUST enforce:

1. **No deletion:** Entries cannot be removed.
2. **No modification:** Entries cannot be altered after creation.
3. **No insertion:** Entries cannot be inserted between existing entries.
4. **Monotonic sequence:** `seq` is strictly increasing with no gaps.
5. **Unique event IDs:** No two entries share an `event_id`.

---

## 6. Chain Verification

Any party can verify integrity by recomputing hash links:

```python
def verify(chain: list[dict]) -> bool:
    if not chain:
        return True
    if chain[0]['prev_hash'] != 'genesis':
        return False
    for i in range(1, len(chain)):
        expected = compute_prev_hash(chain[i-1])
        if chain[i]['prev_hash'] != expected:
            return False
        if chain[i]['seq'] != chain[i-1]['seq'] + 1:
            return False
    return True
```

Verification MUST be run:
- On system boot (if `verify_on_boot: true` in constitution.yaml)
- Before any rollback operation
- On demand via the verification API

---

## 7. How Governance Decisions Produce Events

Every call to the membrane stack produces exactly one chain entry.

### 7.1 Proposed delta → chain entry mapping

| Membrane result | Event type | Status | Verdict |
|----------------|------------|--------|---------|
| All PASS | `action_ratified` | ratified | PASS |
| Any BLOCK | `action_blocked` | blocked | BLOCK |
| Any DEFER (no BLOCK) | `action_deferred` | deferred | DEFER |
| Human approved | `human_approved` | ratified | PASS |
| Human vetoed | `human_vetoed` | blocked | BLOCK |
| Post-check invariant fail | `invariant_violated` + `rollback_applied` | rolled_back | ROLLBACK |

### 7.2 Rationale population

The `rationale` field is populated from:
- The blocking/deferring membrane's `reason` field
- The invariant's failure message
- "All membranes passed" for ratified deltas

---

## 8. Delta Embedding

Chain entries reference deltas by `delta_id` and `fingerprint`.
The full delta payload is stored separately in the delta store.

This keeps chain entries small (< 1KB typically) while maintaining
a complete audit trail. The fingerprint enables verification that
the referenced delta has not been modified.

---

## 9. Retrieval API

Implementations MUST support:

```
GET /api/log                    # All entries (paginated)
GET /api/log?n=N                # Last N entries
GET /api/log?seq=S              # Entry at sequence S
GET /api/log?from=T&to=T        # Entries in time range [T, T]
GET /api/log?status=S           # Filter by status
GET /api/log?verdict=V          # Filter by verdict
GET /api/log/verify             # Chain integrity check → {valid: bool}
GET /api/log/{event_id}         # Single entry by event_id
```

### 9.1 Pagination

For `GET /api/log`, implementations SHOULD support:
```
?page=N&per_page=50
```

Default page size: 50. Maximum page size: 500.

### 9.2 Verification response

```json
{
  "valid": true,
  "entries_checked": 142,
  "first_seq": 0,
  "last_seq": 141,
  "verified_at": "2026-03-19T12:00:00Z"
}
```

---

## 10. Retention Policy

Entries MUST be retained for at least `continuity_chain.retention_days`
(default: 90 days) from the entry timestamp.

After the retention period, entries MAY be archived but MUST NOT be deleted
if they are referenced by active state or pending rollback operations.

Archived entries MUST remain verifiable — the hash chain must remain intact
across the archive boundary.

---

## 11. Versioning

The continuity chain format is frozen at v1.0.
New event types may be added in minor versions.
Changes to hash-linking semantics, the canonical form, or the append-only
guarantee require a major version bump and a migration procedure.

---

## References

- RFC-0001: Core Specification
- RFC-0002: Membrane Schema
- RFC-0003: Reversible Delta Contract
- `spec/v1/continuity-chain.md`
- DOI: 10.5281/zenodo.19075163
