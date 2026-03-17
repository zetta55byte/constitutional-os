"""
tests/test_invariants.py
Tests for invariants/engine.py: registration, checking, severity, library.
"""
import pytest

from constitutional_os.invariants.engine import (
    Invariant, InvariantSet, InvariantResult,
    InvariantSeverity, InvariantSetResult,
    load_default_invariants,
)


# ── Helpers ───────────────────────────────────────────────────────────────────
def _make_passing(inv_id="test.pass"):
    return Invariant(
        id="test.pass", name="Always Pass",
        description="Always returns true",
        fn=lambda state: InvariantResult(inv_id, True),
        severity=InvariantSeverity.ERROR,
    )

def _make_failing(inv_id="test.fail", severity=InvariantSeverity.ERROR):
    return Invariant(
        id=inv_id, name="Always Fail",
        description="Always returns false",
        fn=lambda state: InvariantResult(inv_id, False, severity, "always fails"),
        severity=severity,
    )

def _dummy_state():
    """Minimal state-like object for invariant checks."""
    class S:
        version = 1
        status  = "running"
        class actions_log:
            _tampered = False
            @staticmethod
            def recent_entries(n=20): return []
        class eval_history:
            _tampered = False
        class invariants:
            @staticmethod
            def check_all(s): return InvariantSetResult(all_passed=True)
        class profiles:
            @staticmethod
            def all(): return []
        class forecasts:
            recommendations = []
            curves = {}
        class membranes:
            pass
    return S()


# ── InvariantResult ───────────────────────────────────────────────────────────
class TestInvariantResult:

    def test_truthy_when_passed(self):
        r = InvariantResult("i1", True)
        assert bool(r) is True

    def test_falsy_when_failed(self):
        r = InvariantResult("i1", False, reason="broke")
        assert bool(r) is False

    def test_fields(self):
        r = InvariantResult("i1", False, InvariantSeverity.FATAL, "bad")
        assert r.invariant_id == "i1"
        assert r.passed       == False
        assert r.severity     == InvariantSeverity.FATAL
        assert r.reason       == "bad"


# ── InvariantSet ──────────────────────────────────────────────────────────────
class TestInvariantSet:

    def test_register_and_get(self):
        s   = InvariantSet()
        inv = _make_passing()
        s.register(inv)
        assert s.get("test.pass") is inv

    def test_len(self):
        s = InvariantSet()
        assert len(s) == 0
        s.register(_make_passing())
        assert len(s) == 1

    def test_check_all_passes(self):
        s = InvariantSet()
        s.register(_make_passing())
        result = s.check_all(_dummy_state())
        assert result.all_passed
        assert bool(result)

    def test_check_all_fails(self):
        s = InvariantSet()
        s.register(_make_failing())
        result = s.check_all(_dummy_state())
        assert not result.all_passed
        assert not bool(result)
        assert result.error_count == 1

    def test_fatal_fails(self):
        s = InvariantSet()
        s.register(_make_failing("f", InvariantSeverity.FATAL))
        result = s.check_all(_dummy_state())
        assert not result.all_passed
        assert result.fatal_count == 1

    def test_warning_does_not_block(self):
        s = InvariantSet()
        s.register(_make_failing("w", InvariantSeverity.WARNING))
        result = s.check_all(_dummy_state())
        # Warnings don't block (all_passed still True for warnings only)
        assert result.all_passed
        assert result.warning_count == 1

    def test_disabled_invariant_skipped(self):
        s   = InvariantSet()
        inv = _make_failing()
        inv.enabled = False
        s.register(inv)
        result = s.check_all(_dummy_state())
        assert result.all_passed   # disabled, so not checked

    def test_mixed_pass_fail(self):
        s = InvariantSet()
        s.register(_make_passing("p1"))
        s.register(_make_passing("p2"))
        s.register(_make_failing("f1"))
        result = s.check_all(_dummy_state())
        assert not result.all_passed
        assert result.error_count == 1
        assert len(result.results) == 3

    def test_failures_method(self):
        s = InvariantSet()
        s.register(_make_passing())
        s.register(_make_failing())
        result  = s.check_all(_dummy_state())
        failures = result.failures()
        assert len(failures) == 1
        assert failures[0].passed == False

    def test_exception_in_fn_becomes_fatal(self):
        def exploding(state):
            raise ValueError("boom")
        s = InvariantSet()
        s.register(Invariant(
            id="boom", name="Boom", description="explodes",
            fn=exploding, severity=InvariantSeverity.ERROR,
        ))
        result = s.check_all(_dummy_state())
        assert not result.all_passed

    def test_summary_string_all_pass(self):
        s = InvariantSet()
        s.register(_make_passing())
        result = s.check_all(_dummy_state())
        assert "passed" in result.summary().lower()

    def test_summary_string_failure(self):
        s = InvariantSet()
        s.register(_make_failing())
        result = s.check_all(_dummy_state())
        assert "error" in result.summary().lower() or "fail" in result.summary().lower()

    def test_check_one(self):
        s   = InvariantSet()
        inv = _make_passing()
        s.register(inv)
        r = s.check_one("test.pass", _dummy_state())
        assert r.passed

    def test_check_one_missing(self):
        s = InvariantSet()
        r = s.check_one("nonexistent", _dummy_state())
        assert not r.passed


# ── Default invariant library ─────────────────────────────────────────────────
class TestDefaultInvariants:

    def setup_method(self):
        self.inv_set = load_default_invariants()
        self.state   = _dummy_state()

    def test_loads_five_invariants(self):
        assert len(self.inv_set) == 5

    def test_all_pass_on_clean_state(self):
        result = self.inv_set.check_all(self.state)
        assert result.all_passed, result.summary()

    def test_i1_version_monotonic(self):
        inv = self.inv_set.get("I1_version_monotonic")
        assert inv is not None
        r   = inv.fn(self.state)
        assert r.passed

    def test_i3_log_append_only(self):
        inv = self.inv_set.get("I3_log_append_only")
        assert inv is not None
        r   = inv.fn(self.state)
        assert r.passed

    def test_i3_detects_tamper(self):
        inv = self.inv_set.get("I3_log_append_only")
        s   = _dummy_state()
        s.actions_log._tampered = True
        r   = inv.fn(s)
        assert not r.passed

    def test_i4_human_primacy_clean(self):
        inv = self.inv_set.get("I4_human_primacy")
        assert inv is not None
        r   = inv.fn(self.state)
        assert r.passed

    def test_i5_eval_integrity(self):
        inv = self.inv_set.get("I5_eval_integrity")
        assert inv is not None
        r   = inv.fn(self.state)
        assert r.passed
