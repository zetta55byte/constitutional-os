"""
constitutional-os
=================

A formal runtime for epistemic-governance systems.

Two-layer architecture:
  Reliability OS  — evaluates reality (profiles, evals, forecasts)
  Constitutional OS — governs change (invariants, membranes, delta calculus)

Quick start
-----------
    from constitutional_os import boot, phi

    store, dispatcher = boot()
    result = phi(store.current, ...)

Full API
--------
    from constitutional_os.runtime.boot      import boot
    from constitutional_os.runtime.operators import phi, phi_with_stability
    from constitutional_os.runtime.theory    import lyapunov, stability_report
    from constitutional_os.profiles.loader   import ProfileLoader, ProfileRegistry
    from constitutional_os.invariants.engine import load_default_invariants
    from constitutional_os.membranes.engine  import load_default_membranes
    from constitutional_os.evals.runner      import EvalRunner
    from constitutional_os.forecast.engine   import ForecastEngine
    from constitutional_os.actions.deltas    import Delta, DeltaType, ContinuityLog

Version
-------
    constitutional_os.__version__  -> '0.1.0'
"""

__version__ = "0.1.0"
__author__ = "Independent Researcher"
__license__ = "Apache-2.0"

# ── Convenience top-level imports ─────────────────────────────────────────────
from constitutional_os.actions.deltas import (
    ContinuityLog,
    Delta,
    DeltaType,
    LogEntry,
)
from constitutional_os.evals.runner import (
    EvalBundle,
    EvalCheck,
    EvalHistory,
    EvalReport,
    EvalRunner,
    Finding,
    FindingSeverity,
)
from constitutional_os.forecast.engine import (
    ForecastCurve,
    ForecastEngine,
    ForecastRecommendation,
    ForecastState,
    risk_heatmap,
)
from constitutional_os.invariants.engine import (
    Invariant,
    InvariantResult,
    InvariantSet,
    InvariantSeverity,
    load_default_invariants,
)
from constitutional_os.membranes.engine import (
    Membrane,
    MembraneResult,
    MembraneSet,
    MembraneVerdict,
    ProposedDelta,
    load_default_membranes,
)
from constitutional_os.profiles.loader import (
    EvalSpec,
    MetricSpec,
    Profile,
    ProfileLoader,
    ProfileRegistry,
    diff_profiles,
)
from constitutional_os.runtime.boot import boot
from constitutional_os.runtime.events import (
    ActionExecuted,
    # Constitutional OS events
    ActionProposed,
    ActionRatified,
    # Interface event
    ActionRecommended,
    DriftDetected,
    EvalCompleted,
    EvalRequested,
    EventDispatcher,
    ForecastTick,
    HumanApproved,
    HumanVetoed,
    InvariantViolated,
    # Reliability OS events
    ProfileLoaded,
)
from constitutional_os.runtime.operators import phi, phi_with_stability
from constitutional_os.runtime.state import MetaState, StateStore
from constitutional_os.runtime.theory import (
    analyze_basin,
    check_a_safety,
    lyapunov,
    separatrix_proximity,
    stability_report,
)

__all__ = [
    # Core
    "boot",
    "phi",
    "phi_with_stability",
    # Theory
    "lyapunov",
    "stability_report",
    "check_a_safety",
    "analyze_basin",
    "separatrix_proximity",
    # State
    "MetaState",
    "StateStore",
    # Events
    "EventDispatcher",
    "ProfileLoaded",
    "EvalRequested",
    "EvalCompleted",
    "DriftDetected",
    "ForecastTick",
    "ActionRecommended",
    "ActionProposed",
    "ActionRatified",
    "ActionExecuted",
    "HumanVetoed",
    "HumanApproved",
    "InvariantViolated",
    # Profiles
    "Profile",
    "ProfileLoader",
    "ProfileRegistry",
    "MetricSpec",
    "EvalSpec",
    "diff_profiles",
    # Invariants
    "Invariant",
    "InvariantSet",
    "InvariantResult",
    "InvariantSeverity",
    "load_default_invariants",
    # Membranes
    "Membrane",
    "MembraneSet",
    "MembraneResult",
    "MembraneVerdict",
    "ProposedDelta",
    "load_default_membranes",
    # Evals
    "EvalBundle",
    "EvalCheck",
    "EvalRunner",
    "EvalReport",
    "EvalHistory",
    "Finding",
    "FindingSeverity",
    # Forecast
    "ForecastEngine",
    "ForecastCurve",
    "ForecastState",
    "ForecastRecommendation",
    "risk_heatmap",
    # Actions
    "Delta",
    "DeltaType",
    "ContinuityLog",
    "LogEntry",
]
