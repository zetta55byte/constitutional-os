"""
membranes/engine.py + membranes/library.py

Membranes are directional filters on state transitions.
Unlike invariants (which are always-true predicates),
membranes check whether a SPECIFIC PROPOSED CHANGE is allowed.

The four canonical membranes from the Constitutional OS whitepaper:
  1. Safety membrane        — change must not increase harm potential
  2. Reversibility membrane — change must be undoable
  3. Pluralism membrane     — change must not reduce option space
  4. Human primacy membrane — changes above threshold require human approval

Membrane: (state, proposed_delta) -> MembraneResult
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Any, Optional
from enum import Enum


# ── Result types ──────────────────────────────────────────────────────────────
class MembraneVerdict(Enum):
    PASS    = "pass"
    BLOCK   = "block"
    DEFER   = "defer"    # require human review before proceeding


@dataclass
class MembraneResult:
    membrane_id: str
    verdict:     MembraneVerdict
    reason:      str = ""
    conditions:  list[str] = field(default_factory=list)   # conditions to pass

    @property
    def passed(self) -> bool:
        return self.verdict == MembraneVerdict.PASS

    @property
    def deferred(self) -> bool:
        return self.verdict == MembraneVerdict.DEFER

    def __bool__(self) -> bool:
        return self.passed


@dataclass
class MembraneSetResult:
    results:    list[MembraneResult] = field(default_factory=list)
    verdict:    MembraneVerdict = MembraneVerdict.PASS
    blockers:   list[str] = field(default_factory=list)
    deferrals:  list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.verdict == MembraneVerdict.PASS

    def summary(self) -> str:
        if self.verdict == MembraneVerdict.PASS:
            return f"All {len(self.results)} membranes passed"
        elif self.verdict == MembraneVerdict.BLOCK:
            return f"BLOCKED by: {', '.join(self.blockers)}"
        else:
            return f"DEFERRED for human review: {', '.join(self.deferrals)}"


# ── Delta descriptor (what we're checking) ────────────────────────────────────
@dataclass
class ProposedDelta:
    """Describes a proposed state change for membrane evaluation."""
    delta_type:  str              # the type of change
    payload:     dict             # the change parameters
    autonomy:    str = "assisted" # autonomous | assisted | human-directed
    severity:    str = "normal"   # trivial | normal | significant | critical
    reversible:  bool = True      # is this change undoable?
    scope:       str = "local"    # local | global | constitutional
    requester:   str = "system"


# ── Membrane type ─────────────────────────────────────────────────────────────
MembraneFn = Callable[["RuntimeState", ProposedDelta], MembraneResult]


@dataclass
class Membrane:
    id:          str
    name:        str
    description: str
    fn:          MembraneFn
    enabled:     bool = True
    order:       int  = 0    # lower = checked first


# ── Membrane set ──────────────────────────────────────────────────────────────
class MembraneSet:
    def __init__(self):
        self._membranes: dict[str, Membrane] = {}

    def register(self, mem: Membrane) -> None:
        self._membranes[mem.id] = mem

    def check_all(
        self,
        state:  "RuntimeState",
        delta:  ProposedDelta,
    ) -> MembraneSetResult:
        results   = []
        blockers  = []
        deferrals = []

        ordered = sorted(self._membranes.values(), key=lambda m: m.order)

        for mem in ordered:
            if not mem.enabled:
                continue
            try:
                result = mem.fn(state, delta)
                result.membrane_id = mem.id
            except Exception as e:
                result = MembraneResult(
                    membrane_id = mem.id,
                    verdict     = MembraneVerdict.BLOCK,
                    reason      = f"Membrane raised exception: {e}",
                )
            results.append(result)
            if result.verdict == MembraneVerdict.BLOCK:
                blockers.append(mem.id)
            elif result.verdict == MembraneVerdict.DEFER:
                deferrals.append(mem.id)

        if blockers:
            verdict = MembraneVerdict.BLOCK
        elif deferrals:
            verdict = MembraneVerdict.DEFER
        else:
            verdict = MembraneVerdict.PASS

        return MembraneSetResult(
            results   = results,
            verdict   = verdict,
            blockers  = blockers,
            deferrals = deferrals,
        )

    def __len__(self) -> int:
        return len(self._membranes)


# ── Built-in membrane library ─────────────────────────────────────────────────
def load_default_membranes() -> MembraneSet:
    """Load the four canonical membranes from the Constitutional OS spec."""
    mem_set = MembraneSet()

    # ── M1: Safety membrane ───────────────────────────────────────────────────
    def safety_membrane(state, delta: ProposedDelta) -> MembraneResult:
        """
        A change must not increase the harm potential of the system.
        Critical/fatal changes are blocked unless explicitly safety-cleared.
        """
        if delta.severity == "critical" and delta.autonomy == "autonomous":
            return MembraneResult(
                membrane_id = "M1_safety",
                verdict     = MembraneVerdict.BLOCK,
                reason      = ("Critical autonomous changes are blocked. "
                               "Requires human-directed autonomy level."),
            )
        if delta.scope == "constitutional" and delta.autonomy != "human-directed":
            return MembraneResult(
                membrane_id = "M1_safety",
                verdict     = MembraneVerdict.BLOCK,
                reason      = "Constitutional-scope changes require human direction.",
            )
        return MembraneResult("M1_safety", MembraneVerdict.PASS)

    mem_set.register(Membrane(
        id          = "M1_safety",
        name        = "Safety Membrane",
        description = "Changes must not increase harm potential",
        fn          = safety_membrane,
        order       = 1,
    ))

    # ── M2: Reversibility membrane ────────────────────────────────────────────
    def reversibility_membrane(state, delta: ProposedDelta) -> MembraneResult:
        """
        Changes must be reversible, OR explicitly flagged as irreversible
        with human approval required.
        """
        if not delta.reversible and delta.autonomy == "autonomous":
            return MembraneResult(
                membrane_id = "M2_reversibility",
                verdict     = MembraneVerdict.DEFER,
                reason      = ("Irreversible autonomous change requires human review "
                               "before execution."),
                conditions  = ["human_approval_required"],
            )
        return MembraneResult("M2_reversibility", MembraneVerdict.PASS)

    mem_set.register(Membrane(
        id          = "M2_reversibility",
        name        = "Reversibility Membrane",
        description = "Irreversible autonomous changes require human review",
        fn          = reversibility_membrane,
        order       = 2,
    ))

    # ── M3: Pluralism membrane ────────────────────────────────────────────────
    def pluralism_membrane(state, delta: ProposedDelta) -> MembraneResult:
        """
        A change must not eliminate future option space.
        No single change should make other changes permanently impossible.
        """
        # Check if delta type is a lock-in operation
        lock_in_types = {
            "remove_membrane", "disable_invariant",
            "revoke_human_primacy", "seal_state",
        }
        if delta.delta_type in lock_in_types:
            return MembraneResult(
                membrane_id = "M3_pluralism",
                verdict     = MembraneVerdict.BLOCK,
                reason      = (f"Delta type '{delta.delta_type}' would eliminate "
                               f"future option space. Blocked by pluralism membrane."),
            )
        return MembraneResult("M3_pluralism", MembraneVerdict.PASS)

    mem_set.register(Membrane(
        id          = "M3_pluralism",
        name        = "Pluralism Membrane",
        description = "Changes must not eliminate future option space",
        fn          = pluralism_membrane,
        order       = 3,
    ))

    # ── M4: Human primacy membrane ────────────────────────────────────────────
    def human_primacy_membrane(state, delta: ProposedDelta) -> MembraneResult:
        """
        Changes above a significance threshold require human approval.
        This is the core constitutional guarantee.
        """
        significant_levels = {"significant", "critical"}
        requires_human = (
            delta.severity in significant_levels
            or delta.scope in {"global", "constitutional"}
            or not delta.reversible
        )

        if requires_human and delta.autonomy == "autonomous":
            return MembraneResult(
                membrane_id = "M4_human_primacy",
                verdict     = MembraneVerdict.DEFER,
                reason      = (f"Change (severity={delta.severity}, "
                               f"scope={delta.scope}) requires human approval. "
                               f"Opening veto window."),
                conditions  = ["human_veto_window"],
            )
        return MembraneResult("M4_human_primacy", MembraneVerdict.PASS)

    mem_set.register(Membrane(
        id          = "M4_human_primacy",
        name        = "Human Primacy Membrane",
        description = "Significant changes require human approval",
        fn          = human_primacy_membrane,
        order       = 4,
    ))

    return mem_set
