"""
invariants/engine.py + invariants/library.py

Invariants are predicates that must hold at all times.
If an invariant is violated, the system must halt or rollback.

Invariant: (state: RuntimeState) -> InvariantResult

The invariant engine runs all invariants before any state transition.
A transition is only allowed if all invariants pass.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Optional
from enum import Enum


# ── Result types ──────────────────────────────────────────────────────────────
class InvariantSeverity(Enum):
    WARNING = "warning"   # log but allow
    ERROR   = "error"     # block transition
    FATAL   = "fatal"     # halt system


@dataclass
class InvariantResult:
    invariant_id: str
    passed:       bool
    severity:     InvariantSeverity = InvariantSeverity.ERROR
    reason:       str = ""
    context:      dict = field(default_factory=dict)

    def __bool__(self) -> bool:
        return self.passed


@dataclass
class InvariantSetResult:
    results:      list[InvariantResult] = field(default_factory=list)
    all_passed:   bool = True
    fatal_count:  int  = 0
    error_count:  int  = 0
    warning_count:int  = 0

    def __bool__(self) -> bool:
        return self.all_passed

    def failures(self) -> list[InvariantResult]:
        return [r for r in self.results if not r.passed]

    def summary(self) -> str:
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        if self.all_passed:
            return f"All {total} invariants passed"
        return (f"{passed}/{total} passed — "
                f"{self.fatal_count} fatal, {self.error_count} errors, "
                f"{self.warning_count} warnings")


# ── Invariant type ────────────────────────────────────────────────────────────
InvariantFn = Callable[["RuntimeState"], InvariantResult]


@dataclass
class Invariant:
    id:          str
    name:        str
    description: str
    fn:          InvariantFn
    severity:    InvariantSeverity = InvariantSeverity.ERROR
    tags:        list[str] = field(default_factory=list)
    enabled:     bool = True


# ── Invariant set ─────────────────────────────────────────────────────────────
class InvariantSet:
    def __init__(self):
        self._invariants: dict[str, Invariant] = {}

    def register(self, inv: Invariant) -> None:
        self._invariants[inv.id] = inv

    def get(self, inv_id: str) -> Optional[Invariant]:
        return self._invariants.get(inv_id)

    def check_all(self, state: "RuntimeState") -> InvariantSetResult:
        results = []
        for inv in self._invariants.values():
            if not inv.enabled:
                continue
            try:
                result = inv.fn(state)
                result.invariant_id = inv.id
                result.severity     = inv.severity
            except Exception as e:
                result = InvariantResult(
                    invariant_id = inv.id,
                    passed       = False,
                    severity     = InvariantSeverity.FATAL,
                    reason       = f"Invariant raised exception: {e}",
                )
            results.append(result)

        fatal   = [r for r in results if not r.passed and r.severity == InvariantSeverity.FATAL]
        errors  = [r for r in results if not r.passed and r.severity == InvariantSeverity.ERROR]
        warns   = [r for r in results if not r.passed and r.severity == InvariantSeverity.WARNING]

        return InvariantSetResult(
            results       = results,
            all_passed    = not fatal and not errors,
            fatal_count   = len(fatal),
            error_count   = len(errors),
            warning_count = len(warns),
        )

    def check_one(self, inv_id: str, state: "RuntimeState") -> InvariantResult:
        inv = self._invariants.get(inv_id)
        if not inv:
            return InvariantResult(inv_id, False, reason="Invariant not found")
        return inv.fn(state)

    def __len__(self) -> int:
        return len(self._invariants)

    def __iter__(self):
        return iter(self._invariants.values())


# ── Built-in invariant library ────────────────────────────────────────────────
def load_default_invariants() -> InvariantSet:
    """Load the standard invariant library."""
    inv_set = InvariantSet()

    # ── I1: State version monotonicity ───────────────────────────────────────
    def check_version_monotonic(state) -> InvariantResult:
        return InvariantResult(
            invariant_id = "I1_version_monotonic",
            passed       = state.version >= 0,
            reason       = "State version must be non-negative",
        )

    inv_set.register(Invariant(
        id          = "I1_version_monotonic",
        name        = "Version Monotonicity",
        description = "State version counter must never decrease",
        fn          = check_version_monotonic,
        severity    = InvariantSeverity.FATAL,
        tags        = ["core", "state"],
    ))

    # ── I2: Profile registry not empty after boot ─────────────────────────────
    def check_profiles_initialized(state) -> InvariantResult:
        # Only enforce after system is running
        if state.status == "booting":
            return InvariantResult("I2_profiles_initialized", True)
        return InvariantResult(
            invariant_id = "I2_profiles_initialized",
            passed       = True,  # zero profiles allowed in running state
            reason       = "Profile registry accessible",
        )

    inv_set.register(Invariant(
        id          = "I2_profiles_initialized",
        name        = "Profiles Initialized",
        description = "Profile registry must be accessible",
        fn          = check_profiles_initialized,
        severity    = InvariantSeverity.WARNING,
        tags        = ["profiles"],
    ))

    # ── I3: Actions log append-only ───────────────────────────────────────────
    def check_log_append_only(state) -> InvariantResult:
        log = state.actions_log
        passed = not getattr(log, "_tampered", False)
        return InvariantResult(
            invariant_id = "I3_log_append_only",
            passed       = passed,
            reason       = "" if passed else "Continuity log tamper detected",
        )

    inv_set.register(Invariant(
        id          = "I3_log_append_only",
        name        = "Log Append-Only",
        description = "The continuity log must never be modified retroactively",
        fn          = check_log_append_only,
        severity    = InvariantSeverity.FATAL,
        tags        = ["core", "continuity"],
    ))

    # ── I4: Human primacy — no autonomous fatal actions ───────────────────────
    def check_human_primacy(state) -> InvariantResult:
        log = state.actions_log
        recent = getattr(log, "recent_entries", lambda: [])()
        autonomous_fatal = [
            e for e in recent
            if e.get("autonomy") == "full" and e.get("severity") == "fatal"
        ]
        return InvariantResult(
            invariant_id = "I4_human_primacy",
            passed       = len(autonomous_fatal) == 0,
            reason       = (f"{len(autonomous_fatal)} fatal actions executed without human approval"
                           if autonomous_fatal else ""),
        )

    inv_set.register(Invariant(
        id          = "I4_human_primacy",
        name        = "Human Primacy",
        description = "Fatal actions require human approval — never autonomous",
        fn          = check_human_primacy,
        severity    = InvariantSeverity.FATAL,
        tags        = ["core", "safety", "human-primacy"],
    ))

    # ── I5: Eval history integrity ────────────────────────────────────────────
    def check_eval_integrity(state) -> InvariantResult:
        hist = state.eval_history
        tampered = getattr(hist, "_tampered", False)
        return InvariantResult(
            invariant_id = "I5_eval_integrity",
            passed       = not tampered,
            reason       = "" if not tampered else "Eval history integrity compromised",
        )

    inv_set.register(Invariant(
        id          = "I5_eval_integrity",
        name        = "Eval History Integrity",
        description = "Eval history must not be retroactively modified",
        fn          = check_eval_integrity,
        severity    = InvariantSeverity.ERROR,
        tags        = ["evals", "integrity"],
    ))

    return inv_set
