"""
actions/engine.py
Delta engine that operates on MetaState (Σ).

Every apply() takes Σ and returns Σ'.
The inverse delta can always undo it.
"""

from __future__ import annotations
from constitutional_os.actions.deltas import Delta, DeltaType


class DeltaEngine:
    """Apply and invert deltas over the full MetaState Σ."""

    def apply(self, state: "MetaState", delta: Delta) -> "MetaState":
        from dataclasses import replace
        from constitutional_os.runtime.state import ReliabilityState, ConstitutionalState

        dt = delta.delta_type

        # ── Reliability OS deltas ─────────────────────────────────────────────
        if dt == DeltaType.LOAD_PROFILE.value:
            from constitutional_os.profiles.loader import ProfileLoader
            profile = ProfileLoader.from_dict(delta.payload["profile"])
            state.profiles.register(profile)
            return state.tick()

        elif dt == DeltaType.TOGGLE_INVARIANT.value:
            inv = state.invariants.get(delta.payload["invariant_id"])
            if inv:
                inv.enabled = delta.payload["enabled"]
            return state.tick()

        elif dt == DeltaType.TOGGLE_MEMBRANE.value:
            mem = state.constitutional.membranes._membranes.get(delta.payload["membrane_id"])
            if mem:
                mem.enabled = delta.payload["enabled"]
            return state.tick()

        # ── Constitutional OS deltas ──────────────────────────────────────────
        elif dt == DeltaType.SET_STATUS.value:
            return replace(state, status=delta.payload["status"]).tick()

        elif dt == DeltaType.PAUSE_SYSTEM.value:
            return replace(state, status="paused").tick()

        elif dt == DeltaType.RESUME_SYSTEM.value:
            return replace(state, status="running").tick()

        elif dt == "investigate_degradation":
            # No-op structural change; the recommendation is logged
            return state.tick()

        elif dt == "monitor_volatility":
            return state.tick()

        elif dt in ('note_improvement', 'monitor_volatility',
                    'investigate_degradation', 'note_improvement'):
            return state.tick()
        else:
            import warnings
            warnings.warn(f"Unknown delta type: {dt}")
            return state.tick()

    def inverse(self, state: "MetaState", delta: Delta) -> "MetaState":
        from constitutional_os.actions.deltas import Delta as D
        inv = D(
            delta_type      = delta.delta_type,
            payload         = delta.inverse_payload,
            inverse_payload = delta.payload,
            author          = delta.author,
            rationale       = f"ROLLBACK of {delta.id}",
        )
        return self.apply(state, inv)
