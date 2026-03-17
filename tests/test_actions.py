"""
tests/test_actions.py
Tests for actions/deltas.py: Delta, DeltaEngine, ContinuityLog.
"""
import pytest

from constitutional_os.actions.deltas import Delta, DeltaType, ContinuityLog, LogEntry, DeltaEngine


# ── Delta ─────────────────────────────────────────────────────────────────────
class TestDelta:

    def test_auto_id(self):
        d1 = Delta(delta_type="test")
        d2 = Delta(delta_type="test")
        assert d1.id != d2.id   # unique IDs

    def test_fingerprint_deterministic(self):
        d = Delta(
            delta_type="load_profile",
            payload={"profile": {"id": "p1"}},
            created_at="2026-01-01T00:00:00",
        )
        assert d.fingerprint() == d.fingerprint()

    def test_fingerprint_changes_with_payload(self):
        d1 = Delta(delta_type="test", payload={"x": 1},  created_at="2026-01-01")
        d2 = Delta(delta_type="test", payload={"x": 99}, created_at="2026-01-01")
        assert d1.fingerprint() != d2.fingerprint()

    def test_fields(self):
        d = Delta(
            delta_type="update_config",
            payload={"key": "value"},
            author="test",
            rationale="testing",
        )
        assert d.delta_type == "update_config"
        assert d.payload    == {"key": "value"}
        assert d.author     == "test"
        assert d.rationale  == "testing"


# ── ContinuityLog ─────────────────────────────────────────────────────────────
class TestContinuityLog:

    def _make_entry(self, seq=0, delta_type="test", status="executed"):
        return LogEntry(
            seq=seq, delta_id="d1", delta_type=delta_type,
            fingerprint="abc", state_version=1,
            proposal_id="p1", status=status,
            author="test", rationale="test entry",
        )

    def test_append_and_len(self):
        log = ContinuityLog()
        assert len(log) == 0
        log.append(self._make_entry())
        assert len(log) == 1

    def test_seq_auto_assigned(self):
        log = ContinuityLog()
        e1 = log.append(self._make_entry())
        e2 = log.append(self._make_entry())
        assert e1.seq == 0
        assert e2.seq == 1

    def test_prev_hash_genesis(self):
        log = ContinuityLog()
        e   = log.append(self._make_entry())
        assert e.prev_hash == "genesis"

    def test_prev_hash_chained(self):
        log = ContinuityLog()
        e1  = log.append(self._make_entry())
        e2  = log.append(self._make_entry())
        assert e2.prev_hash != "genesis"
        assert len(e2.prev_hash) == 16   # hex digest

    def test_verify_clean_log(self):
        log = ContinuityLog()
        for i in range(5):
            log.append(self._make_entry(seq=i))
        assert log.verify() is True

    def test_recent_entries(self):
        log = ContinuityLog()
        for i in range(30):
            log.append(self._make_entry(seq=i))
        recent = log.recent_entries(10)
        assert len(recent) == 10

    def test_entries_for_proposal(self):
        log = ContinuityLog()
        e1 = self._make_entry()
        e1.proposal_id = "prop_a"
        e2 = self._make_entry()
        e2.proposal_id = "prop_b"
        e3 = self._make_entry()
        e3.proposal_id = "prop_a"
        log.append(e1)
        log.append(e2)
        log.append(e3)
        entries = log.entries_for_proposal("prop_a")
        assert len(entries) == 2

    def test_tamper_not_flagged_on_clean(self):
        log = ContinuityLog()
        log.append(self._make_entry())
        assert log._tampered is False


# ── DeltaEngine ───────────────────────────────────────────────────────────────
class TestDeltaEngine:

    def _make_state(self):
        from constitutional_os.runtime.boot import boot
        store, _ = boot(verbose=False)
        return store.current

    def test_set_status_delta(self):
        state  = self._make_state()
        engine = DeltaEngine()
        delta  = Delta(
            delta_type = DeltaType.SET_STATUS.value,
            payload    = {"status": "paused"},
        )
        new_state = engine.apply(state, delta)
        assert new_state.status == "paused"

    def test_version_increments(self):
        state   = self._make_state()
        engine  = DeltaEngine()
        v_before = state.version
        delta   = Delta(
            delta_type = DeltaType.SET_STATUS.value,
            payload    = {"status": "running"},
        )
        new_state = engine.apply(state, delta)
        assert new_state.version > v_before

    def test_pause_resume(self):
        state  = self._make_state()
        engine = DeltaEngine()

        paused = engine.apply(state, Delta(
            delta_type=DeltaType.PAUSE_SYSTEM.value, payload={}
        ))
        assert paused.status == "paused"

        resumed = engine.apply(paused, Delta(
            delta_type=DeltaType.RESUME_SYSTEM.value, payload={}
        ))
        assert resumed.status == "running"

    def test_load_profile_delta(self):
        state  = self._make_state()
        engine = DeltaEngine()
        assert len(state.profiles) == 0

        delta = Delta(
            delta_type = DeltaType.LOAD_PROFILE.value,
            payload    = {"profile": {
                "id": "test.loaded", "name": "Test", "version": "1.0.0",
                "metrics": [], "evals": [], "actions": [],
            }},
        )
        new_state = engine.apply(state, delta)
        assert len(new_state.profiles) == 1
        assert new_state.profiles.get("test.loaded") is not None

    def test_toggle_invariant(self):
        state  = self._make_state()
        engine = DeltaEngine()

        # Disable an invariant
        delta = Delta(
            delta_type = DeltaType.TOGGLE_INVARIANT.value,
            payload    = {"invariant_id": "I2_profiles_initialized", "enabled": False},
        )
        new_state = engine.apply(state, delta)
        inv = new_state.invariants.get("I2_profiles_initialized")
        assert inv.enabled is False

    def test_epistemic_deltas_are_no_ops(self):
        state  = self._make_state()
        engine = DeltaEngine()
        v_before = state.version

        for dt in ["note_improvement", "monitor_volatility", "investigate_degradation"]:
            new_state = engine.apply(state, Delta(delta_type=dt, payload={}))
            assert new_state.version > v_before   # ticks but doesn't change structure
            state = new_state
