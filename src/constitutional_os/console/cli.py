"""
console/cli.py
Command-line console for the epistemic-governance stack.

Commands:
  boot [--profiles DIR]     Boot the runtime
  status                    Show Σ summary
  profile load <path>       Load a profile
  profile list              List all profiles
  eval run <bundle> [<pid>] Run eval bundle
  invariants                Check all invariants
  membranes <delta_type>    Test membranes against a delta
  forecast <profile_id>     Show forecast for a profile
  recommend                 Run Φ = G∘E and show result
  log [--n N]               Tail continuity log
  events [--n N]            Recent event log
  rollback [--steps N]      Roll back N state transitions
  history                   Show state history
  observe <metric> <value>  Inject an observation from reality
"""

from __future__ import annotations
import sys
import json
from typing import Optional

_store      = None
_dispatcher = None


def _rt():
    if _store is None:
        print("Not booted. Run: boot")
        sys.exit(1)
    return _store, _dispatcher


def cmd_boot(profiles_dir=None, strict=False, verbose=True):
    global _store, _dispatcher
    from constitutional_os.runtime.boot import boot
    _store, _dispatcher = boot(profiles_dir=profiles_dir, strict=strict, verbose=verbose)
    print(json.dumps(_store.current.summary(), indent=2))


def cmd_status():
    store, _ = _rt()
    print(json.dumps(store.current.summary(), indent=2))


def cmd_profile_load(path: str):
    store, dispatcher = _rt()
    from constitutional_os.profiles.loader import ProfileLoader
    from constitutional_os.runtime.events import ProfileLoaded
    try:
        profile = ProfileLoader.from_file(path)
        store.current.profiles.register(profile)
        state = dispatcher.dispatch(store.current, ProfileLoaded(
            profile_id=profile.id, profile_name=profile.name, version=profile.version,
        ))
        store.apply(state)
        print(f"Loaded: {profile.id} v{profile.version}")
        print(json.dumps(profile.to_dict(), indent=2))
    except Exception as e:
        print(f"ERROR: {e}")


def cmd_profile_list():
    store, _ = _rt()
    for p in store.current.profiles.all():
        metrics = len(p.metrics)
        evals   = len(p.evals)
        print(f"  {p.id:<30} v{p.version:<8} {metrics:2d} metrics  {evals:2d} evals  {p.name}")


def cmd_eval_run(bundle_id: str, profile_id: str = ""):
    store, _ = _rt()
    from constitutional_os.evals.runner import EvalRunner
    report = EvalRunner().run(bundle_id, store.current, profile_id)
    store.current.eval_history.append(report)
    print(json.dumps(report.to_dict(), indent=2))


def cmd_invariants():
    store, _ = _rt()
    result = store.current.invariants.check_all(store.current)
    status = "PASS" if result else "FAIL"
    print(f"Invariants: {status} — {result.summary()}")
    for r in result.results:
        mark = "✓" if r.passed else "✗"
        print(f"  {mark} [{r.severity.value:7s}] {r.invariant_id:<35} {r.reason or 'ok'}")


def cmd_membranes(delta_type: str = "test", severity: str = "normal",
                  autonomy: str = "autonomous"):
    store, _ = _rt()
    from constitutional_os.membranes.engine import ProposedDelta
    delta = ProposedDelta(
        delta_type=delta_type, payload={},
        autonomy=autonomy, severity=severity, reversible=True, scope="local",
    )
    result = store.current.membranes.check_all(store.current, delta)
    print(f"Verdict: {result.verdict.value} — {result.summary()}")
    for r in result.results:
        print(f"  {r.membrane_id:<30} {r.verdict.value:<8}  {r.reason or 'ok'}")


def cmd_forecast(profile_id: str, metric: str = "response_quality"):
    store, _ = _rt()
    from constitutional_os.forecast.engine import ForecastEngine
    import random, math
    engine = ForecastEngine()
    # Simulate a degrading metric history
    history = [0.9 - i * 0.015 + random.gauss(0, 0.01) for i in range(14)]
    curve   = engine.project(metric, profile_id, history)
    rec     = engine.recommend(curve)

    print(f"Profile:  {profile_id}")
    print(f"Metric:   {metric}")
    print(f"Trend:    {curve.trend}   Risk: {curve.risk_level}")
    print()
    for p in curve.points:
        bar = "█" * int(p.confidence * 16)
        print(f"  Day {p.t:2d}: {p.value:6.3f}  [{p.lower:.3f}–{p.upper:.3f}]"
              f"  {p.confidence:.0%}  {bar}")
    if rec:
        print(f"\nRecommendation: {rec.action_type}  urgency={rec.urgency}")
        print(f"  {rec.rationale}")


def cmd_recommend():
    """Run one Φ = G∘E cycle and show the result."""
    store, dispatcher = _rt()
    from constitutional_os.runtime.operators import phi
    from constitutional_os.evals.runner       import EvalRunner
    from constitutional_os.forecast.engine    import ForecastEngine
    import random

    # Build synthetic history for demo
    history_map = {}
    for p in store.current.profiles.all():
        for m in p.metrics:
            key = f"{p.id}:{m.name}"
            history_map[key] = [
                (m.baseline or 0.8) - i * 0.01 + random.gauss(0, 0.02)
                for i in range(14)
            ]

    result = phi(
        state        = store.current,
        eval_runner  = EvalRunner(),
        forecast_eng = ForecastEngine(),
        dispatcher   = dispatcher,
        history_map  = history_map,
    )

    store.apply(result.new_state)

    print(f"\n{'─'*50}")
    print(f"Φ = G ∘ E  (one full cycle)")
    print(f"{'─'*50}")
    print(f"Fixed point reached: {result.is_fixed_point}")
    print()

    e = result.epistemic_result
    print(f"E (Reliability OS):")
    print(f"  Eval summaries:  {len(e.eval_summaries or [])} bundles run")
    print(f"  Drift alerts:    {len(e.drift_alerts or [])}")
    if e.recommendation:
        print(f"  Recommendation:  {e.recommendation.delta_type}  urgency={e.recommendation.urgency}")
        print(f"    {e.recommendation.rationale[:80]}")
    else:
        print(f"  Recommendation:  none")
    print()

    g = result.governance_result
    print(f"G (Constitutional OS):")
    print(f"  Verdict:         {g.verdict}")
    if g.proposal_id:
        print(f"  Proposal ID:     {g.proposal_id}")
    if g.blockers:
        print(f"  Blockers:        {g.blockers}")
    if g.deferrals:
        print(f"  Deferrals (→ human review): {g.deferrals}")
    print()
    print(f"New Σ version: {result.new_state.version}")


def cmd_log(n: int = 20):
    store, _ = _rt()
    entries = store.current.actions_log.recent_entries(n)
    print(f"Continuity log ({len(store.current.actions_log)} total):")
    for e in entries:
        print(f"  [{e.get('seq',0):4d}] {e.get('ts','')[:19]}  "
              f"{e.get('delta_type',''):25s}  {e.get('status',''):20s}  "
              f"{e.get('rationale','')[:50]}")


def cmd_events(n: int = 20):
    _, dispatcher = _rt()
    events = dispatcher.recent_events(n)
    print(f"Recent events ({n}):")
    for e in events:
        print(f"  {e['ts'][:19]}  [{e['layer']:14s}]  {e['type']}")


def cmd_observe(metric: str, value: float, source: str = "external"):
    store, dispatcher = _rt()
    from constitutional_os.runtime.events import ObservationIngested
    state = dispatcher.dispatch(store.current, ObservationIngested(
        source=source, metric=metric, value=value,
    ))
    store.apply(state)
    print(f"Observed: {source}/{metric} = {value}")


def cmd_rollback(steps: int = 1):
    store, _ = _rt()
    state = store.rollback(steps)
    print(f"Rolled back {steps} step(s). Now at version {state.version}")
    print(json.dumps(state.summary(), indent=2))


def cmd_history():
    store, _ = _rt()
    for s in store.history_summary():
        print(f"  v{s['version']:4d}  {s['tick'][:19]}  {s['status']}")


def main(argv=None):
    args = (argv or sys.argv)[1:]
    if not args:
        print(__doc__)
        return

    cmd = args[0]

    if cmd == "boot":
        d = args[1] if len(args) > 1 and not args[1].startswith("-") else None
        cmd_boot(profiles_dir=d)
    elif cmd == "status":
        cmd_status()
    elif cmd == "profile":
        sub = args[1] if len(args) > 1 else ""
        if sub == "load" and len(args) > 2:   cmd_profile_load(args[2])
        elif sub == "list":                    cmd_profile_list()
        else: print("profile load <path> | profile list")
    elif cmd == "eval":
        sub = args[1] if len(args) > 1 else ""
        if sub == "run" and len(args) > 2:
            pid = args[4] if "--profile" in args and len(args) > 4 else ""
            cmd_eval_run(args[2], pid)
        else: print("eval run <bundle_id> [--profile <id>]")
    elif cmd == "invariants":  cmd_invariants()
    elif cmd == "membranes":
        dt  = args[1] if len(args) > 1 else "test"
        sev = args[2] if len(args) > 2 else "normal"
        cmd_membranes(dt, sev)
    elif cmd == "forecast":
        pid = args[1] if len(args) > 1 else "demo"
        m   = args[2] if len(args) > 2 else "response_quality"
        cmd_forecast(pid, m)
    elif cmd == "recommend":   cmd_recommend()
    elif cmd == "log":
        n = int(args[1]) if len(args) > 1 else 20
        cmd_log(n)
    elif cmd == "events":
        n = int(args[1]) if len(args) > 1 else 20
        cmd_events(n)
    elif cmd == "observe" and len(args) >= 3:
        cmd_observe(args[1], float(args[2]),
                    args[3] if len(args) > 3 else "external")
    elif cmd == "rollback":
        n = int(args[2]) if "--steps" in args and len(args) > 2 else 1
        cmd_rollback(n)
    elif cmd == "history":     cmd_history()
    else:
        print(f"Unknown: {cmd}")
        print(__doc__)


if __name__ == "__main__":
    # Interactive mode
    print("Epistemic-Governance Stack — Interactive Console")
    cmd_boot(verbose=False)
    main(["recommend"])


def cmd_stability(v_history=None):
    """Full stability analysis: V(S), basin, separatrix, A-safety theorem."""
    store, _ = _rt()
    from constitutional_os.runtime.theory import stability_report
    report = stability_report(store.current, v_history=v_history)
    print("\n" + "═" * 56)
    print("  Stability Report")
    print("═" * 56)
    print(report.summary)
    print()
    print(f"V(S) decomposition:")
    for k, v in report.lyapunov.components.items():
        bar = "█" * int(v * 30)
        print(f"  {k:<12} {v:.4f}  {bar}")
    print(f"  {'TOTAL':<12} {report.lyapunov.total:.4f}")
    print()
    print(f"A-safety theorem:")
    print(f"  {report.a_safety.proof}")
    if report.a_safety.checks:
        for c in report.a_safety.checks:
            mark = "✓" if c.is_safe else "✗"
            print(f"  {mark} {c.delta_type:<30} inv={'✓' if c.invariants_hold else '✗'}"
                  f"  mem={'✓' if c.membranes_pass else '✗'}")
    print()
    print(f"V trajectory: {[round(v,3) for v in report.v_trajectory]}")
    print(f"Converging:   {'yes ↓' if report.converging else 'no ↑ — WARNING'}")
