"""
runtime/loop.py
Main event loop. Drives Φ = G ∘ E cycles on a timer.
Also runs invariant checks, forecast ticks, and health evals.
"""

from __future__ import annotations
import time
import threading
from typing import Optional, Callable
from constitutional_os.runtime.events import ForecastTick


class RuntimeLoop:
    def __init__(
        self,
        store:        "StateStore",
        dispatcher:   "EventDispatcher",
        tick_secs:    float = 60.0,
        eval_runner:  "EvalRunner"   = None,
        forecast_eng: "ForecastEngine" = None,
    ):
        self.store        = store
        self.dispatcher   = dispatcher
        self.tick_secs    = tick_secs
        self.eval_runner  = eval_runner
        self.forecast_eng = forecast_eng
        self._running     = False
        self._thread: Optional[threading.Thread] = None
        self._tasks: list[tuple[float, Callable]] = []
        self._last_run: dict[int, float] = {}
        self._cycle_count = 0
        self._register_defaults()

    def add_task(self, interval: float, fn: Callable) -> None:
        self._tasks.append((interval, fn))

    def step(self) -> "MetaState":
        """One loop iteration."""
        from constitutional_os.runtime.operators import phi
        from constitutional_os.evals.runner       import EvalRunner
        from constitutional_os.forecast.engine    import ForecastEngine

        now   = time.time()
        state = self.store.current

        runner  = self.eval_runner  or EvalRunner()
        fengine = self.forecast_eng or ForecastEngine()

        # Build history map from observations
        history_map = {}
        for obs in state.reality.observations[-200:]:
            key = f"{obs.get('source','?')}:{obs.get('metric','value')}"
            history_map.setdefault(key, []).append(float(obs.get('value', 0)))

        # Scheduled tasks
        for i, (interval, fn) in enumerate(self._tasks):
            last = self._last_run.get(i, 0)
            if now - last >= interval:
                try:
                    state = fn(state, self.store, self.dispatcher) or state
                    self.store.apply(state)
                except Exception as e:
                    print(f"[loop] Task {i} error: {e}")
                self._last_run[i] = now

        self._cycle_count += 1
        return state

    def run_forever(self) -> None:
        self._running = True
        print(f"[loop] Starting (tick={self.tick_secs}s)")
        while self._running:
            try:
                self.step()
            except Exception as e:
                print(f"[loop] Error: {e}")
            time.sleep(self.tick_secs)

    def start(self) -> None:
        self._thread = threading.Thread(target=self.run_forever, daemon=True)
        self._thread.start()
        print("[loop] Background thread started")

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        print("[loop] Stopped")

    def _register_defaults(self) -> None:

        def forecast_task(state, store, dispatcher):
            state = dispatcher.dispatch(state, ForecastTick(horizon="7d", confidence=0.8))
            return state
        self.add_task(300, forecast_task)   # every 5 min

        def health_task(state, store, dispatcher):
            from constitutional_os.evals.runner import EvalRunner
            r = EvalRunner()
            report = r.run("core.health", state)
            state.eval_history.append(report)
            if not report.passed:
                print(f"[loop] Health FAILED: {report.summary}")
            return state
        self.add_task(600, health_task)     # every 10 min

        def invariant_task(state, store, dispatcher):
            from constitutional_os.runtime.events import InvariantViolated
            result = state.invariants.check_all(state)
            if not result:
                for f in result.failures():
                    state = dispatcher.dispatch(state, InvariantViolated(
                        invariant_id=f.invariant_id, context=f.reason,
                        severity=f.severity.value,
                    ))
            return state
        self.add_task(120, invariant_task)  # every 2 min
