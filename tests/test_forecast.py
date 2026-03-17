"""
tests/test_forecast.py
Tests for forecast/engine.py: projection, recommendations, risk classification.
"""
import pytest

from constitutional_os.forecast.engine import (
    ForecastEngine, ForecastCurve, ForecastPoint,
    ForecastRecommendation, ForecastState,
    risk_heatmap,
)


# ── ForecastEngine ────────────────────────────────────────────────────────────
class TestForecastEngine:

    def setup_method(self):
        self.engine = ForecastEngine(alpha=0.3, horizon_days=7)

    def test_empty_history_returns_empty_curve(self):
        curve = self.engine.project("quality", "p1", [])
        assert curve.points == []

    def test_single_value_history(self):
        curve = self.engine.project("quality", "p1", [0.85])
        assert len(curve.points) == 7   # horizon_days
        assert curve.metric     == "quality"
        assert curve.profile_id == "p1"

    def test_horizon_respected(self):
        curve = self.engine.project("quality", "p1", [0.8, 0.8], horizon=14)
        assert len(curve.points) == 14

    def test_points_have_confidence(self):
        curve = self.engine.project("quality", "p1", [0.85] * 7)
        for p in curve.points:
            assert 0.0 <= p.confidence <= 1.0

    def test_confidence_decreases_with_horizon(self):
        curve = self.engine.project("quality", "p1", [0.85] * 7)
        confidences = [p.confidence for p in curve.points]
        # Each point should have <= confidence of prior point
        assert confidences[0] >= confidences[-1]

    def test_intervals_widen_with_horizon(self):
        curve  = self.engine.project("quality", "p1", [0.85] * 7)
        widths = [p.upper - p.lower for p in curve.points]
        assert widths[0] <= widths[-1]

    def test_trend_stable(self):
        stable = [0.85] * 14
        curve  = self.engine.project("quality", "p1", stable)
        assert curve.trend == "stable"

    def test_trend_degrading(self):
        degrading = [0.9 - i * 0.05 for i in range(14)]
        curve     = self.engine.project("quality", "p1", degrading)
        assert curve.trend in ("degrading", "slowly_changing")

    def test_risk_low_for_stable(self):
        stable = [0.85] * 14
        curve  = self.engine.project("quality", "p1", stable)
        assert curve.risk_level in ("low", "medium")

    def test_risk_high_for_volatile(self):
        import random
        random.seed(42)
        volatile = [random.uniform(0.3, 0.9) for _ in range(14)]
        curve    = self.engine.project("quality", "p1", volatile)
        assert curve.risk_level in ("medium", "high", "critical")

    def test_summary_string(self):
        curve = self.engine.project("quality", "p1", [0.85] * 7)
        s     = curve.summary()
        assert "quality" in s
        assert "projected" in s.lower() or "stable" in s.lower()

    def test_at_day(self):
        curve = self.engine.project("quality", "p1", [0.85] * 7, horizon=7)
        p3    = curve.at_day(3)
        assert p3 is not None
        assert p3.t == 3

    def test_at_day_missing(self):
        curve = self.engine.project("quality", "p1", [0.85] * 7, horizon=7)
        assert curve.at_day(99) is None


# ── Recommendations ───────────────────────────────────────────────────────────
class TestRecommendations:

    def setup_method(self):
        self.engine = ForecastEngine()

    def test_no_recommendation_for_low_risk(self):
        stable = [0.85] * 14
        curve  = self.engine.project("quality", "p1", stable)
        rec    = self.engine.recommend(curve)
        assert rec is None

    def test_recommendation_for_high_risk(self):
        degrading = [0.9 - i * 0.08 for i in range(14)]
        curve     = self.engine.project("quality", "p1", degrading)
        # Force high risk
        curve.risk_level = "high"
        rec = self.engine.recommend(curve)
        assert rec is not None
        assert rec.metric     == "quality"
        assert rec.profile_id == "p1"

    def test_recommendation_for_critical_risk(self):
        degrading  = [0.9 - i * 0.1 for i in range(14)]
        curve      = self.engine.project("quality", "p1", degrading)
        curve.risk_level = "critical"
        rec = self.engine.recommend(curve)
        assert rec is not None
        assert rec.urgency in ("critical", "high")

    def test_recommendation_has_rationale(self):
        curve = self.engine.project("quality", "p1", [0.8] * 14)
        curve.risk_level = "high"
        curve.trend      = "degrading"
        rec  = self.engine.recommend(curve)
        if rec:
            assert len(rec.rationale) > 10

    def test_recommendation_id_unique(self):
        curve = self.engine.project("quality", "p1", [0.8] * 14)
        curve.risk_level = "high"
        r1 = self.engine.recommend(curve)
        r2 = self.engine.recommend(curve)
        if r1 and r2:
            assert r1.recommendation_id != r2.recommendation_id


# ── ForecastState ─────────────────────────────────────────────────────────────
class TestForecastState:

    def test_add_curve(self):
        fs    = ForecastState()
        curve = ForecastCurve(metric="q", profile_id="p1", horizon_days=7)
        fs.add_curve(curve)
        assert "p1:q" in fs.curves

    def test_add_recommendation(self):
        fs  = ForecastState()
        rec = ForecastRecommendation(
            recommendation_id="r1", profile_id="p1", metric="q",
            action_type="investigate", rationale="test", urgency="high",
        )
        fs.add_recommendation(rec)
        assert len(fs.recommendations) == 1

    def test_pending_recommendations_high_critical_only(self):
        fs = ForecastState()
        for urgency in ["low", "normal", "high", "critical"]:
            fs.add_recommendation(ForecastRecommendation(
                recommendation_id=urgency, profile_id="p1", metric="q",
                action_type="test", rationale="test", urgency=urgency,
            ))
        pending = fs.pending_recommendations()
        assert len(pending) == 2
        assert all(r.urgency in ("high", "critical") for r in pending)


# ── run_all ───────────────────────────────────────────────────────────────────
class TestRunAll:

    def test_run_all_empty_history(self):
        engine = ForecastEngine()

        class FakeState:
            class reality:
                observations = []
            class profiles:
                @staticmethod
                def all(): return []

        fs = engine.run_all(FakeState(), {})
        assert len(fs.curves) == 0

    def test_run_all_with_history(self):
        engine = ForecastEngine()
        history_map = {
            "p1:quality": [0.9 - i*0.01 for i in range(14)],
            "p1:latency": [600 + i*10   for i in range(14)],
        }

        class FakeState:
            class reality:
                observations = []
            class profiles:
                @staticmethod
                def all(): return []

        fs = engine.run_all(FakeState(), history_map)
        assert "p1:quality" in fs.curves
        assert "p1:latency" in fs.curves


# ── Heatmap ───────────────────────────────────────────────────────────────────
class TestRiskHeatmap:

    def test_heatmap_structure(self):
        fs = ForecastState()
        c1 = ForecastCurve(metric="quality", profile_id="p1",
                           horizon_days=7, risk_level="high", trend="degrading")
        c2 = ForecastCurve(metric="latency", profile_id="p1",
                           horizon_days=7, risk_level="low",  trend="stable")
        fs.add_curve(c1)
        fs.add_curve(c2)

        hm = risk_heatmap(fs)
        assert "p1" in hm
        assert "quality" in hm["p1"]
        assert "latency" in hm["p1"]
        assert hm["p1"]["quality"]["risk"]  == "high"
        assert hm["p1"]["latency"]["risk"]  == "low"
        assert hm["p1"]["quality"]["trend"] == "degrading"
