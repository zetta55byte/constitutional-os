"""
runtime/events.py
Event types and dispatcher for the epistemic-governance stack.

Events flow in one direction across the layer boundary:
  Reliability OS → [ActionRecommended] → Constitutional OS

All other events stay within their layer.

Handler: (Σ, event) -> (Σ, list[Event])
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Any
from datetime import datetime, timezone
from enum import Enum
import uuid


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _id() -> str:
    return str(uuid.uuid4())[:8]


class Layer(Enum):
    REALITY        = "reality"
    RELIABILITY    = "reliability"
    INTERFACE      = "interface"      # crosses layers
    CONSTITUTIONAL = "constitutional"
    SYSTEM         = "system"


@dataclass(frozen=True)
class Event:
    id:    str  = field(default_factory=_id)
    ts:    str  = field(default_factory=_now)
    layer: str  = Layer.SYSTEM.value


# ══════════════════════════════════════════════════════
# REALITY LAYER
# ══════════════════════════════════════════════════════

@dataclass(frozen=True)
class ObservationIngested(Event):
    """Raw observation from the reality layer."""
    source:  str   = ""
    metric:  str   = ""
    value:   float = 0.0
    context: str   = ""
    layer:   str   = Layer.REALITY.value


# ══════════════════════════════════════════════════════
# RELIABILITY OS (Σ_R) EVENTS
# ══════════════════════════════════════════════════════

@dataclass(frozen=True)
class ProfileLoaded(Event):
    profile_id:   str = ""
    profile_name: str = ""
    version:      str = "1.0.0"
    layer:        str = Layer.RELIABILITY.value

@dataclass(frozen=True)
class ProfileUpdated(Event):
    profile_id:   str = ""
    old_version:  str = ""
    new_version:  str = ""
    diff_summary: str = ""
    layer:        str = Layer.RELIABILITY.value

@dataclass(frozen=True)
class EvalRequested(Event):
    bundle_id:  str = ""
    profile_id: str = ""
    requester:  str = "system"
    layer:      str = Layer.RELIABILITY.value

@dataclass(frozen=True)
class EvalCompleted(Event):
    bundle_id:  str   = ""
    profile_id: str   = ""
    passed:     bool  = False
    score:      float = 0.0
    summary:    str   = ""
    layer:      str   = Layer.RELIABILITY.value

@dataclass(frozen=True)
class DriftDetected(Event):
    metric:     str   = ""
    profile_id: str   = ""
    current:    float = 0.0
    baseline:   float = 0.0
    delta_pct:  float = 0.0
    severity:   str   = "mild"
    layer:      str   = Layer.RELIABILITY.value

@dataclass(frozen=True)
class ForecastTick(Event):
    horizon:    str   = "7d"
    confidence: float = 0.8
    layer:      str   = Layer.RELIABILITY.value


# ══════════════════════════════════════════════════════
# INTERFACE EVENT — crosses Reliability → Constitutional
# This is the formal Φ_R → Φ_G boundary
# ══════════════════════════════════════════════════════

@dataclass(frozen=True)
class ActionRecommended(Event):
    """
    THE interface event.
    Reliability OS produces this; Constitutional OS consumes it.
    Carries a candidate delta δ ∈ Δ_C.
    """
    action_id:   str   = ""
    delta_type:  str   = ""
    payload:     dict  = field(default_factory=dict)
    rationale:   str   = ""
    urgency:     str   = "normal"   # low | normal | high | critical
    confidence:  float = 0.0
    profile_id:  str   = ""
    forecast_id: str   = ""
    layer:       str   = Layer.INTERFACE.value


# ══════════════════════════════════════════════════════
# CONSTITUTIONAL OS (Σ_C) EVENTS
# ══════════════════════════════════════════════════════

@dataclass(frozen=True)
class ActionProposed(Event):
    """δ enters the proposal lifecycle."""
    proposal_id:  str  = ""
    action_id:    str  = ""
    delta_type:   str  = ""
    payload:      dict = field(default_factory=dict)
    proposer:     str  = ""
    urgency:      str  = "normal"
    layer:        str  = Layer.CONSTITUTIONAL.value

@dataclass(frozen=True)
class InvariantChecked(Event):
    proposal_id:  str  = ""
    invariant_id: str  = ""
    passed:       bool = False
    reason:       str  = ""
    layer:        str  = Layer.CONSTITUTIONAL.value

@dataclass(frozen=True)
class MembraneChecked(Event):
    proposal_id:  str  = ""
    membrane_id:  str  = ""
    verdict:      str  = "pass"
    reason:       str  = ""
    layer:        str  = Layer.CONSTITUTIONAL.value

@dataclass(frozen=True)
class HumanVetoWindowOpened(Event):
    proposal_id:  str = ""
    window_secs:  int = 300
    layer:        str = Layer.CONSTITUTIONAL.value

@dataclass(frozen=True)
class HumanApproved(Event):
    proposal_id:  str = ""
    approved_by:  str = "human"
    layer:        str = Layer.CONSTITUTIONAL.value

@dataclass(frozen=True)
class HumanVetoed(Event):
    proposal_id:  str = ""
    reason:       str = ""
    vetoed_by:    str = "human"
    layer:        str = Layer.CONSTITUTIONAL.value

@dataclass(frozen=True)
class ActionRatified(Event):
    """δ passed all checks and veto window. Ready to apply."""
    proposal_id:  str = ""
    action_id:    str = ""
    delta_type:   str = ""
    payload:      dict = field(default_factory=dict)
    layer:        str = Layer.CONSTITUTIONAL.value

@dataclass(frozen=True)
class ActionExecuted(Event):
    proposal_id:  str = ""
    action_id:    str = ""
    result:       str = "ok"
    new_version:  int = 0
    layer:        str = Layer.CONSTITUTIONAL.value

@dataclass(frozen=True)
class ActionRolledBack(Event):
    proposal_id:        str = ""
    action_id:          str = ""
    reason:             str = ""
    rolled_back_to_ver: int = 0
    layer:              str = Layer.CONSTITUTIONAL.value

@dataclass(frozen=True)
class InvariantViolated(Event):
    invariant_id: str = ""
    context:      str = ""
    severity:     str = "error"   # warning | error | fatal
    layer:        str = Layer.CONSTITUTIONAL.value


# ══════════════════════════════════════════════════════
# SYSTEM EVENTS
# ══════════════════════════════════════════════════════

@dataclass(frozen=True)
class SystemBooted(Event):
    version: str = "0.1.0"
    layer:   str = Layer.SYSTEM.value

@dataclass(frozen=True)
class SystemPaused(Event):
    reason:  str = ""
    layer:   str = Layer.SYSTEM.value

@dataclass(frozen=True)
class SystemResumed(Event):
    layer:   str = Layer.SYSTEM.value


# ══════════════════════════════════════════════════════
# DISPATCHER
# ══════════════════════════════════════════════════════

Handler = Callable[["MetaState", Event], tuple["MetaState", list[Event]]]


class EventDispatcher:
    """
    Maps event types → handlers.
    Handler: (Σ, event) -> (Σ', [new_events])
    New events cascade (BFS, depth-limited).
    """

    def __init__(self):
        self._handlers: dict[type, list[Handler]] = {}
        self._middleware: list[Callable] = []
        self._dead_letter: list[tuple]   = []
        self._event_log: list[Event]     = []

    def register(self, event_type: type, handler: Handler) -> None:
        self._handlers.setdefault(event_type, []).append(handler)

    def middleware(self, fn: Callable) -> None:
        self._middleware.append(fn)

    def dispatch(
        self,
        state: "MetaState",
        event: Event,
        _depth: int = 0,
    ) -> "MetaState":
        if _depth > 30:
            self._dead_letter.append(("max_depth", event))
            return state

        self._event_log.append(event)

        for mw in self._middleware:
            try: mw(state, event)
            except Exception: pass

        handlers = self._handlers.get(type(event), [])
        if not handlers:
            self._dead_letter.append(("unhandled", event))

        new_events: list[Event] = []
        for handler in handlers:
            try:
                state, emitted = handler(state, event)
                new_events.extend(emitted)
            except Exception as e:
                self._dead_letter.append(("error", event, str(e)))

        for ev in new_events:
            state = self.dispatch(state, ev, _depth + 1)

        return state

    def handlers_for(self, event_type: type) -> list[Handler]:
        return self._handlers.get(event_type, [])

    def recent_events(self, n: int = 20) -> list[dict]:
        return [
            {"type": type(e).__name__, "layer": e.layer, "ts": e.ts}
            for e in self._event_log[-n:]
        ]

    def dead_letters(self) -> list:
        return list(self._dead_letter)
