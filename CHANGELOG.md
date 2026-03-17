# Changelog

All notable changes to `constitutional-os` are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [0.1.0] — 2026-03-17

### Added

**Core runtime**
- `MetaState` — immutable global meta-state Σ = (Σ_R, Σ_C, Σ_X)
- `StateStore` — mutable wrapper with full history and rollback
- `EventDispatcher` — pure-function event routing `(Σ, event) → (Σ', [events])`
- Boot sequence with default invariants and membranes pre-registered

**Reliability OS (Σ_R)**
- `ProfileLoader` — load profiles from dict, YAML string, or file
- `ProfileRegistry` — versioned registry with history per profile ID
- `diff_profiles` — compute semantic diff between two profile versions
- `EvalRunner` — runs eval bundles, produces `EvalReport` with findings
- Built-in bundles: `core.integrity`, `core.health`
- `ForecastEngine` — exponential smoothing with confidence intervals,
  trend classification (stable / degrading / improving / volatile),
  risk classification (low / medium / high / critical)
- `ForecastState` — accumulates curves and recommendations
- `risk_heatmap` — 2D risk view per profile × metric

**Constitutional OS (Σ_C)**
- `load_default_invariants` — five built-in invariants:
  `I1_version_monotonic`, `I2_profiles_initialized`,
  `I3_log_append_only`, `I4_human_primacy`, `I5_eval_integrity`
- `load_default_membranes` — four canonical membranes:
  `M1_safety`, `M2_reversibility`, `M3_pluralism`, `M4_human_primacy`
- `DeltaEngine` — typed, reversible delta application over `MetaState`
- `ContinuityLog` — SHA-256 hash-chained append-only log with
  `verify()` for tamper detection
- `Delta` + `DeltaType` — typed delta calculus terms

**Formal theory (`runtime/theory.py`)**
- `lyapunov(state)` — governance energy V(Σ) with four components
  (V_inv, V_mem, V_drift, V_rec), fixed-point detection
- `lyapunov_decreasing(v1, v2)` — Lyapunov monotonicity check
- `check_a_safety(state, recs)` — constructive proof of A-safety theorem:
  ∀δ ∈ A(F). InvOK(Σ, δ) ∧ MemOK(δ) ⟹ safe(δ)
- `analyze_basin(state)` — identify which attractor basin Σ is in
- `separatrix_proximity(state)` — ridge curvature κ and separatrix distance
- `stability_report(state)` — full stability analysis combining all above

**Φ operator (`runtime/operators.py`)**
- `phi(state, ...)` — combined epistemic-governance step Φ = G ∘ E
- `phi_with_stability(state, ...)` — Φ with attached stability report
- Fixed-point detection: Φ(Σ) ≈ Σ when no admissible δ exists

**Console**
- CLI: `constitutional-os <command>` — boot, status, profile, eval,
  invariants, membranes, forecast, recommend, stability, log, rollback
- FastAPI HTTP surface on port 8001 (`constitutional-os --api`)

**Visualization (`runtime/visualization.py`)**
- `plot_lyapunov_trajectory` — V(S) decomposed over Φ cycles
- `plot_basin_map` — 2D governance-epistemic landscape (V_drift × V_mem)
- `plot_separatrix_proximity` — ridge curvature κ over time
- `plot_profile_heatmap` — risk heatmap per profile × cycle
- Dark-mode matplotlib output

**Tests**
- 187 tests across 6 test files
- `tests/test_profiles.py` — 21 tests
- `tests/test_invariants.py` — 24 tests
- `tests/test_membranes.py` — 25 tests
- `tests/test_evals.py` — 19 tests
- `tests/test_forecast.py` — 24 tests
- `tests/test_actions.py` — 18 tests
- `tests/test_theory.py` — 28 tests
- `tests/test_runtime.py` — 28 tests

### Mathematical foundations

This release implements four theorems from the companion whitepaper
([Zenodo DOI: 10.5281/zenodo.19045723](https://zenodo.org/records/19045723)):

- **Theorem 1 (Runtime Safety):** `valid(Σ) ⟹ valid(δ(Σ))` for all ratified δ
- **Theorem 2 (Reversibility):** Every δ has a groupoid inverse enabling rollback
- **Theorem 3 (Lyapunov Stability):** V(Σ) is non-increasing under Φ = G ∘ E
- **Theorem 4 (A-Safety):** Recommendations satisfy invariant + membrane constraints

---

## [Unreleased]

### Planned for 0.2.0
- Profile DSL interpreter (full YAML schema validation)
- Signed profile blobs (Ed25519)
- Multi-sport / multi-context profile registry
- WebSocket live dashboard
- arXiv companion paper submission
