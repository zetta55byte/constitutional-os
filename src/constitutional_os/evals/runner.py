"""
evals/runner.py + evals/bundles.py + evals/reports.py

Eval bundles are collections of checks that assess whether
a profile or system component meets its specification.

An eval bundle produces a compliance report with:
  - Pass/fail per check
  - Aggregate score
  - Findings with severity
  - Recommendations
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Any, Optional
from datetime import datetime, timezone
from enum import Enum
import uuid


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _id() -> str:
    return str(uuid.uuid4())[:8]


# ── Check result ──────────────────────────────────────────────────────────────
class FindingSeverity(Enum):
    INFO    = "info"
    LOW     = "low"
    MEDIUM  = "medium"
    HIGH    = "high"
    CRITICAL= "critical"


@dataclass
class Finding:
    check_id:  str
    passed:    bool
    severity:  FindingSeverity = FindingSeverity.INFO
    message:   str = ""
    value:     Any = None
    expected:  Any = None
    recommendation: str = ""


@dataclass
class EvalReport:
    """
    The output of running an eval bundle against a profile or state.
    This is the primary output of Reliability OS.
    """
    report_id:   str  = field(default_factory=_id)
    bundle_id:   str  = ""
    profile_id:  str  = ""
    ts:          str  = field(default_factory=_now)
    score:       float = 0.0     # 0.0 - 1.0
    passed:      bool  = False
    findings:    list[Finding] = field(default_factory=list)
    summary:     str   = ""
    recommended_actions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "report_id":  self.report_id,
            "bundle_id":  self.bundle_id,
            "profile_id": self.profile_id,
            "ts":         self.ts,
            "score":      round(self.score, 3),
            "passed":     self.passed,
            "n_findings": len(self.findings),
            "n_critical": sum(1 for f in self.findings
                              if f.severity == FindingSeverity.CRITICAL and not f.passed),
            "summary":    self.summary,
            "findings":   [
                {"check": f.check_id, "passed": f.passed,
                 "severity": f.severity.value, "message": f.message}
                for f in self.findings
            ],
            "recommended_actions": self.recommended_actions,
        }


# ── Eval check type ───────────────────────────────────────────────────────────
CheckFn = Callable[["RuntimeState", "Profile"], Finding]


@dataclass
class EvalCheck:
    id:       str
    name:     str
    fn:       CheckFn
    severity: FindingSeverity = FindingSeverity.MEDIUM
    weight:   float = 1.0


# ── Eval bundle ───────────────────────────────────────────────────────────────
@dataclass
class EvalBundle:
    id:      str
    name:    str
    description: str = ""
    checks:  list[EvalCheck] = field(default_factory=list)
    pass_threshold: float = 0.8   # score >= threshold to pass

    def add_check(self, check: EvalCheck) -> None:
        self.checks.append(check)


# ── Eval runner ───────────────────────────────────────────────────────────────
class EvalRunner:
    """Executes eval bundles and produces compliance reports."""

    def __init__(self):
        self._bundles: dict[str, EvalBundle] = {}
        self._register_defaults()

    def register(self, bundle: EvalBundle) -> None:
        self._bundles[bundle.id] = bundle

    def get(self, bundle_id: str) -> Optional[EvalBundle]:
        return self._bundles.get(bundle_id)

    def run(
        self,
        bundle_id:  str,
        state:      "RuntimeState",
        profile_id: str = "",
    ) -> EvalReport:
        bundle = self._bundles.get(bundle_id)
        if not bundle:
            return EvalReport(
                bundle_id  = bundle_id,
                profile_id = profile_id,
                passed     = False,
                summary    = f"Bundle '{bundle_id}' not found",
            )

        profile = state.profiles.get(profile_id) if profile_id else None
        findings = []
        total_weight = 0.0
        weighted_pass = 0.0

        for check in bundle.checks:
            try:
                finding = check.fn(state, profile)
                finding.check_id = check.id
            except Exception as e:
                finding = Finding(
                    check_id  = check.id,
                    passed    = False,
                    severity  = FindingSeverity.HIGH,
                    message   = f"Check raised exception: {e}",
                )
            findings.append(finding)
            total_weight  += check.weight
            if finding.passed:
                weighted_pass += check.weight

        score  = (weighted_pass / total_weight) if total_weight > 0 else 0.0
        passed = score >= bundle.pass_threshold

        critical_fails = [f for f in findings
                          if not f.passed and f.severity == FindingSeverity.CRITICAL]
        if critical_fails:
            passed = False

        # Build recommendations
        recs = []
        for f in findings:
            if not f.passed and f.recommendation:
                recs.append(f.recommendation)

        n_pass = sum(1 for f in findings if f.passed)
        summary = (f"{n_pass}/{len(findings)} checks passed "
                   f"(score={score:.0%})"
                   + (f" — {len(critical_fails)} critical failures" if critical_fails else ""))

        return EvalReport(
            bundle_id    = bundle_id,
            profile_id   = profile_id,
            score        = score,
            passed       = passed,
            findings     = findings,
            summary      = summary,
            recommended_actions = recs,
        )

    def run_all_for_profile(
        self,
        state: "RuntimeState",
        profile_id: str,
    ) -> list[EvalReport]:
        profile = state.profiles.get(profile_id)
        if not profile:
            return []
        reports = []
        for eval_spec in profile.evals:
            report = self.run(eval_spec.bundle_id, state, profile_id)
            reports.append(report)
        return reports

    def _register_defaults(self) -> None:
        """Register the built-in eval bundles."""

        # ── Bundle: Profile Integrity ─────────────────────────────────────────
        integrity = EvalBundle(
            id   = "core.integrity",
            name = "Profile Integrity",
            description = "Checks that a profile is well-formed and self-consistent",
        )

        def check_has_metrics(state, profile) -> Finding:
            if not profile:
                return Finding("has_metrics", False, FindingSeverity.HIGH,
                               "No profile provided")
            return Finding(
                "has_metrics",
                len(profile.metrics) > 0,
                FindingSeverity.MEDIUM,
                "Profile has at least one metric" if profile.metrics
                else "Profile has no metrics defined",
                recommendation="Add at least one metric to the profile",
            )

        def check_has_version(state, profile) -> Finding:
            if not profile:
                return Finding("has_version", False, FindingSeverity.LOW, "No profile")
            valid = bool(profile.version) and profile.version != "0.0.0"
            return Finding(
                "has_version", valid, FindingSeverity.LOW,
                f"Version: {profile.version}",
                recommendation="Set a meaningful semantic version",
            )

        def check_metric_thresholds(state, profile) -> Finding:
            if not profile:
                return Finding("metric_thresholds", True, FindingSeverity.LOW)
            unthresholded = [m.name for m in profile.metrics if m.threshold is None]
            return Finding(
                "metric_thresholds",
                len(unthresholded) == 0,
                FindingSeverity.MEDIUM,
                (f"All metrics have thresholds" if not unthresholded
                 else f"Missing thresholds: {unthresholded}"),
                recommendation="Set alert thresholds for all metrics",
            )

        integrity.add_check(EvalCheck("has_metrics",    "Has Metrics",    check_has_metrics,    FindingSeverity.MEDIUM))
        integrity.add_check(EvalCheck("has_version",    "Has Version",    check_has_version,    FindingSeverity.LOW))
        integrity.add_check(EvalCheck("metric_thresholds", "Metric Thresholds", check_metric_thresholds, FindingSeverity.MEDIUM))
        self.register(integrity)

        # ── Bundle: System Health ─────────────────────────────────────────────
        health = EvalBundle(
            id   = "core.health",
            name = "System Health",
            description = "Checks the overall health of the runtime",
            pass_threshold = 0.7,
        )

        def check_system_running(state, profile) -> Finding:
            return Finding(
                "system_running",
                state.status == "running",
                FindingSeverity.CRITICAL,
                f"System status: {state.status}",
                recommendation="Ensure system is in 'running' state",
            )

        def check_invariants_healthy(state, profile) -> Finding:
            result = state.invariants.check_all(state)
            return Finding(
                "invariants_healthy",
                bool(result),
                FindingSeverity.HIGH,
                result.summary(),
                recommendation="Resolve invariant violations",
            )

        def check_log_integrity(state, profile) -> Finding:
            ok = state.actions_log.verify()
            return Finding(
                "log_integrity", ok,
                FindingSeverity.CRITICAL,
                "Continuity log integrity OK" if ok else "Log tamper detected!",
                recommendation="Investigate log tampering",
            )

        health.add_check(EvalCheck("system_running",      "System Running",       check_system_running,      FindingSeverity.CRITICAL))
        health.add_check(EvalCheck("invariants_healthy",  "Invariants Healthy",   check_invariants_healthy,  FindingSeverity.HIGH))
        health.add_check(EvalCheck("log_integrity",       "Log Integrity",        check_log_integrity,       FindingSeverity.CRITICAL))
        self.register(health)


# ── Eval history ──────────────────────────────────────────────────────────────
class EvalHistory:
    """Stores all eval reports, indexed by profile and bundle."""

    def __init__(self):
        self._reports: list[EvalReport] = []
        self._tampered: bool = False

    def append(self, report: EvalReport) -> None:
        self._reports.append(report)

    def for_profile(self, profile_id: str) -> list[EvalReport]:
        return [r for r in self._reports if r.profile_id == profile_id]

    def for_bundle(self, bundle_id: str) -> list[EvalReport]:
        return [r for r in self._reports if r.bundle_id == bundle_id]

    def latest(self, n: int = 10) -> list[EvalReport]:
        return self._reports[-n:]

    def trend(self, bundle_id: str, profile_id: str) -> list[float]:
        """Score trend over time for a bundle/profile pair."""
        reports = [r for r in self._reports
                   if r.bundle_id == bundle_id and r.profile_id == profile_id]
        return [r.score for r in reports[-20:]]

    def __len__(self) -> int:
        return len(self._reports)
