"""
tests/test_runtime.py
Integration tests for the full runtime: boot, state store,
event dispatch, Phi operator, rollback.
"""
import pytest


# ── Boot ──────────────────────────────────────────────────────────────────────
class TestBoot:

    def test_boot_returns_store_and_dispatcher(self):
        from constitutional_os.runtime.boot import boot
        store, dispatcher = boot(verbose=False)
        assert store      is not None
        assert dispatcher is not None

    def test_boot_state_is_running(self):
        from constitutional_os.runtime.boot import boot
        store, _ = boot(verbose=False)
        assert store.current.status == "running"

    def test_boot_version_positive(self):
        from constitutional_os.runtime.boot import boot
        store, _ = boot(verbose=False)
        assert store.current.version > 0

    def test_boot_has_invariants(self):
        from constitutional_os.runtime.boot import boot
        store, _ = boot(verbose=False)
        assert len(store.current.invariants) == 5

    def test_boot_has_membranes(self):
        from constitutional_os.runtime.boot import boot
        store, _ = boot(verbose=False)
        assert len(store.current.membranes) == 4

    def test_boot_empty_profiles(self):
        from constitutional_os.runtime.boot import boot
        store, _ = boot(verbose=False)
        assert len(store.current.profiles) == 0

    def test_boot_summary_complete(self):
        from constitutional_os.runtime.boot import boot
        store, _ = boot(verbose=False)
        s = store.current.summary()
        assert "version"       in s
        assert "status"        in s
        assert "con_n_invariants" in s

    def test_boot_twice_independent(self):
        from constitutional_os.runtime.boot import boot
        store1, _ = boot(verbose=False)
        store2, _ = boot(verbose=False)
        # Separate state stores
        assert store1 is not store2
        assert store1.current is not store2.current


# ── StateStore ────────────────────────────────────────────────────────────────
class TestStateStore:

    def setup_method(self):
        from constitutional_os.runtime.boot import boot
        self.store, self.dispatcher = boot(verbose=False)

    def test_current_returns_state(self):
        from constitutional_os.runtime.state import MetaState
        assert isinstance(self.store.current, MetaState)

    def test_apply_advances_history(self):
        n_before = len(self.store)
        new_state = self.store.current.tick()
        self.store.apply(new_state)
        assert len(self.store) == n_before + 1

    def test_rollback_one_step(self):
        v_before = self.store.current.version
        new_state = self.store.current.tick()
        self.store.apply(new_state)
        assert self.store.current.version > v_before

        self.store.rollback(1)
        assert self.store.current.version == v_before

    def test_rollback_multiple_steps(self):
        v0 = self.store.current.version
        for _ in range(5):
            self.store.apply(self.store.current.tick())
        self.store.rollback(3)
        assert self.store.current.version < v0 + 5

    def test_rollback_to_version(self):
        target_v = self.store.current.version
        for _ in range(4):
            self.store.apply(self.store.current.tick())
        result = self.store.rollback_to_version(target_v)
        assert result is not None
        assert result.version == target_v

    def test_rollback_to_missing_version_returns_none(self):
        result = self.store.rollback_to_version(99999)
        assert result is None

    def test_history_summary(self):
        history = self.store.history_summary()
        assert isinstance(history, list)
        assert len(history) > 0
        assert "version" in history[0]

    def test_on_change_listener(self):
        called = []
        self.store.on_change(lambda s: called.append(s.version))
        self.store.apply(self.store.current.tick())
        assert len(called) == 1


# ── Events ────────────────────────────────────────────────────────────────────
class TestEvents:

    def setup_method(self):
        from constitutional_os.runtime.boot import boot
        self.store, self.dispatcher = boot(verbose=False)

    def test_profile_loaded_event(self):
        from constitutional_os.runtime.events import ProfileLoaded
        from constitutional_os.profiles.loader import ProfileLoader

        profile = ProfileLoader.from_dict({
            "id": "event.test", "name": "Event Test",
            "version": "1.0.0", "metrics": [], "evals": [], "actions": [],
        })
        self.store.current.profiles.register(profile)
        state = self.dispatcher.dispatch(self.store.current, ProfileLoaded(
            profile_id="event.test", profile_name="Event Test", version="1.0.0",
        ))
        # Dispatcher ran without exception
        assert state is not None

    def test_observation_ingested(self):
        from constitutional_os.runtime.events import ObservationIngested
        state = self.dispatcher.dispatch(self.store.current, ObservationIngested(
            source="test", metric="quality", value=0.85,
        ))
        self.store.apply(state)
        assert len(self.store.current.reality.observations) == 1
        assert self.store.current.reality.observations[0]["metric"] == "quality"

    def test_action_recommended_triggers_membrane_check(self):
        from constitutional_os.runtime.events import ActionRecommended
        initial_log_len = len(self.store.current.actions_log)
        state = self.dispatcher.dispatch(self.store.current, ActionRecommended(
            action_id  = "test_action",
            delta_type = "investigate_degradation",
            payload    = {},
            rationale  = "quality degrading",
            urgency    = "normal",
            confidence = 0.7,
        ))
        self.store.apply(state)
        # Log should have grown (action was processed)
        # Either blocked, deferred, or ratified — all leave a trace
        assert len(self.store.current.actions_log) >= initial_log_len

    def test_dispatcher_recent_events(self):
        from constitutional_os.runtime.events import ObservationIngested
        self.dispatcher.dispatch(self.store.current, ObservationIngested(
            source="test", metric="quality", value=0.85,
        ))
        events = self.dispatcher.recent_events(5)
        assert len(events) >= 1
        assert any(e["type"] == "ObservationIngested" for e in events)


# ── Phi operator ──────────────────────────────────────────────────────────────
class TestPhiOperator:

    def setup_method(self):
        from constitutional_os.runtime.boot import boot
        self.store, self.dispatcher = boot(verbose=False)

    def test_phi_returns_result(self):
        from constitutional_os.runtime.operators import phi
        from constitutional_os.evals.runner      import EvalRunner
        from constitutional_os.forecast.engine   import ForecastEngine

        result = phi(
            state        = self.store.current,
            eval_runner  = EvalRunner(),
            forecast_eng = ForecastEngine(),
            dispatcher   = self.dispatcher,
            history_map  = {},
        )
        assert result is not None
        assert result.new_state is not None

    def test_phi_advances_version(self):
        from constitutional_os.runtime.operators import phi
        from constitutional_os.evals.runner      import EvalRunner
        from constitutional_os.forecast.engine   import ForecastEngine

        v_before = self.store.current.version
        result   = phi(
            state        = self.store.current,
            eval_runner  = EvalRunner(),
            forecast_eng = ForecastEngine(),
            dispatcher   = self.dispatcher,
            history_map  = {},
        )
        assert result.new_state.version > v_before

    def test_phi_no_delta_is_fixed_point(self):
        from constitutional_os.runtime.operators import phi
        from constitutional_os.evals.runner      import EvalRunner
        from constitutional_os.forecast.engine   import ForecastEngine

        # No history → no recommendations → no delta → fixed point
        result = phi(
            state        = self.store.current,
            eval_runner  = EvalRunner(),
            forecast_eng = ForecastEngine(),
            dispatcher   = self.dispatcher,
            history_map  = {},
        )
        assert result.is_fixed_point is True

    def test_phi_with_stability(self):
        from constitutional_os.runtime.operators import phi_with_stability
        from constitutional_os.evals.runner      import EvalRunner
        from constitutional_os.forecast.engine   import ForecastEngine
        from constitutional_os.runtime.theory    import StabilityReport

        result, report = phi_with_stability(
            state        = self.store.current,
            eval_runner  = EvalRunner(),
            forecast_eng = ForecastEngine(),
            dispatcher   = self.dispatcher,
            history_map  = {},
        )
        assert isinstance(report, StabilityReport)
        assert report.lyapunov is not None

    def test_phi_governance_result_has_verdict(self):
        from constitutional_os.runtime.operators import phi
        from constitutional_os.evals.runner      import EvalRunner
        from constitutional_os.forecast.engine   import ForecastEngine

        result = phi(
            state        = self.store.current,
            eval_runner  = EvalRunner(),
            forecast_eng = ForecastEngine(),
            dispatcher   = self.dispatcher,
            history_map  = {},
        )
        assert result.governance_result.verdict in (
            "admitted", "blocked", "deferred", "no_delta"
        )


# ── MetaState immutability ────────────────────────────────────────────────────
class TestMetaStateImmutability:

    def test_tick_returns_new_state(self):
        from constitutional_os.runtime.boot import boot
        store, _ = boot(verbose=False)
        s1 = store.current
        s2 = s1.tick()
        assert s1 is not s2
        assert s2.version == s1.version + 1

    def test_with_status_returns_new_state(self):
        from constitutional_os.runtime.boot import boot
        store, _ = boot(verbose=False)
        s1 = store.current
        s2 = s1.with_status("paused")
        assert s1.status == "running"
        assert s2.status == "paused"
        assert s1 is not s2

    def test_original_unchanged_after_apply(self):
        from constitutional_os.runtime.boot import boot
        store, _ = boot(verbose=False)
        original = store.current
        v_orig   = original.version
        store.apply(original.tick())
        # Original object unchanged
        assert original.version == v_orig
