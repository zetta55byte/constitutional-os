"""
forecast/engine.py + forecast/views.py

Forecast engine for Reliability OS.
Produces drift projections, confidence intervals,
heatmaps, and action recommendations based on trend data.

This is the epistemic layer — it tells you what will happen next.
The Constitutional OS then decides what to DO about it.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime, timezone
import math


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Forecast data structures ──────────────────────────────────────────────────
@dataclass
class ForecastPoint:
    """A single point on a forecast curve."""
    t:          float   # time offset (days)
    value:      float   # projected value
    lower:      float   # lower confidence bound
    upper:      float   # upper confidence bound
    confidence: float   # confidence at this point (0-1)


@dataclass
class ForecastCurve:
    """A projected trajectory for a single metric."""
    metric:       str
    profile_id:   str
    horizon_days: int
    points:       list[ForecastPoint] = field(default_factory=list)
    trend:        str = "stable"   # improving | stable | degrading | volatile
    risk_level:   str = "low"      # low | medium | high | critical
    generated_at: str = field(default_factory=_now)

    def at_day(self, day: int) -> Optional[ForecastPoint]:
        return next((p for p in self.points if int(p.t) == day), None)

    def summary(self) -> str:
        if not self.points:
            return f"{self.metric}: no data"
        final = self.points[-1]
        return (f"{self.metric}: {self.trend} trend, "
                f"projected {final.value:.2f} in {self.horizon_days}d "
                f"(confidence={final.confidence:.0%})")


@dataclass
class ForecastRecommendation:
    """
    A recommended action produced by the forecast engine.
    This is the OUTPUT that crosses into Constitutional OS.
    """
    recommendation_id: str
    profile_id:        str
    metric:            str
    action_type:       str
    rationale:         str
    urgency:           str   = "normal"   # low | normal | high | critical
    confidence:        float = 0.0
    forecast_horizon:  int   = 7          # days
    generated_at:      str   = field(default_factory=_now)


@dataclass
class ForecastState:
    """All current forecasts and recommendations."""
    curves:          dict[str, ForecastCurve] = field(default_factory=dict)
    recommendations: list[ForecastRecommendation] = field(default_factory=list)
    last_updated:    str = field(default_factory=_now)

    def add_curve(self, curve: ForecastCurve) -> None:
        key = f"{curve.profile_id}:{curve.metric}"
        self.curves[key] = curve

    def add_recommendation(self, rec: ForecastRecommendation) -> None:
        self.recommendations.append(rec)

    def pending_recommendations(self) -> list[ForecastRecommendation]:
        return [r for r in self.recommendations if r.urgency in ("high", "critical")]


# ── Forecast engine ───────────────────────────────────────────────────────────
class ForecastEngine:
    """
    Projects metric trajectories and generates action recommendations.

    Uses exponential smoothing for trend estimation and
    Kalman-style confidence intervals.
    """

    def __init__(self, alpha: float = 0.3, horizon_days: int = 7):
        self.alpha        = alpha         # smoothing factor
        self.horizon_days = horizon_days

    def project(
        self,
        metric:     str,
        profile_id: str,
        history:    list[float],   # recent observations, oldest first
        horizon:    int = None,
    ) -> ForecastCurve:
        """
        Project a metric forward using exponential smoothing.
        Returns a ForecastCurve with confidence intervals.
        """
        horizon = horizon or self.horizon_days

        if not history:
            return ForecastCurve(metric=metric, profile_id=profile_id,
                                 horizon_days=horizon)

        # Exponential smoothing
        smoothed = history[0]
        for obs in history[1:]:
            smoothed = self.alpha * obs + (1 - self.alpha) * smoothed

        # Trend estimate (linear regression on last N points)
        n = min(len(history), 7)
        recent = history[-n:]
        if n >= 2:
            xs = list(range(n))
            x_mean = sum(xs) / n
            y_mean = sum(recent) / n
            num = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, recent))
            den = sum((x - x_mean) ** 2 for x in xs)
            slope = num / den if den != 0 else 0.0
        else:
            slope = 0.0

        # Residual variance for confidence intervals
        if n >= 2:
            residuals = [abs(recent[i] - (recent[0] + slope * i)) for i in range(n)]
            std = max(sum(residuals) / n, 1e-6)
        else:
            std = abs(smoothed * 0.1) + 0.1

        # Generate forecast points
        points = []
        base = smoothed
        for t in range(1, horizon + 1):
            projected = base + slope * t
            # Confidence decreases with horizon
            confidence = max(0.1, 1.0 - (t / horizon) * 0.6)
            # Confidence intervals widen with horizon
            interval = std * math.sqrt(t) * 1.645  # 90% interval
            points.append(ForecastPoint(
                t          = t,
                value      = round(projected, 4),
                lower      = round(projected - interval, 4),
                upper      = round(projected + interval, 4),
                confidence = round(confidence, 3),
            ))

        # Classify trend
        total_change = points[-1].value - base if points else 0
        pct_change   = total_change / abs(base) if base != 0 else 0

        if abs(pct_change) < 0.03:
            trend = "stable"
        elif pct_change > 0.15:
            trend = "improving" if metric.endswith("_score") else "degrading"
        elif pct_change < -0.15:
            trend = "degrading" if metric.endswith("_score") else "improving"
        else:
            trend = "slowly_changing"

        # Classify risk
        vol = std / (abs(smoothed) + 1e-6)
        if abs(pct_change) > 0.3 or vol > 0.4:
            risk = "critical"
        elif abs(pct_change) > 0.15 or vol > 0.2:
            risk = "high"
        elif abs(pct_change) > 0.05:
            risk = "medium"
        else:
            risk = "low"

        return ForecastCurve(
            metric       = metric,
            profile_id   = profile_id,
            horizon_days = horizon,
            points       = points,
            trend        = trend,
            risk_level   = risk,
        )

    def recommend(
        self,
        curve:      ForecastCurve,
        threshold:  Optional[float] = None,
    ) -> Optional[ForecastRecommendation]:
        """
        Generate an action recommendation based on a forecast curve.
        Returns None if no action is warranted.
        """
        import uuid

        if curve.risk_level == "low":
            return None

        # Determine urgency
        urgency_map = {"critical": "critical", "high": "high",
                       "medium": "normal", "low": "low"}
        urgency = urgency_map.get(curve.risk_level, "normal")

        # Determine action type based on trend
        if "degrading" in curve.trend:
            action_type = "investigate_degradation"
        elif "improving" in curve.trend:
            action_type = "note_improvement"
        else:
            action_type = "monitor_volatility"

        final = curve.points[-1] if curve.points else None
        rationale = (
            f"Metric '{curve.metric}' shows {curve.trend} trend "
            f"with {curve.risk_level} risk level. "
            + (f"Projected value in {curve.horizon_days}d: {final.value:.3f}"
               if final else "")
        )

        return ForecastRecommendation(
            recommendation_id = str(uuid.uuid4())[:8],
            profile_id        = curve.profile_id,
            metric            = curve.metric,
            action_type       = action_type,
            rationale         = rationale,
            urgency           = urgency,
            confidence        = final.confidence if final else 0.5,
            forecast_horizon  = curve.horizon_days,
        )

    def run_all(
        self,
        state:        "RuntimeState",
        history_map:  dict[str, list[float]],  # "profile_id:metric" -> [values]
    ) -> ForecastState:
        """Run forecasts for all metric histories. Returns updated ForecastState."""
        from dataclasses import replace
        fs = ForecastState()

        for key, history in history_map.items():
            parts = key.split(":", 1)
            if len(parts) != 2:
                continue
            profile_id, metric = parts
            curve = self.project(metric, profile_id, history)
            fs.add_curve(curve)
            rec = self.recommend(curve)
            if rec:
                fs.add_recommendation(rec)

        return fs


# ── Heatmap view ──────────────────────────────────────────────────────────────
def risk_heatmap(forecast_state: ForecastState) -> dict[str, dict]:
    """
    Build a risk heatmap: profile_id -> {metric -> risk_level}.
    For dashboard display.
    """
    heatmap: dict[str, dict] = {}
    for key, curve in forecast_state.curves.items():
        pid, metric = key.split(":", 1)
        heatmap.setdefault(pid, {})[metric] = {
            "risk":  curve.risk_level,
            "trend": curve.trend,
        }
    return heatmap
