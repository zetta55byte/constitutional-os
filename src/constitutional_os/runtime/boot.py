"""
runtime/boot.py
Boot sequence for the epistemic-governance stack.

Step 1  Initialize Σ = (Σ_R, Σ_C, Σ_X)
Step 2  Register Σ_C: invariants + membranes
Step 3  Register event handlers (both layers)
Step 4  Load profiles → emit ProfileLoaded events
Step 5  Run initial health eval
Step 6  Verify invariants
Step 7  Mark running → emit SystemBooted
"""

from __future__ import annotations
from dataclasses import replace
from typing import Optional
from pathlib import Path


def boot(
    profiles_dir: Optional[str] = None,
    strict:       bool = False,
    verbose:      bool = True,
) -> tuple["StateStore", "EventDispatcher"]:

    def log(msg: str):
        if verbose: print(f"[boot] {msg}")

    from constitutional_os.runtime.state     import MetaState, ReliabilityState, ConstitutionalState, RealityState, StateStore
    from constitutional_os.runtime.events    import (EventDispatcher, SystemBooted, ProfileLoaded,
                                   EvalRequested, EvalCompleted, ActionRecommended,
                                   ActionProposed, ActionRatified, ActionExecuted,
                                   InvariantViolated, ForecastTick,
                                   HumanVetoWindowOpened, ObservationIngested)
    from constitutional_os.profiles.loader   import ProfileRegistry, ProfileLoader
    from constitutional_os.invariants.engine import load_default_invariants
    from constitutional_os.membranes.engine  import load_default_membranes, ProposedDelta, MembraneVerdict
    from constitutional_os.evals.runner      import EvalHistory, EvalRunner
    from constitutional_os.actions.deltas    import ContinuityLog, LogEntry, DeltaEngine
    from constitutional_os.forecast.engine   import ForecastState, ForecastEngine

    log("Initializing epistemic-governance stack...")

    # ── Step 1: Initialize Σ ─────────────────────────────────────────────────
    reliability = ReliabilityState(
        profiles     = ProfileRegistry(),
        eval_history = EvalHistory(),
        forecasts    = ForecastState(),
    )
    constitutional = ConstitutionalState(
        invariants  = load_default_invariants(),
        membranes   = load_default_membranes(),
        actions_log = ContinuityLog(),
    )
    reality = RealityState()

    state = MetaState(
        reliability    = reliability,
        constitutional = constitutional,
        reality        = reality,
        status         = "booting",
    )

    log(f"Σ_R: {len(state.profiles)} profiles")
    log(f"Σ_C: {len(state.invariants)} invariants, {len(state.membranes)} membranes")

    store      = StateStore(state)
    dispatcher = EventDispatcher()
    runner     = EvalRunner()
    delta_eng  = DeltaEngine()
    forecast_eng = ForecastEngine()

    # ── Step 2: Register event handlers ──────────────────────────────────────

    # ── Reality layer ─────────────────────────────────────────────────────────
    def on_observation(state, event: ObservationIngested):
        new_x = state.reality.ingest({
            "source": event.source, "metric": event.metric,
            "value": event.value, "ts": event.ts,
        })
        return state.with_reality(new_x), []

    dispatcher.register(ObservationIngested, on_observation)

    # ── Reliability OS layer ──────────────────────────────────────────────────
    def on_profile_loaded(state, event: ProfileLoaded):
        log(f"ProfileLoaded: {event.profile_id} v{event.version}")
        # Auto-run integrity eval
        report = runner.run("core.integrity", state, event.profile_id)
        state.eval_history.append(report)
        if not report.passed:
            log(f"  WARN: Integrity check failed: {report.summary}")
        return state, []

    dispatcher.register(ProfileLoaded, on_profile_loaded)

    def on_eval_requested(state, event: EvalRequested):
        report = runner.run(event.bundle_id, state, event.profile_id)
        state.eval_history.append(report)
        return state, [EvalCompleted(
            bundle_id  = event.bundle_id,
            profile_id = event.profile_id,
            passed     = report.passed,
            score      = report.score,
            summary    = report.summary,
        )]

    dispatcher.register(EvalRequested, on_eval_requested)

    def on_eval_completed(state, event: EvalCompleted):
        if not event.passed:
            log(f"Eval FAILED: {event.bundle_id}/{event.profile_id} score={event.score:.2f}")
        return state, []

    dispatcher.register(EvalCompleted, on_eval_completed)

    def on_forecast_tick(state, event: ForecastTick):
        # Build history from observations
        history_map = {}
        for obs in state.reality.observations[-100:]:
            key = f"{obs.get('source','unknown')}:{obs.get('metric','value')}"
            history_map.setdefault(key, []).append(float(obs.get('value', 0)))

        new_forecasts = forecast_eng.run_all(state, history_map)

        # Emit ActionRecommended for any critical recommendations
        new_events = []
        for rec in new_forecasts.pending_recommendations():
            new_events.append(ActionRecommended(
                action_id   = rec.recommendation_id,
                delta_type  = rec.action_type,
                payload     = {"metric": rec.metric, "profile_id": rec.profile_id},
                rationale   = rec.rationale,
                urgency     = rec.urgency,
                confidence  = rec.confidence,
                profile_id  = rec.profile_id,
            ))

        from constitutional_os.runtime.state import ReliabilityState
        new_R = ReliabilityState(
            profiles     = state.profiles,
            eval_history = state.eval_history,
            forecasts    = new_forecasts,
        )
        state = state.with_reliability(new_R)
        return state, new_events

    dispatcher.register(ForecastTick, on_forecast_tick)

    # ── Interface: Reliability → Constitutional ───────────────────────────────
    def on_action_recommended(state, event: ActionRecommended):
        """
        THE boundary crossing.
        E produces ActionRecommended; G receives it here.
        """
        import uuid
        log(f"ActionRecommended [{event.urgency}]: {event.delta_type} — {event.rationale[:60]}")

        # Membrane check
        proposed = ProposedDelta(
            delta_type = event.delta_type,
            payload    = event.payload,
            autonomy   = "autonomous",
            severity   = "significant" if event.urgency in ("high","critical") else "normal",
            reversible = True,
            scope      = "local",
            requester  = "reliability_os",
        )
        mem_result = state.membranes.check_all(state, proposed)
        log(f"  Membrane verdict: {mem_result.verdict.value} — {mem_result.summary()}")

        proposal_id = str(uuid.uuid4())[:8]

        if mem_result.verdict == MembraneVerdict.BLOCK:
            entry = LogEntry(
                seq=0, delta_id=event.action_id, delta_type=event.delta_type,
                fingerprint="", state_version=state.version,
                proposal_id=proposal_id, status="blocked",
                author="reliability_os", rationale=f"Blocked: {mem_result.blockers}",
            )
            state.actions_log.append(entry)
            return state, []

        if mem_result.verdict == MembraneVerdict.DEFER:
            entry = LogEntry(
                seq=0, delta_id=event.action_id, delta_type=event.delta_type,
                fingerprint="", state_version=state.version,
                proposal_id=proposal_id, status="deferred",
                author="reliability_os", rationale=f"Deferred: {mem_result.deferrals}",
            )
            state.actions_log.append(entry)
            return state, [HumanVetoWindowOpened(
                proposal_id = proposal_id,
                window_secs = 300,
            )]

        # Passed all membranes → propose
        return state, [ActionProposed(
            proposal_id = proposal_id,
            action_id   = event.action_id,
            delta_type  = event.delta_type,
            payload     = event.payload,
            proposer    = "reliability_os",
            urgency     = event.urgency,
        )]

    dispatcher.register(ActionRecommended, on_action_recommended)

    # ── Constitutional OS layer ───────────────────────────────────────────────
    def on_action_proposed(state, event: ActionProposed):
        log(f"ActionProposed: {event.proposal_id} ({event.delta_type})")
        inv_result = state.invariants.check_all(state)
        if not inv_result:
            log(f"  Invariant FAILED: {inv_result.summary()}")
            return state, [InvariantViolated(
                invariant_id = "batch_check",
                context      = inv_result.summary(),
                severity     = "error",
            )]
        log(f"  Invariants OK. Ratifying {event.proposal_id}")
        return state, [ActionRatified(
            proposal_id = event.proposal_id,
            action_id   = event.action_id,
            delta_type  = event.delta_type,
            payload     = event.payload,
        )]

    dispatcher.register(ActionProposed, on_action_proposed)

    def on_action_ratified(state, event: ActionRatified):
        log(f"ActionRatified: {event.proposal_id} — executing")
        from constitutional_os.actions.deltas import Delta
        delta = Delta(
            delta_type = event.delta_type,
            payload    = event.payload,
            author     = "constitutional_os",
            rationale  = f"Ratified proposal {event.proposal_id}",
            proposal_id = event.proposal_id,
        )
        try:
            state = delta_eng.apply(state, delta)
        except Exception as e:
            log(f"  Delta apply error: {e}")
        entry = LogEntry(
            seq=0, delta_id=event.action_id, delta_type=event.delta_type,
            fingerprint=delta.fingerprint(), state_version=state.version,
            proposal_id=event.proposal_id, status="ratified",
            author="constitutional_os", rationale=delta.rationale,
        )
        state.actions_log.append(entry)
        return state, [ActionExecuted(
            proposal_id = event.proposal_id,
            action_id   = event.action_id,
            result      = "ok",
            new_version = state.version,
        )]

    dispatcher.register(ActionRatified, on_action_ratified)

    def on_action_executed(state, event: ActionExecuted):
        log(f"ActionExecuted: {event.action_id} v{event.new_version}")
        entry = LogEntry(
            seq=0, delta_id=event.action_id, delta_type="executed",
            fingerprint="", state_version=state.version,
            proposal_id=event.proposal_id, status="executed",
        )
        state.actions_log.append(entry)
        return state, []

    dispatcher.register(ActionExecuted, on_action_executed)

    def on_invariant_violated(state, event: InvariantViolated):
        log(f"INVARIANT VIOLATED: {event.invariant_id} — {event.context}")
        if event.severity == "fatal":
            return state.with_status("error"), []
        return state, []

    dispatcher.register(InvariantViolated, on_invariant_violated)

    def on_human_veto_opened(state, event: HumanVetoWindowOpened):
        log(f"Human veto window opened: proposal {event.proposal_id} ({event.window_secs}s)")
        return state, []

    dispatcher.register(HumanVetoWindowOpened, on_human_veto_opened)

    # ── Step 4: Load profiles ─────────────────────────────────────────────────
    if profiles_dir:
        p = Path(profiles_dir)
        if p.exists():
            for f in sorted(p.glob("*.yaml")):
                try:
                    profile = ProfileLoader.from_file(str(f))
                    state.profiles.register(profile)
                    state = dispatcher.dispatch(state, ProfileLoaded(
                        profile_id=profile.id, profile_name=profile.name,
                        version=profile.version,
                    ))
                    store.apply(state)
                    log(f"Loaded profile: {profile.id} v{profile.version}")
                except Exception as e:
                    log(f"Failed to load {f.name}: {e}")

    # ── Step 5: Initial health eval ───────────────────────────────────────────
    report = runner.run("core.health", state)
    state.eval_history.append(report)
    log(f"Health eval: {report.summary}")

    # ── Step 6: Verify invariants ─────────────────────────────────────────────
    inv_result = state.invariants.check_all(state)
    if not inv_result:
        log(f"WARNING: {inv_result.summary()}")
        if strict:
            raise RuntimeError(f"Boot aborted: {inv_result.summary()}")

    # ── Step 7: Mark running ──────────────────────────────────────────────────
    state = replace(state, status="running").tick()
    store.apply(state)
    state = dispatcher.dispatch(state, SystemBooted(version="0.1.0"))
    store.apply(state)

    log(f"Boot complete. Σ summary: {state.summary()}")
    return store, dispatcher
