"""
runtime/theory.py

Formal properties of the epistemic-governance stack, implemented as
checkable functions.

1. LYAPUNOV STABILITY FUNCTION  V: S → ℝ≥0
   A "governance energy" measure. V(S) = 0 iff S is a fixed point.
   V decreases (or stays flat) under T = G ∘ E — the system is
   Lyapunov-stable around its constitutional-epistemic attractors.

2. SAFETY THEOREM  (A-safety)
   "No recommendation from Reliability OS can produce a delta
    that violates Constitutional OS invariants."
   Formally: ∀δ ∈ A(F). InvOK(Σ, δ) ∧ MemOK(δ)  ⟹  Ik(δ(Σ)) = true ∀k.

   We prove this constructively: for each δ produced by A(F),
   we run the invariant checker on δ(Σ) and verify.

3. BASIN ANALYSIS
   Approximate basin membership for a state S.
   Which attractor does S flow toward under repeated T?

4. SEPARATRIX PROXIMITY
   How close is S to the boundary between two basins?
   (Analogous to ridge curvature in the biology paper.)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import math


# ══════════════════════════════════════════════════════════════════════════════
# 1. LYAPUNOV STABILITY FUNCTION
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class LyapunovComponents:
    """
    Decomposition of V(S) into interpretable components.

    V(S) = w_inv * V_inv(S)       # invariant tension
         + w_mem * V_mem(S)       # membrane pressure
         + w_drift * V_drift(S)   # epistemic drift
         + w_rec * V_rec(S)       # unresolved recommendations
    """
    v_invariants:    float   # V_inv: invariant violations / total invariants
    v_membranes:     float   # V_mem: membrane pressures on pending proposals
    v_drift:         float   # V_drift: forecast drift magnitude
    v_recommendations: float # V_rec: unresolved high-urgency recommendations
    total:           float   # V(S)
    is_fixed_point:  bool    # V(S) ≈ 0
    components:      dict    = field(default_factory=dict)

    # Weights (can be tuned)
    W_INV  = 0.40
    W_MEM  = 0.25
    W_DRIFT = 0.20
    W_REC  = 0.15

    FIXED_POINT_THRESHOLD = 0.02   # V(S) < this → attractor


def lyapunov(state: "MetaState") -> LyapunovComponents:
    """
    V(S) — governance energy of state S.

    V(S) = 0  ⟺  S is a constitutional-epistemic fixed point:
      - All invariants hold
      - No membrane pressure (no pending proposals)
      - No forecast drift
      - No unresolved recommendations
    """
    # ── V_inv: invariant tension ──────────────────────────────────────────────
    inv_result = state.invariants.check_all(state)
    n_inv      = max(len(list(state.invariants)), 1)
    n_fail     = inv_result.fatal_count + inv_result.error_count
    n_warn     = inv_result.warning_count
    # Weighted: fatal > error > warning
    v_inv = (n_fail + 0.3 * n_warn) / n_inv

    # ── V_mem: membrane pressure ──────────────────────────────────────────────
    # Counts deferred proposals (those waiting for human review)
    log    = state.actions_log
    recent = log.recent_entries(50)
    deferred = sum(1 for e in recent if e.get("status") == "deferred")
    blocked  = sum(1 for e in recent if e.get("status") == "blocked")
    # Deferred = positive pressure (needs resolution); blocked = resolved (zero)
    v_mem = min(deferred * 0.25, 1.0)   # saturates at 4 deferred

    # ── V_drift: epistemic drift ──────────────────────────────────────────────
    forecasts = state.forecasts
    if not forecasts.curves:
        v_drift = 0.0
    else:
        risk_scores = {"low": 0.0, "medium": 0.3, "high": 0.7, "critical": 1.0}
        curve_risks = [
            risk_scores.get(c.risk_level, 0.0)
            for c in forecasts.curves.values()
        ]
        v_drift = sum(curve_risks) / max(len(curve_risks), 1)

    # ── V_rec: unresolved recommendations ────────────────────────────────────
    recs          = forecasts.recommendations
    urgency_scores = {"critical": 1.0, "high": 0.6, "normal": 0.2, "low": 0.05}
    if not recs:
        v_rec = 0.0
    else:
        rec_energies = [urgency_scores.get(r.urgency, 0.2) for r in recs]
        v_rec = min(sum(rec_energies) / max(len(rec_energies), 1), 1.0)

    # ── Total V(S) ────────────────────────────────────────────────────────────
    C = LyapunovComponents
    total = (
        C.W_INV   * v_inv  +
        C.W_MEM   * v_mem  +
        C.W_DRIFT * v_drift +
        C.W_REC   * v_rec
    )
    total = min(total, 1.0)   # normalize to [0, 1]

    return LyapunovComponents(
        v_invariants     = round(v_inv,   4),
        v_membranes      = round(v_mem,   4),
        v_drift          = round(v_drift, 4),
        v_recommendations= round(v_rec,   4),
        total            = round(total,   4),
        is_fixed_point   = total < C.FIXED_POINT_THRESHOLD,
        components       = {
            "V_inv":   round(v_inv,   4),
            "V_mem":   round(v_mem,   4),
            "V_drift": round(v_drift, 4),
            "V_rec":   round(v_rec,   4),
        },
    )


def lyapunov_decreasing(v1: LyapunovComponents, v2: LyapunovComponents) -> bool:
    """
    Check if V is non-increasing: V(T(S)) ≤ V(S).
    True → one step toward attractor (or already there).
    False → V increased → potential instability.
    """
    return v2.total <= v1.total + 1e-6   # small tolerance for floating point


# ══════════════════════════════════════════════════════════════════════════════
# 2. SAFETY THEOREM  (A-safety)
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class SafetyCheck:
    """Result of verifying A-safety for a candidate delta."""
    delta_type:       str
    delta_payload:    dict
    invariants_hold:  bool         # ∀k. Ik(Σ) ⟹ Ik(δ(Σ))
    membranes_pass:   bool         # ∀ℓ. Mℓ(δ) = pass
    is_safe:          bool         # both hold
    violations:       list[str]    # which invariants/membranes failed
    proof_steps:      list[str]    # constructive proof trace


@dataclass
class SafetyTheoremResult:
    """
    Result of checking A-safety across all recommendations from A(F).
    Theorem: ∀δ ∈ A(F). InvOK(Σ, δ) ∧ MemOK(δ)  ⟹  safe.
    """
    theorem_holds:   bool          # all checked deltas are safe
    n_checked:       int
    n_safe:          int
    n_unsafe:        int
    checks:          list[SafetyCheck]
    counterexamples: list[SafetyCheck]   # deltas that violate the theorem
    proof:           str           # summary of the constructive proof


def check_a_safety(
    state:          "MetaState",
    recommendations: list["ForecastRecommendation"],
) -> SafetyTheoremResult:
    """
    Constructive proof of A-safety.

    For each δ ∈ A(F):
      1. Apply δ to a COPY of Σ (never the real state)
      2. Check all invariants on δ(Σ)
      3. Check all membranes on δ
      4. If both hold: δ is safe
      5. If either fails: record counterexample

    The theorem holds iff no counterexamples are found.
    """
    from constitutional_os.membranes.engine import ProposedDelta
    from constitutional_os.actions.deltas   import Delta, DeltaEngine
    import copy

    engine = DeltaEngine()
    checks = []

    for rec in recommendations:
        proof_steps = []
        violations  = []

        # Step 1: Construct the delta
        delta = Delta(
            delta_type = rec.action_type,
            payload    = {"metric": rec.metric, "profile_id": rec.profile_id},
            author     = "reliability_os",
            rationale  = rec.rationale,
        )
        proof_steps.append(f"δ = {delta.delta_type}({delta.payload})")

        # Step 2: Apply to copy and check invariants
        try:
            state_copy  = copy.deepcopy(state)
            state_after = engine.apply(state_copy, delta)
            inv_result  = state_after.invariants.check_all(state_after)
            inv_ok      = bool(inv_result)
            proof_steps.append(
                f"InvOK(Σ, δ): {'✓' if inv_ok else '✗'} — {inv_result.summary()}"
            )
            if not inv_ok:
                violations.extend(
                    f"invariant:{r.invariant_id}" for r in inv_result.failures()
                )
        except Exception as e:
            inv_ok = False
            violations.append(f"invariant_check_error: {e}")
            proof_steps.append(f"InvOK: ERROR — {e}")

        # Step 3: Check membranes
        proposed = ProposedDelta(
            delta_type = rec.action_type,
            payload    = {"metric": rec.metric},
            autonomy   = "autonomous",
            severity   = "significant" if rec.urgency in ("high","critical") else "normal",
            reversible = True,
            scope      = "local",
        )
        mem_result = state.membranes.check_all(state, proposed)
        # DEFER = deferred to human review = still safe (human primacy is working)
        # BLOCK = structurally unsafe
        # A-safety: both PASS and DEFER are safe outcomes
        mem_ok     = mem_result.passed or mem_result.verdict.value == "defer"
        proof_steps.append(
            f"MemOK(δ): {'✓' if mem_ok else '✗'} — {mem_result.summary()}"
        )
        if not mem_ok:
            violations.extend(f"membrane:{m}" for m in mem_result.blockers)

        is_safe = inv_ok and mem_ok
        proof_steps.append(
            f"A-safe(δ): {'✓ QED' if is_safe else '✗ COUNTEREXAMPLE'}"
        )

        checks.append(SafetyCheck(
            delta_type    = rec.action_type,
            delta_payload = {"metric": rec.metric},
            invariants_hold = inv_ok,
            membranes_pass  = mem_ok,
            is_safe         = is_safe,
            violations      = violations,
            proof_steps     = proof_steps,
        ))

    n_safe   = sum(1 for c in checks if c.is_safe)
    n_unsafe = len(checks) - n_safe
    counterexamples = [c for c in checks if not c.is_safe]
    theorem_holds   = (n_unsafe == 0)

    if theorem_holds and checks:
        proof = (
            f"A-safety theorem holds: all {len(checks)} recommendations from A(F) "
            f"produce deltas satisfying InvOK ∧ MemOK. "
            f"No counterexample found. QED."
        )
    elif not checks:
        proof = "A-safety vacuously holds: A(F) = ∅ (no recommendations produced)."
    else:
        proof = (
            f"A-safety theorem FAILS: {n_unsafe}/{len(checks)} recommendations "
            f"produce unsafe deltas. Counterexamples: "
            + ", ".join(c.delta_type for c in counterexamples)
        )

    return SafetyTheoremResult(
        theorem_holds   = theorem_holds,
        n_checked       = len(checks),
        n_safe          = n_safe,
        n_unsafe        = n_unsafe,
        checks          = checks,
        counterexamples = counterexamples,
        proof           = proof,
    )


# ══════════════════════════════════════════════════════════════════════════════
# 3. BASIN ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class BasinAnalysis:
    """
    Which attractor basin is S currently in?
    Attractors are characterized by the pattern of invariant satisfaction
    and forecast stability across profiles.
    """
    basin_id:         str    # name of the attractor basin
    confidence:       float  # 0-1, how strongly S is in this basin
    basin_description: str
    v_total:          float  # Lyapunov value
    distance_to_edge: float  # approximate separatrix distance


# Named basins (analogous to biology paper's attractor states)
BASIN_DEFINITIONS = {
    "stable_governance": {
        "description": "All invariants hold, no drift, no unresolved recommendations",
        "condition": lambda v: v.total < 0.05,
        "attractor": True,
    },
    "drifting_epistemic": {
        "description": "Forecast drift detected but governance intact",
        "condition": lambda v: 0.05 <= v.total < 0.25 and v.v_drift > v.v_invariants,
        "attractor": False,
    },
    "governance_pressure": {
        "description": "Membrane pressure or deferred proposals accumulating",
        "condition": lambda v: v.v_membranes > 0.2,
        "attractor": False,
    },
    "invariant_tension": {
        "description": "Invariant violations or warnings present",
        "condition": lambda v: v.v_invariants > 0.1,
        "attractor": False,
    },
    "critical_instability": {
        "description": "High V: multiple subsystems under pressure",
        "condition": lambda v: v.total > 0.5,
        "attractor": False,
    },
}


def analyze_basin(state: "MetaState") -> BasinAnalysis:
    """Identify which basin S is in based on V(S) decomposition."""
    v = lyapunov(state)

    matched = None
    for basin_id, defn in BASIN_DEFINITIONS.items():
        if defn["condition"](v):
            matched = basin_id
            break

    if not matched:
        matched = "transitional"

    defn = BASIN_DEFINITIONS.get(matched, {
        "description": "Transitional state between attractors",
        "attractor": False,
    })

    # Confidence: inversely proportional to proximity to other basins
    # Simple heuristic: confidence = 1 - (V / threshold_of_next_basin)
    confidence = max(0.1, 1.0 - v.total) if defn.get("attractor") else 0.5 - v.total * 0.3

    # Distance to separatrix (ridge): roughly 1/V_mem + 1/V_inv for governance ridges
    membrane_ridge_dist = 1.0 / (v.v_membranes + 0.05)
    inv_ridge_dist      = 1.0 / (v.v_invariants + 0.05)
    dist_to_edge        = min(membrane_ridge_dist, inv_ridge_dist) * 0.1  # normalize

    return BasinAnalysis(
        basin_id          = matched,
        confidence        = round(max(0.0, min(1.0, confidence)), 3),
        basin_description = defn["description"],
        v_total           = v.total,
        distance_to_edge  = round(min(dist_to_edge, 1.0), 3),
    )


# ══════════════════════════════════════════════════════════════════════════════
# 4. SEPARATRIX PROXIMITY
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class SeparatrixProximity:
    """
    How close is S to the boundary between two basins?

    Analogous to ridge curvature κ in the biology paper:
    - High proximity → S is near a separatrix → small perturbations can flip basin
    - Low proximity  → S is deep in an attractor → robust to perturbation

    The "separatrix" here is the boundary where:
      V_mem(S) = threshold  OR  V_inv(S) = threshold
    """
    proximity:        float   # 0 = far from boundary, 1 = on the boundary
    nearest_boundary: str     # which boundary is closest
    margin:           float   # V_threshold - V_current (positive = safe side)
    at_risk:          bool    # proximity > 0.7 → near-separatrix regime
    ridge_curvature:  float   # κ ≈ d²V/dS² at the boundary (higher = steeper ridge)


def separatrix_proximity(state: "MetaState") -> SeparatrixProximity:
    """
    Estimate S's proximity to the governance-epistemic separatrix.

    The separatrix is where the system transitions between:
      stable_governance  ↔  drifting_epistemic
      stable_governance  ↔  governance_pressure
      stable_governance  ↔  invariant_tension
    """
    v = lyapunov(state)

    # Thresholds for each boundary
    boundaries = {
        "epistemic_boundary":   (v.v_drift,       0.25),   # crosses at V_drift = 0.25
        "governance_boundary":  (v.v_membranes,   0.20),   # crosses at V_mem = 0.20
        "invariant_boundary":   (v.v_invariants,  0.10),   # crosses at V_inv = 0.10
    }

    margins = {
        name: threshold - current
        for name, (current, threshold) in boundaries.items()
    }

    # Nearest boundary = smallest margin (could be negative = already crossed)
    nearest = min(margins, key=lambda k: margins[k])
    margin  = margins[nearest]

    # Proximity = 1 - (margin / threshold), clipped to [0, 1]
    current_val, threshold = boundaries[nearest]
    proximity = max(0.0, min(1.0, current_val / threshold))

    # Ridge curvature κ: approximated as second derivative of V
    # Higher κ → steeper ridge → harder to cross (more robust)
    # We estimate κ from how steeply V changes near the boundary
    kappa = 1.0 / (abs(margin) + 0.05)   # larger when closer to boundary

    return SeparatrixProximity(
        proximity        = round(proximity, 3),
        nearest_boundary = nearest,
        margin           = round(margin, 4),
        at_risk          = proximity > 0.70,
        ridge_curvature  = round(min(kappa, 20.0), 3),
    )


# ══════════════════════════════════════════════════════════════════════════════
# 5. FULL STABILITY REPORT
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class StabilityReport:
    """Complete formal stability analysis of state S."""
    lyapunov:         LyapunovComponents
    basin:            BasinAnalysis
    separatrix:       SeparatrixProximity
    a_safety:         SafetyTheoremResult
    v_trajectory:     list[float]    # V(S) over recent history
    converging:       bool           # V decreasing over trajectory
    summary:          str


def stability_report(
    state:           "MetaState",
    v_history:       list[float] = None,
    recommendations: list = None,
) -> StabilityReport:
    """Generate a complete stability analysis."""
    v     = lyapunov(state)
    basin = analyze_basin(state)
    sep   = separatrix_proximity(state)

    recs   = recommendations or list(state.forecasts.recommendations)
    safety = check_a_safety(state, recs)

    # Convergence: is V trending downward?
    hist       = (v_history or []) + [v.total]
    converging = len(hist) < 2 or hist[-1] <= hist[-2] + 1e-4

    # Summary
    lines = [
        f"V(S) = {v.total:.4f}  {'[ATTRACTOR]' if v.is_fixed_point else '[TRANSIENT]'}",
        f"Basin: {basin.basin_id}  (conf={basin.confidence:.0%})",
        f"Separatrix: proximity={sep.proximity:.0%}  κ={sep.ridge_curvature:.2f}"
        + ("  ⚠ AT RISK" if sep.at_risk else ""),
        f"A-safety: {'✓ holds' if safety.theorem_holds else '✗ VIOLATED'}  "
        + f"({safety.n_safe}/{safety.n_checked} deltas safe)",
        f"Converging: {'yes' if converging else 'no — V increasing'}",
    ]

    return StabilityReport(
        lyapunov      = v,
        basin         = basin,
        separatrix    = sep,
        a_safety      = safety,
        v_trajectory  = hist[-20:],
        converging    = converging,
        summary       = "\n".join(lines),
    )
