"""
tests/test_evals.py
Tests for evals/runner.py: eval bundles, runner, reports, history.
"""
import pytest

from constitutional_os.evals.runner import (
    EvalBundle, EvalCheck, EvalRunner, EvalReport,
    EvalHistory, Finding, FindingSeverity,
)
from constitutional_os.profiles.loader import ProfileLoader, ProfileRegistry
from constitutional_os.invariants.engine import load_default_invariants
from constitutional_os.membranes.engine  import load_default_membranes
from constitutional_os.actions.deltas    import ContinuityLog
from constitutional_os.forecast.engine   import ForecastState


# ── Minimal state for evals ───────────────────────────────────────────────────
def _make_state(with_profile=False):
    from constitutional_os.runtime.state import MetaState, ReliabilityState, ConstitutionalState, RealityState

    reg = ProfileRegistry()
    if with_profile:
        p = ProfileLoader.from_dict({
            "id": "test.eval",
            "name": "Eval Test Profile",
            "version": "1.0.0",
            "metrics": [
                {"name": "quality", "threshold": 0.70, "baseline": 0.88,
                 "direction": "higher_is_better"},
            ],
            "evals": [
                {"bundle_id": "core.integrity", "required": True, "weight": 1.0},
            ],
        })
        reg.register(p)

    from constitutional_os.evals.runner import EvalHistory as EH
    return MetaState(
        reliability    = ReliabilityState(
            profiles=reg, eval_history=EH(), forecasts=ForecastState(),
        ),
        constitutional = ConstitutionalState(
            invariants=load_default_invariants(),
            membranes=load_default_membranes(),
            actions_log=ContinuityLog(),
        ),
        reality        = __import__("runtime.state", fromlist=["RealityState"]).RealityState(),
        status         = "running",
    )


# ── Finding ───────────────────────────────────────────────────────────────────
class TestFinding:

    def test_fields(self):
        f = Finding(
            check_id="c1", passed=True,
            severity=FindingSeverity.LOW, message="ok",
        )
        assert f.check_id == "c1"
        assert f.passed   == True

    def test_failed_finding(self):
        f = Finding(
            check_id="c1", passed=False,
            severity=FindingSeverity.CRITICAL,
            message="broken", recommendation="fix it",
        )
        assert f.passed          == False
        assert f.severity        == FindingSeverity.CRITICAL
        assert f.recommendation  == "fix it"


# ── EvalBundle ────────────────────────────────────────────────────────────────
class TestEvalBundle:

    def test_add_check(self):
        b = EvalBundle(id="test.bundle", name="Test Bundle")
        b.add_check(EvalCheck(
            id="c1", name="Check 1",
            fn=lambda s, p: Finding("c1", True),
        ))
        assert len(b.checks) == 1

    def test_default_threshold(self):
        b = EvalBundle(id="test.bundle", name="Test Bundle")
        assert b.pass_threshold == 0.8


# ── EvalRunner ────────────────────────────────────────────────────────────────
class TestEvalRunner:

    def setup_method(self):
        self.runner = EvalRunner()
        self.state  = _make_state(with_profile=True)

    def test_default_bundles_registered(self):
        assert self.runner.get("core.integrity") is not None
        assert self.runner.get("core.health")    is not None

    def test_run_core_integrity_with_profile(self):
        report = self.runner.run("core.integrity", self.state, "test.eval")
        assert isinstance(report, EvalReport)
        assert report.bundle_id  == "core.integrity"
        assert report.profile_id == "test.eval"
        assert 0.0 <= report.score <= 1.0

    def test_run_core_health(self):
        report = self.runner.run("core.health", self.state)
        assert isinstance(report, EvalReport)
        assert report.bundle_id == "core.health"

    def test_run_missing_bundle(self):
        report = self.runner.run("nonexistent.bundle", self.state)
        assert report.passed == False
        assert "not found" in report.summary.lower()

    def test_report_has_findings(self):
        report = self.runner.run("core.integrity", self.state, "test.eval")
        assert len(report.findings) > 0

    def test_report_to_dict(self):
        report = self.runner.run("core.integrity", self.state, "test.eval")
        d      = report.to_dict()
        assert "bundle_id"  in d
        assert "score"      in d
        assert "passed"     in d
        assert "findings"   in d
        assert "summary"    in d

    def test_critical_failure_forces_fail(self):
        """A single critical failure should force overall pass=False."""
        bundle = EvalBundle(
            id="test.critical", name="Critical Test",
            pass_threshold=0.0,   # would pass on score alone
        )
        bundle.add_check(EvalCheck(
            id="crit", name="Critical Check",
            fn=lambda s, p: Finding(
                "crit", False,
                FindingSeverity.CRITICAL, "critical failure"
            ),
            severity=FindingSeverity.CRITICAL,
        ))
        self.runner.register(bundle)
        report = self.runner.run("test.critical", self.state)
        assert report.passed == False

    def test_weighted_score(self):
        """Score should be weighted by check weights."""
        bundle = EvalBundle(id="test.weighted", name="Weighted", pass_threshold=0.5)
        bundle.add_check(EvalCheck(
            id="heavy", name="Heavy",
            fn=lambda s, p: Finding("heavy", True),
            weight=3.0,
        ))
        bundle.add_check(EvalCheck(
            id="light", name="Light",
            fn=lambda s, p: Finding("light", False),
            weight=1.0,
        ))
        self.runner.register(bundle)
        report = self.runner.run("test.weighted", self.state)
        # 3/(3+1) = 0.75 score → should pass at threshold 0.5
        assert abs(report.score - 0.75) < 0.01
        assert report.passed

    def test_run_all_for_profile(self):
        reports = self.runner.run_all_for_profile(self.state, "test.eval")
        assert len(reports) == 1   # profile has one eval spec
        assert reports[0].bundle_id == "core.integrity"

    def test_run_all_missing_profile_returns_empty(self):
        reports = self.runner.run_all_for_profile(self.state, "nonexistent")
        assert reports == []


# ── EvalHistory ───────────────────────────────────────────────────────────────
class TestEvalHistory:

    def setup_method(self):
        self.hist   = EvalHistory()
        self.runner = EvalRunner()
        self.state  = _make_state(with_profile=True)

    def _make_report(self, bundle_id="core.integrity", profile_id="test.eval", score=0.8):
        return EvalReport(
            bundle_id=bundle_id, profile_id=profile_id,
            score=score, passed=score >= 0.8,
            findings=[], summary=f"score={score}",
        )

    def test_append_and_len(self):
        assert len(self.hist) == 0
        self.hist.append(self._make_report())
        assert len(self.hist) == 1

    def test_for_profile(self):
        self.hist.append(self._make_report(profile_id="p1"))
        self.hist.append(self._make_report(profile_id="p2"))
        self.hist.append(self._make_report(profile_id="p1"))
        assert len(self.hist.for_profile("p1")) == 2
        assert len(self.hist.for_profile("p2")) == 1

    def test_for_bundle(self):
        self.hist.append(self._make_report(bundle_id="b1"))
        self.hist.append(self._make_report(bundle_id="b2"))
        assert len(self.hist.for_bundle("b1")) == 1

    def test_latest(self):
        for i in range(15):
            self.hist.append(self._make_report(score=i/15))
        latest = self.hist.latest(5)
        assert len(latest) == 5

    def test_trend(self):
        scores = [0.9, 0.85, 0.80, 0.75, 0.70]
        for s in scores:
            self.hist.append(self._make_report(
                bundle_id="core.integrity", profile_id="test.eval", score=s
            ))
        trend = self.hist.trend("core.integrity", "test.eval")
        assert trend == scores
