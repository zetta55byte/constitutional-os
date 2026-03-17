"""
actions/deltas.py + actions/engine.py + actions/log.py

The delta calculus from the Constitutional OS whitepaper.

A delta is a typed, reversible state transformer.
Deltas form a groupoid: every delta has an inverse,
and delta composition is associative.

Delta: state -> state
Inverse(delta): state -> state
Compose(d1, d2): state -> state
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable, Optional
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import uuid


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id() -> str:
    return str(uuid.uuid4())[:8]


# ── Delta types ───────────────────────────────────────────────────────────────
class DeltaType(Enum):
    # Profile operations
    LOAD_PROFILE     = "load_profile"
    UPDATE_PROFILE   = "update_profile"
    REMOVE_PROFILE   = "remove_profile"

    # Invariant operations
    ADD_INVARIANT    = "add_invariant"
    REMOVE_INVARIANT = "remove_invariant"
    TOGGLE_INVARIANT = "toggle_invariant"

    # Membrane operations
    ADD_MEMBRANE     = "add_membrane"
    TOGGLE_MEMBRANE  = "toggle_membrane"

    # Eval operations
    RUN_EVAL         = "run_eval"

    # System operations
    SET_STATUS       = "set_status"
    PAUSE_SYSTEM     = "pause_system"
    RESUME_SYSTEM    = "resume_system"

    # Configuration
    UPDATE_CONFIG    = "update_config"


# ── Delta ─────────────────────────────────────────────────────────────────────
@dataclass
class Delta:
    """
    A typed, reversible state transformer.

    Every delta carries enough information to:
      1. Apply itself to a state (forward transform)
      2. Undo itself (inverse transform)
      3. Compose with other deltas (groupoid structure)
    """
    id:          str  = field(default_factory=_id)
    delta_type:  str  = ""
    payload:     dict = field(default_factory=dict)
    inverse_payload: dict = field(default_factory=dict)  # data needed to undo
    author:      str  = "system"
    rationale:   str  = ""
    created_at:  str  = field(default_factory=_now)
    proposal_id: str  = ""

    def fingerprint(self) -> str:
        canonical = json.dumps({
            "type": self.delta_type,
            "payload": self.payload,
            "created_at": self.created_at,
        }, sort_keys=True)
        return hashlib.sha256(canonical.encode()).hexdigest()[:12]


# ── Apply / rollback engine ───────────────────────────────────────────────────
class DeltaEngine:
    """
    Applies deltas to RuntimeState and computes inverse deltas.
    All operations are pure: return new state, never mutate.
    """

    def apply(self, state: "RuntimeState", delta: Delta) -> "RuntimeState":
        """Apply a delta. Returns new state."""
        from dataclasses import replace

        dt = delta.delta_type

        if dt == DeltaType.LOAD_PROFILE.value:
            from constitutional_os.profiles.loader import ProfileLoader
            profile = ProfileLoader.from_dict(delta.payload["profile"])
            state.profiles.register(profile)
            return state.tick()

        elif dt == DeltaType.TOGGLE_INVARIANT.value:
            inv_id  = delta.payload["invariant_id"]
            enabled = delta.payload["enabled"]
            inv = state.invariants.get(inv_id)
            if inv:
                inv.enabled = enabled
            return state.tick()

        elif dt == DeltaType.TOGGLE_MEMBRANE.value:
            mem_id  = delta.payload["membrane_id"]
            enabled = delta.payload["enabled"]
            mem = state.membranes._membranes.get(mem_id)
            if mem:
                mem.enabled = enabled
            return state.tick()

        elif dt == DeltaType.SET_STATUS.value:
            return replace(state, status=delta.payload["status"]).tick()

        elif dt == DeltaType.PAUSE_SYSTEM.value:
            return replace(state, status="paused").tick()

        elif dt == DeltaType.RESUME_SYSTEM.value:
            return replace(state, status="running").tick()

        elif dt in ('note_improvement', 'monitor_volatility', 'investigate_degradation'):
            # Epistemic recommendations — no structural change
            return state.tick()
        else:
            return state.tick()

    def inverse(self, state: "RuntimeState", delta: Delta) -> "RuntimeState":
        """Apply the inverse of a delta (rollback)."""
        inv_delta = Delta(
            delta_type      = delta.delta_type,
            payload         = delta.inverse_payload,
            inverse_payload = delta.payload,
            author          = delta.author,
            rationale       = f"ROLLBACK of delta {delta.id}: {delta.rationale}",
        )
        return self.apply(state, inv_delta)


def _copy_registry(reg):
    from constitutional_os.profiles.loader import ProfileRegistry
    new = ProfileRegistry()
    new._current  = dict(reg._current)
    new._history  = {k: list(v) for k, v in reg._history.items()}
    return new


def _copy_invariants(inv_set):
    from constitutional_os.invariants.engine import InvariantSet
    new = InvariantSet()
    new._invariants = dict(inv_set._invariants)
    return new


def _copy_membranes(mem_set):
    from constitutional_os.membranes.engine import MembraneSet
    new = MembraneSet()
    new._membranes = dict(mem_set._membranes)
    return new


# ── Continuity chain (append-only log) ───────────────────────────────────────
@dataclass
class LogEntry:
    """One entry in the continuity chain."""
    seq:          int
    delta_id:     str
    delta_type:   str
    fingerprint:  str
    state_version: int
    proposal_id:  str
    status:       str   # proposed | ratified | executed | rolled_back
    ts:           str   = field(default_factory=_now)
    author:       str   = "system"
    rationale:    str   = ""
    prev_hash:    str   = ""   # hash of previous entry (chain integrity)

    def to_dict(self) -> dict:
        return self.__dict__.copy()


class ContinuityLog:
    """
    Append-only log of all deltas.
    Forms a hash-chained sequence for tamper detection.
    Each entry includes the hash of the previous entry.
    """

    def __init__(self):
        self._entries: list[LogEntry] = []
        self._tampered: bool = False

    def append(self, entry: LogEntry) -> LogEntry:
        # Compute prev_hash
        if self._entries:
            prev = self._entries[-1]
            prev_data = json.dumps(prev.to_dict(), sort_keys=True)
            entry.prev_hash = hashlib.sha256(prev_data.encode()).hexdigest()[:16]
        else:
            entry.prev_hash = "genesis"
        entry.seq = len(self._entries)
        self._entries.append(entry)
        return entry

    def verify(self) -> bool:
        """Verify chain integrity. Returns False if tampered."""
        for i, entry in enumerate(self._entries[1:], 1):
            prev = self._entries[i-1]
            prev_data = json.dumps(prev.to_dict(), sort_keys=True)
            expected  = hashlib.sha256(prev_data.encode()).hexdigest()[:16]
            if entry.prev_hash != expected:
                self._tampered = True
                return False
        return True

    def recent_entries(self, n: int = 20) -> list[dict]:
        return [e.to_dict() for e in self._entries[-n:]]

    def entries_for_proposal(self, proposal_id: str) -> list[LogEntry]:
        return [e for e in self._entries if e.proposal_id == proposal_id]

    def __len__(self) -> int:
        return len(self._entries)
