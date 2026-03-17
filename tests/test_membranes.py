"""
tests/test_membranes.py
Tests for membranes/engine.py: all four membranes, verdicts, combinations.
"""
import pytest

from constitutional_os.membranes.engine import (
    Membrane, MembraneSet, MembraneResult, MembraneVerdict,
    ProposedDelta, MembraneSetResult,
    load_default_membranes,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────
def _delta(**kwargs):
    defaults = dict(
        delta_type="test_delta",
        payload={},
        autonomy="autonomous",
        severity="normal",
        reversible=True,
        scope="local",
        requester="test",
    )
    defaults.update(kwargs)
    return ProposedDelta(**defaults)


def _dummy_state():
    class S:
        version = 1
        status  = "running"
    return S()


# ── MembraneResult ────────────────────────────────────────────────────────────
class TestMembraneResult:

    def test_pass_is_truthy(self):
        r = MembraneResult("m1", MembraneVerdict.PASS)
        assert bool(r) is True
        assert r.passed is True

    def test_block_is_falsy(self):
        r = MembraneResult("m1", MembraneVerdict.BLOCK, "reason")
        assert bool(r) is False
        assert r.passed is False

    def test_defer_not_passed(self):
        r = MembraneResult("m1", MembraneVerdict.DEFER)
        assert r.passed  is False
        assert r.deferred is True


# ── MembraneSet ───────────────────────────────────────────────────────────────
class TestMembraneSet:

    def test_register_and_check(self):
        ms = MembraneSet()
        ms.register(Membrane(
            id="m1", name="Always Pass", description="",
            fn=lambda s, d: MembraneResult("m1", MembraneVerdict.PASS),
        ))
        result = ms.check_all(_dummy_state(), _delta())
        assert result.passed

    def test_block_propagates(self):
        ms = MembraneSet()
        ms.register(Membrane(
            id="blocker", name="Blocker", description="",
            fn=lambda s, d: MembraneResult("blocker", MembraneVerdict.BLOCK, "no"),
        ))
        result = ms.check_all(_dummy_state(), _delta())
        assert not result.passed
        assert result.verdict == MembraneVerdict.BLOCK
        assert "blocker" in result.blockers

    def test_defer_propagates(self):
        ms = MembraneSet()
        ms.register(Membrane(
            id="deferrer", name="Deferrer", description="",
            fn=lambda s, d: MembraneResult("deferrer", MembraneVerdict.DEFER),
        ))
        result = ms.check_all(_dummy_state(), _delta())
        assert result.verdict == MembraneVerdict.DEFER
        assert "deferrer" in result.deferrals

    def test_block_beats_defer(self):
        ms = MembraneSet()
        ms.register(Membrane(
            id="m1", name="Block", description="", order=1,
            fn=lambda s, d: MembraneResult("m1", MembraneVerdict.BLOCK, "blocked"),
        ))
        ms.register(Membrane(
            id="m2", name="Defer", description="", order=2,
            fn=lambda s, d: MembraneResult("m2", MembraneVerdict.DEFER),
        ))
        result = ms.check_all(_dummy_state(), _delta())
        assert result.verdict == MembraneVerdict.BLOCK

    def test_disabled_membrane_skipped(self):
        ms = MembraneSet()
        ms.register(Membrane(
            id="disabled", name="Disabled Blocker", description="",
            fn=lambda s, d: MembraneResult("disabled", MembraneVerdict.BLOCK),
            enabled=False,
        ))
        result = ms.check_all(_dummy_state(), _delta())
        assert result.passed

    def test_len(self):
        ms = MembraneSet()
        assert len(ms) == 0
        ms.register(Membrane(
            id="m1", name="m1", description="",
            fn=lambda s, d: MembraneResult("m1", MembraneVerdict.PASS),
        ))
        assert len(ms) == 1

    def test_exception_becomes_block(self):
        def exploding(s, d):
            raise RuntimeError("boom")
        ms = MembraneSet()
        ms.register(Membrane(id="boom", name="Boom", description="", fn=exploding))
        result = ms.check_all(_dummy_state(), _delta())
        assert result.verdict == MembraneVerdict.BLOCK


# ── Four canonical membranes ──────────────────────────────────────────────────
class TestDefaultMembranes:

    def setup_method(self):
        self.ms    = load_default_membranes()
        self.state = _dummy_state()

    def test_loads_four_membranes(self):
        assert len(self.ms) == 4

    def test_normal_delta_passes_all(self):
        d      = _delta(autonomy="autonomous", severity="normal",
                        reversible=True, scope="local")
        result = self.ms.check_all(self.state, d)
        assert result.passed, result.summary()

    # ── M1: Safety ────────────────────────────────────────────────────────────
    def test_m1_blocks_critical_autonomous(self):
        d      = _delta(autonomy="autonomous", severity="critical", scope="local")
        result = self.ms.check_all(self.state, d)
        assert not result.passed
        assert "M1_safety" in result.blockers

    def test_m1_blocks_constitutional_non_human(self):
        d      = _delta(autonomy="autonomous", scope="constitutional")
        result = self.ms.check_all(self.state, d)
        assert "M1_safety" in result.blockers

    def test_m1_passes_critical_human_directed(self):
        d   = _delta(autonomy="human-directed", severity="critical", scope="local")
        m1  = self.ms._membranes["M1_safety"]
        r   = m1.fn(self.state, d)
        assert r.verdict == MembraneVerdict.PASS

    # ── M2: Reversibility ─────────────────────────────────────────────────────
    def test_m2_defers_irreversible_autonomous(self):
        d   = _delta(autonomy="autonomous", reversible=False)
        m2  = self.ms._membranes["M2_reversibility"]
        r   = m2.fn(self.state, d)
        assert r.verdict == MembraneVerdict.DEFER

    def test_m2_passes_irreversible_human_directed(self):
        d   = _delta(autonomy="human-directed", reversible=False)
        m2  = self.ms._membranes["M2_reversibility"]
        r   = m2.fn(self.state, d)
        assert r.verdict == MembraneVerdict.PASS

    def test_m2_passes_reversible_autonomous(self):
        d   = _delta(autonomy="autonomous", reversible=True)
        m2  = self.ms._membranes["M2_reversibility"]
        r   = m2.fn(self.state, d)
        assert r.verdict == MembraneVerdict.PASS

    # ── M3: Pluralism ─────────────────────────────────────────────────────────
    def test_m3_blocks_lock_in_types(self):
        for lock_in in ["remove_membrane", "disable_invariant",
                        "revoke_human_primacy", "seal_state"]:
            d   = _delta(delta_type=lock_in)
            m3  = self.ms._membranes["M3_pluralism"]
            r   = m3.fn(self.state, d)
            assert r.verdict == MembraneVerdict.BLOCK, \
                f"{lock_in} should be blocked by M3"

    def test_m3_passes_normal_types(self):
        for normal in ["update_config", "load_profile", "run_eval"]:
            d   = _delta(delta_type=normal)
            m3  = self.ms._membranes["M3_pluralism"]
            r   = m3.fn(self.state, d)
            assert r.verdict == MembraneVerdict.PASS, \
                f"{normal} should pass M3"

    # ── M4: Human primacy ─────────────────────────────────────────────────────
    def test_m4_defers_significant_autonomous(self):
        d   = _delta(autonomy="autonomous", severity="significant")
        m4  = self.ms._membranes["M4_human_primacy"]
        r   = m4.fn(self.state, d)
        assert r.verdict == MembraneVerdict.DEFER

    def test_m4_defers_global_scope(self):
        d   = _delta(autonomy="autonomous", scope="global")
        m4  = self.ms._membranes["M4_human_primacy"]
        r   = m4.fn(self.state, d)
        assert r.verdict == MembraneVerdict.DEFER

    def test_m4_defers_irreversible(self):
        d   = _delta(autonomy="autonomous", reversible=False)
        m4  = self.ms._membranes["M4_human_primacy"]
        r   = m4.fn(self.state, d)
        assert r.verdict == MembraneVerdict.DEFER

    def test_m4_passes_normal_autonomous(self):
        d   = _delta(autonomy="autonomous", severity="normal",
                     scope="local", reversible=True)
        m4  = self.ms._membranes["M4_human_primacy"]
        r   = m4.fn(self.state, d)
        assert r.verdict == MembraneVerdict.PASS

    def test_m4_passes_significant_human_directed(self):
        d   = _delta(autonomy="human-directed", severity="significant")
        m4  = self.ms._membranes["M4_human_primacy"]
        r   = m4.fn(self.state, d)
        assert r.verdict == MembraneVerdict.PASS
