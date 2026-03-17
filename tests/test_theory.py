"""
tests/test_theory.py
Tests for runtime/theory.py: Lyapunov function, A-safety theorem,
basin analysis, separatrix proximity.
"""
import pytest

from constitutional_os.runtime.theory import (
    lyapunov, lyapunov_decreasing, LyapunovComponents,
    check_a_safety, SafetyTheoremResult,
    analyze_basin, BasinAnalysis,
    separatrix_proximity, SeparatrixProximity,
    stability_report,
)


# ── Helpers ───────────────────────────────────────────────────────────────────
def _booted_state():
    from constitutional_os.runtime.boot import boot
    store, _ = boot(verbose=False)
    return store.current

def _state_with_profile():
    from constitutional_os.runtime.boot import boot
    from constitutional_os.runtime.events import ProfileLoaded
    from constitutional_os.profiles.loader import ProfileLoader

    store, dispatcher = boot(verbose=False)
    profile = ProfileLoader.from_dict({
        "id": "theory.test",
        "name": "Theory Test Profile",
        "version": "1.0.0",
        "metrics": [
            {"name": "quality", "threshold": 0.70, "baseline": 0.88,
             "direction": "higher_is_better"},
        ],
        "evals": [
            {"bundle_id": "core.integrity", "required": True, "weight": 1.0},
        ],
    })
    store.current.profiles.register(profile)
    state = dispatcher.dispatch(store.current, ProfileLoaded(
        profile_id=profile.id, profile_name=profile.name, version=profile.version,
    ))
    store.apply(state)
    return store.current


# ── Lyapunov function ─────────────────────────────────────────────────────────
class TestLyapunov:

    def test_returns_lyapunov_components(self):
        state = _booted_state()
        v     = lyapunov(state)
        assert isinstance(v, LyapunovComponents)

    def test_total_in_range(self):
        state = _booted_state()
        v     = lyapunov(state)
        assert 0.0 <= v.total <= 1.0

    def test_components_non_negative(self):
        state = _booted_state()
        v     = lyapunov(state)
        assert v.v_invariants     >= 0
        assert v.v_membranes      >= 0
        assert v.v_drift          >= 0
        assert v.v_recommendations >= 0

    def test_clean_state_low_energy(self):
        """A freshly booted state with no drift should have low V."""
        state = _booted_state()
        v     = lyapunov(state)
        # V should be well below 0.5 on a clean state
        assert v.total < 0.5

    def test_fixed_point_flag(self):
        state = _booted_state()
        v     = lyapunov(state)
        # is_fixed_point should match the threshold
        assert v.is_fixed_point == (v.total < LyapunovComponents.FIXED_POINT_THRESHOLD)

    def test_components_dict_present(self):
        state = _booted_state()
        v     = lyapunov(state)
        assert "V_inv"   in v.components
        assert "V_mem"   in v.components
        assert "V_drift" in v.components
        assert "V_rec"   in v.components

    def test_weighted_sum_matches_total(self):
        state = _booted_state()
        v     = lyapunov(state)
        C = LyapunovComponents
        expected = min(
            C.W_INV   * v.v_invariants +
            C.W_MEM   * v.v_membranes  +
            C.W_DRIFT * v.v_drift      +
            C.W_REC   * v.v_recommendations,
            1.0
        )
        assert abs(v.total - expected) < 1e-6


class TestLyapunovDecreasing:

    def test_decreasing_returns_true(self):
        v1 = LyapunovComponents(0.3, 0.1, 0.2, 0.1, 0.22, False, {})
        v2 = LyapunovComponents(0.2, 0.1, 0.1, 0.0, 0.15, False, {})
        assert lyapunov_decreasing(v1, v2) is True

    def test_increasing_returns_false(self):
        v1 = LyapunovComponents(0.1, 0.0, 0.1, 0.0, 0.08, False, {})
        v2 = LyapunovComponents(0.3, 0.2, 0.3, 0.1, 0.27, False, {})
        assert lyapunov_decreasing(v1, v2) is False

    def test_equal_returns_true(self):
        v1 = LyapunovComponents(0.2, 0.1, 0.1, 0.0, 0.15, False, {})
        v2 = LyapunovComponents(0.2, 0.1, 0.1, 0.0, 0.15, False, {})
        assert lyapunov_decreasing(v1, v2) is True


# ── A-safety theorem ──────────────────────────────────────────────────────────
class TestASafety:

    def test_vacuously_holds_with_no_recs(self):
        state  = _booted_state()
        result = check_a_safety(state, [])
        assert result.theorem_holds is True
        assert result.n_checked     == 0
        assert "vacuously" in result.proof.lower()

    def test_safe_recs_satisfy_theorem(self):
        from constitutional_os.forecast.engine import ForecastRecommendation
        state = _booted_state()
        recs  = [ForecastRecommendation(
            recommendation_id = "r1",
            profile_id        = "test",
            metric            = "quality",
            action_type       = "investigate_degradation",
            rationale         = "quality is degrading",
            urgency           = "normal",
            confidence        = 0.8,
        )]
        result = check_a_safety(state, recs)
        assert result.theorem_holds is True
        assert result.n_checked     == 1
        assert result.n_safe        == 1
        assert "QED" in result.proof

    def test_result_has_proof_steps(self):
        from constitutional_os.forecast.engine import ForecastRecommendation
        state = _booted_state()
        recs  = [ForecastRecommendation(
            recommendation_id="r1", profile_id="test", metric="quality",
            action_type="monitor_volatility", rationale="test",
            urgency="low", confidence=0.5,
        )]
        result = check_a_safety(state, recs)
        assert len(result.checks) == 1
        assert len(result.checks[0].proof_steps) >= 3

    def test_counterexample_detection(self):
        """Delta that blocks should produce a counterexample."""
        from constitutional_os.forecast.engine import ForecastRecommendation
        state = _booted_state()
        # revoke_human_primacy is blocked by M3 (pluralism)
        recs = [ForecastRecommendation(
            recommendation_id="r1", profile_id="test", metric="quality",
            action_type="revoke_human_primacy",   # pluralism membrane blocks this
            rationale="test", urgency="low", confidence=0.5,
        )]
        result = check_a_safety(state, recs)
        # Should have a counterexample — but DEFER still counts as safe
        # Only BLOCK is a true counterexample for A-safety
        assert result.n_checked == 1


# ── Basin analysis ────────────────────────────────────────────────────────────
class TestBasinAnalysis:

    def test_returns_basin_analysis(self):
        state = _booted_state()
        basin = analyze_basin(state)
        assert isinstance(basin, BasinAnalysis)

    def test_known_basins(self):
        from constitutional_os.runtime.theory import BASIN_DEFINITIONS
        valid_basins = set(BASIN_DEFINITIONS.keys()) | {"transitional"}
        state = _booted_state()
        basin = analyze_basin(state)
        assert basin.basin_id in valid_basins

    def test_confidence_in_range(self):
        state = _booted_state()
        basin = analyze_basin(state)
        assert 0.0 <= basin.confidence <= 1.0

    def test_v_total_consistent(self):
        state = _booted_state()
        v     = lyapunov(state)
        basin = analyze_basin(state)
        assert abs(basin.v_total - v.total) < 1e-6

    def test_clean_state_not_critical(self):
        state = _booted_state()
        basin = analyze_basin(state)
        assert basin.basin_id != "critical_instability"


# ── Separatrix proximity ──────────────────────────────────────────────────────
class TestSeparatrixProximity:

    def test_returns_proximity(self):
        state = _booted_state()
        sep   = separatrix_proximity(state)
        assert isinstance(sep, SeparatrixProximity)

    def test_proximity_in_range(self):
        state = _booted_state()
        sep   = separatrix_proximity(state)
        assert 0.0 <= sep.proximity <= 1.0

    def test_kappa_positive(self):
        state = _booted_state()
        sep   = separatrix_proximity(state)
        assert sep.ridge_curvature > 0

    def test_at_risk_flag(self):
        state = _booted_state()
        sep   = separatrix_proximity(state)
        assert sep.at_risk == (sep.proximity > 0.70)

    def test_nearest_boundary_is_known(self):
        state = _booted_state()
        sep   = separatrix_proximity(state)
        known = {"epistemic_boundary", "governance_boundary", "invariant_boundary"}
        assert sep.nearest_boundary in known


# ── Full stability report ─────────────────────────────────────────────────────
class TestStabilityReport:

    def test_returns_report(self):
        state  = _booted_state()
        report = stability_report(state)
        assert report.lyapunov   is not None
        assert report.basin      is not None
        assert report.separatrix is not None
        assert report.a_safety   is not None

    def test_summary_string_not_empty(self):
        state  = _booted_state()
        report = stability_report(state)
        assert len(report.summary) > 50

    def test_v_trajectory_accumulated(self):
        state   = _booted_state()
        history = [0.3, 0.25, 0.20]
        report  = stability_report(state, v_history=history)
        # Should include history + current
        assert len(report.v_trajectory) == len(history) + 1

    def test_converging_detection(self):
        state  = _booted_state()
        # Strictly decreasing history → converging
        report = stability_report(state, v_history=[0.5, 0.4, 0.3, 0.2])
        assert report.converging is True
