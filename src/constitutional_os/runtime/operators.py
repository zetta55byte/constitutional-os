"""
runtime/operators.py

The two formal operators and their composition.

  E: Σ → (Σ', δ_rec)        Epistemic operator (Reliability OS)
  G: (Σ, δ)  → Σ'           Governance operator (Constitutional OS)
  Φ = G ∘ E: Σ → Σ'         Combined step

Fixed point: Σ* such that Φ(Σ*) = Σ*
  ↔ E recommends no δ that G admits, or all recommended δ are blocked/vetoed.
  These are constitutional-epistemic attractors.
"""

from __future__ import annotations
from dataclasses import dataclass, replace
from typing import Optional
from constitutional_os.runtime.state import MetaState, ReliabilityState, ConstitutionalState
from constitutional_os.runtime.events import ActionRecommended


# ── Epistemic operator E ──────────────────────────────────────────────────────
@dataclass
class EpistemicResult:
    """Output of E(Σ): updated Σ_R and an optional recommended δ."""
    new_reliability:    ReliabilityState
    recommendation:     Optional[ActionRecommended]
    eval_summaries:     list[str] = None
    drift_alerts:       list[str] = None


def epistemic_step(
    state:        MetaState,
    eval_runner:  "EvalRunner",
    forecast_eng: "ForecastEngine",
    history_map:  dict,
) -> EpistemicResult:
    """
    E(Σ) = (Σ_R', δ_rec)

    1. Run eval bundles for all profiles → update H
    2. Update forecast curves → update F
    3. Derive recommended δ from F (if any)
    """
    from constitutional_os.evals.runner   import EvalRunner
    from constitutional_os.forecast.engine import ForecastEngine

    R = state.reliability
    eval_summaries = []
    drift_alerts   = []

    # Step 1: Run evals for all profiles
    for profile in R.profiles.all():
        for eval_spec in profile.evals:
            report = eval_runner.run(eval_spec.bundle_id, state, profile.id)
            R.eval_history.append(report)
            eval_summaries.append(f"{profile.id}/{eval_spec.bundle_id}: {report.summary}")
            if not report.passed:
                drift_alerts.append(f"FAIL {profile.id}/{eval_spec.bundle_id}")

    # Step 2: Run forecasts
    new_forecasts = forecast_eng.run_all(state, history_map)

    # Step 3: Find highest-urgency recommendation
    recommendation = None
    if new_forecasts.recommendations:
        critical = [r for r in new_forecasts.recommendations if r.urgency == "critical"]
        high     = [r for r in new_forecasts.recommendations if r.urgency == "high"]
        candidates = critical or high
        if candidates:
            best = max(candidates, key=lambda r: r.confidence)
            recommendation = ActionRecommended(
                action_id   = best.recommendation_id,
                delta_type  = best.action_type,
                payload     = {"metric": best.metric, "profile_id": best.profile_id},
                rationale   = best.rationale,
                urgency     = best.urgency,
                confidence  = best.confidence,
                profile_id  = best.profile_id,
                forecast_id = best.recommendation_id,
            )

    # Build updated Σ_R
    new_R = ReliabilityState(
        profiles     = R.profiles,
        eval_history = R.eval_history,
        forecasts    = new_forecasts,
    )

    return EpistemicResult(
        new_reliability = new_R,
        recommendation  = recommendation,
        eval_summaries  = eval_summaries,
        drift_alerts    = drift_alerts,
    )


# ── Governance operator G ─────────────────────────────────────────────────────
@dataclass
class GovernanceResult:
    """Output of G(Σ, δ): updated Σ_C and verdict."""
    new_constitutional: ConstitutionalState
    verdict:            str   # admitted | blocked | deferred | no_delta
    proposal_id:        str   = ""
    blockers:           list  = None
    deferrals:          list  = None


def governance_step(
    state:       MetaState,
    dispatcher:  "EventDispatcher",
    delta:       Optional[ActionRecommended],
) -> GovernanceResult:
    """
    G(Σ, δ) = Σ_C'

    If δ is None: no change, verdict = no_delta.
    Otherwise:
      1. Check invariants I(Σ, δ)
      2. Check membranes M(Σ, δ)
      3. If passes: propose → ratify → execute → log to L
      4. If blocked: log rejection
      5. If deferred: open human veto window
    """
    from constitutional_os.membranes.engine import ProposedDelta, MembraneVerdict
    from constitutional_os.actions.deltas   import ContinuityLog, LogEntry
    import uuid

    C = state.constitutional

    if delta is None:
        return GovernanceResult(
            new_constitutional = C,
            verdict            = "no_delta",
        )

    # Step 1: Invariant check
    inv_result = state.invariants.check_all(state)
    if not inv_result:
        return GovernanceResult(
            new_constitutional = C,
            verdict            = "blocked",
            blockers           = [f"invariant:{r.invariant_id}" for r in inv_result.failures()],
        )

    # Step 2: Membrane check
    proposed = ProposedDelta(
        delta_type = delta.delta_type,
        payload    = delta.payload,
        autonomy   = "autonomous",
        severity   = "significant" if delta.urgency in ("high","critical") else "normal",
        reversible = True,
        scope      = "local",
        requester  = "reliability_os",
    )
    mem_result = state.membranes.check_all(state, proposed)

    if mem_result.verdict == MembraneVerdict.BLOCK:
        return GovernanceResult(
            new_constitutional = C,
            verdict            = "blocked",
            blockers           = mem_result.blockers,
        )

    if mem_result.verdict == MembraneVerdict.DEFER:
        # Log the deferral — human must act
        proposal_id = str(uuid.uuid4())[:8]
        entry = LogEntry(
            seq=0, delta_id=delta.action_id, delta_type=delta.delta_type,
            fingerprint="", state_version=state.version,
            proposal_id=proposal_id, status="deferred_for_human",
            author="reliability_os", rationale=delta.rationale,
        )
        C.actions_log.append(entry)
        return GovernanceResult(
            new_constitutional = C,
            verdict            = "deferred",
            proposal_id        = proposal_id,
            deferrals          = mem_result.deferrals,
        )

    # Step 3: Ratify and log to L
    proposal_id = str(uuid.uuid4())[:8]
    entry = LogEntry(
        seq=0, delta_id=delta.action_id, delta_type=delta.delta_type,
        fingerprint=delta.action_id, state_version=state.version,
        proposal_id=proposal_id, status="ratified_and_executed",
        author="reliability_os", rationale=delta.rationale,
    )
    C.actions_log.append(entry)

    return GovernanceResult(
        new_constitutional = C,
        verdict            = "admitted",
        proposal_id        = proposal_id,
    )


# ── Φ = G ∘ E : the combined step ────────────────────────────────────────────
@dataclass
class PhiResult:
    """
    Output of Φ(Σ) = G(E(Σ)).
    The complete epistemic-governance cycle.
    """
    new_state:          MetaState
    epistemic_result:   EpistemicResult
    governance_result:  GovernanceResult
    is_fixed_point:     bool  = False   # True if Φ(Σ) ≈ Σ (attractor reached)


def phi(
    state:        MetaState,
    eval_runner:  "EvalRunner",
    forecast_eng: "ForecastEngine",
    dispatcher:   "EventDispatcher",
    history_map:  dict,
) -> PhiResult:
    """
    Φ(Σ) = G(E(Σ))

    1. E(Σ)  → (Σ_R', δ_rec)
    2. G(Σ, δ_rec) → Σ_C'
    3. Σ' = (Σ_R', Σ_C', Σ_X)
    4. Check fixed-point condition: δ_rec is None or blocked/deferred
    """
    # Epistemic step
    e_result = epistemic_step(state, eval_runner, forecast_eng, history_map)

    # Update Σ with new Σ_R
    state = state.with_reliability(e_result.new_reliability)

    # Governance step
    g_result = governance_step(state, dispatcher, e_result.recommendation)

    # Update Σ with new Σ_C
    state = state.with_constitutional(g_result.new_constitutional)

    # Fixed-point check: no delta recommended, or all blocked/deferred
    is_fp = (
        e_result.recommendation is None
        or g_result.verdict in ("blocked", "deferred", "no_delta")
    )

    return PhiResult(
        new_state         = state,
        epistemic_result  = e_result,
        governance_result = g_result,
        is_fixed_point    = is_fp,
    )


# ── Phi with Lyapunov tracking ────────────────────────────────────────────────
def phi_with_stability(
    state:        "MetaState",
    eval_runner:  "EvalRunner",
    forecast_eng: "ForecastEngine",
    dispatcher:   "EventDispatcher",
    history_map:  dict,
    v_history:    list = None,
) -> tuple["PhiResult", "StabilityReport"]:
    """
    Run Φ and compute the full stability report.
    Returns (PhiResult, StabilityReport).
    """
    from constitutional_os.runtime.theory import stability_report, lyapunov

    v_before = lyapunov(state)
    result   = phi(state, eval_runner, forecast_eng, dispatcher, history_map)

    v_hist = (v_history or []) + [v_before.total]
    report = stability_report(
        result.new_state,
        v_history       = v_hist,
        recommendations = list(result.new_state.forecasts.recommendations),
    )

    return result, report
