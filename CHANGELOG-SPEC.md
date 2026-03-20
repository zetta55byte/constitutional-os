# Constitutional OS — Spec Changelog

All changes to the Constitutional OS specification are documented here.

---

## [v1.0.0] — March 2026 — FROZEN

### Spec documents
- `spec/v1/membranes.md` — Membrane Schema Specification
- `spec/v1/reversible-deltas.md` — Reversible Delta Contract
- `spec/v1/continuity-chain.md` — Continuity Chain Format
- `spec/v1/state-machine.md` — Governance State Machine

### Schema
- `constitution.yaml` — Constitutional OS Manifest format

### RFCs
- `rfc/RFC-0001-core-spec.md` — Core specification

### What this version defines

**Membranes**
- Four canonical membranes: M1 Safety, M2 Reversibility, M3 Pluralism, M4 Human Primacy
- Membrane function signature: `(state, delta) → MembraneResult`
- Three verdicts: PASS, BLOCK, DEFER
- Four membrane policies: S1, R1, P1, H1
- Evaluation order and composition rules
- Determinism and statelessness requirements

**Reversible Deltas**
- Canonical delta structure with `payload` and `payload_inv`
- Groupoid structure: identity, inverse, composition, associativity
- Minimality and determinism requirements
- Serialization rules and fingerprinting
- Delta lifecycle: proposed → ratified/blocked/deferred → rolled_back

**Continuity Chain**
- Canonical event schema with SHA-256 hash linking
- Append-only guarantee
- 14 event types
- Chain verification algorithm
- Retention policy

**State Machine**
- Global meta-state Σ = (Σ_R, Σ_C, Σ_X)
- Epistemic operator E and governance operator G
- Combined operator Φ = G ∘ E
- Constitutional fixed points
- Governance energy V(Σ) with Lyapunov stability theorem
- Admissible controller definition
- Three integration hooks: propose_plan, propose_action, propose_delta
- Single interface event: ActionRecommended

**Constitution.yaml**
- Full schema with all required and optional fields
- Five agent type presets with default configurations
- Membrane configuration
- Invariant configuration
- Allowed actions (autonomous / human_directed / blocked)
- Oversight and logging configuration
- Continuity chain configuration
- Governance energy weights

### Mathematical foundations

Four formal theorems proved in the companion paper:

1. **Runtime Safety:** `valid(Σ) ⟹ valid(δ(Σ))` for all ratified δ
2. **Reversibility:** Every ratified delta has a groupoid inverse
3. **Lyapunov Stability:** V(Σ) non-increasing under Φ for admissible controllers
4. **A-Safety:** `InvOK(Σ, δ) ∧ MemOK(δ) ⟹ safe(δ)` for all forecast recommendations

Portability corollary: any controller implementing the constitutional protocol
inherits Lyapunov stability regardless of implementation language or strategy.

---

## [Unreleased — v1.1.0]

### Planned
- RFC-0002: Membrane Schema (formal RFC document)
- RFC-0003: Reversible Delta Contract (formal RFC document)
- RFC-0004: Continuity Chain Format (formal RFC document)
- `constitution.yaml` JSON Schema validator
- `constitutional-os validate` CLI command
- Governed planning agent example
- Governed multi-agent negotiation example
