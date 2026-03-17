"""
runtime/state.py

Global meta-state:  Σ = (Σ_R, Σ_C, Σ_X)

  Σ_R  (Reliability OS state):  Profiles P, Eval history H, Forecast state F
  Σ_C  (Constitutional OS state): Constitutional state C, Continuity chain L
  Σ_X  (Reality layer):          External observations fed in from outside

All state is immutable. Every transition produces a new Σ.
The StateStore holds the current Σ and the full history stack for rollback.
"""

from __future__ import annotations
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Optional
import copy


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Σ_R: Reliability OS state ─────────────────────────────────────────────────
@dataclass
class ReliabilityState:
    """
    Σ_R = (P, H, F)
      P = ProfileRegistry
      H = EvalHistory
      F = ForecastState
    """
    profiles:     "ProfileRegistry"
    eval_history: "EvalHistory"
    forecasts:    "ForecastState"

    def summary(self) -> dict:
        return {
            "n_profiles":       len(self.profiles),
            "n_evals":          len(self.eval_history),
            "n_forecast_curves": len(self.forecasts.curves),
            "n_recommendations": len(self.forecasts.recommendations),
        }


# ── Σ_C: Constitutional OS state ──────────────────────────────────────────────
@dataclass
class ConstitutionalState:
    """
    Σ_C = (C, L)
      C = (rights R, obligations O, invariants I, membranes M)
      L = ContinuityLog (append-only ratified delta chain)
    """
    invariants:   "InvariantSet"
    membranes:    "MembraneSet"
    actions_log:  "ContinuityLog"
    rights:       dict  = field(default_factory=dict)      # R
    obligations:  dict  = field(default_factory=dict)      # O
    proposals:    dict  = field(default_factory=dict)      # active proposals

    def summary(self) -> dict:
        return {
            "n_invariants":  len(self.invariants),
            "n_membranes":   len(self.membranes),
            "n_log_entries": len(self.actions_log),
            "n_proposals":   len(self.proposals),
        }


# ── Σ_X: Reality layer ────────────────────────────────────────────────────────
@dataclass
class RealityState:
    """
    Σ_X = external observations from real systems.
    Fed in from outside; never modified by the OS itself.
    """
    observations: list  = field(default_factory=list)
    last_ingested: str  = field(default_factory=_now)

    def ingest(self, obs: dict) -> "RealityState":
        return RealityState(
            observations  = self.observations + [obs],
            last_ingested = _now(),
        )


# ── Σ: Global meta-state ──────────────────────────────────────────────────────
@dataclass(frozen=True)
class MetaState:
    """
    Σ = (Σ_R, Σ_C, Σ_X)

    The complete state of the epistemic-governance stack.
    Frozen so all transitions are explicit and traceable.
    """
    reliability:    ReliabilityState
    constitutional: ConstitutionalState
    reality:        RealityState

    version:   int  = 0
    status:    str  = "booting"   # booting | running | paused | error
    booted_at: str  = field(default_factory=_now)
    last_tick: str  = field(default_factory=_now)

    # ── Convenience accessors ─────────────────────────────────────────────────
    @property
    def profiles(self):
        return self.reliability.profiles

    @property
    def invariants(self):
        return self.constitutional.invariants

    @property
    def membranes(self):
        return self.constitutional.membranes

    @property
    def eval_history(self):
        return self.reliability.eval_history

    @property
    def actions_log(self):
        return self.constitutional.actions_log

    @property
    def forecasts(self):
        return self.reliability.forecasts

    # ── Transitions ───────────────────────────────────────────────────────────
    def tick(self) -> "MetaState":
        return replace(self, version=self.version + 1, last_tick=_now())

    def with_status(self, s: str) -> "MetaState":
        return replace(self, status=s)

    def with_reliability(self, r: ReliabilityState) -> "MetaState":
        return replace(self, reliability=r).tick()

    def with_constitutional(self, c: ConstitutionalState) -> "MetaState":
        return replace(self, constitutional=c).tick()

    def with_reality(self, x: RealityState) -> "MetaState":
        return replace(self, reality=x).tick()

    def summary(self) -> dict:
        return {
            "version":        self.version,
            "status":         self.status,
            "booted_at":      self.booted_at,
            "last_tick":      self.last_tick,
            **{f"rel_{k}": v for k, v in self.reliability.summary().items()},
            **{f"con_{k}": v for k, v in self.constitutional.summary().items()},
        }


# ── StateStore ────────────────────────────────────────────────────────────────
class StateStore:
    """
    Mutable wrapper around immutable MetaState.
    Holds current Σ and full history for rollback.
    All writes go through apply().
    """

    def __init__(self, initial: MetaState):
        self._current  = initial
        self._history: list[MetaState] = [initial]
        self._listeners: list = []

    @property
    def current(self) -> MetaState:
        return self._current

    # ── Σ_R accessors ─────────────────────────────────────────────────────────
    @property
    def R(self) -> ReliabilityState:
        return self._current.reliability

    # ── Σ_C accessors ─────────────────────────────────────────────────────────
    @property
    def C(self) -> ConstitutionalState:
        return self._current.constitutional

    def apply(self, new_state: MetaState) -> MetaState:
        self._history.append(self._current)
        self._current = new_state
        for fn in self._listeners:
            try: fn(new_state)
            except Exception: pass
        return new_state

    def rollback(self, steps: int = 1) -> MetaState:
        steps = min(steps, len(self._history) - 1)
        if steps <= 0:
            return self._current
        for _ in range(steps):
            if self._history:
                self._current = self._history.pop()
        return self._current

    def rollback_to_version(self, version: int) -> Optional[MetaState]:
        target = next(
            (s for s in reversed(self._history) if s.version == version), None
        )
        if not target:
            return None
        self._history = [s for s in self._history if s.version <= version]
        self._current = target
        return target

    def on_change(self, fn) -> None:
        self._listeners.append(fn)

    def history_summary(self) -> list[dict]:
        return [
            {"version": s.version, "status": s.status, "tick": s.last_tick}
            for s in self._history[-20:]
        ]

    def __len__(self) -> int:
        return len(self._history)
