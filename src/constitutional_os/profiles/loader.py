"""
profiles/loader.py + profiles/registry.py
Profile DSL, loader, registry, and diff engine.

A Profile is a versioned specification of expected behavior.
It defines: what to measure, what thresholds to enforce,
what eval bundles to run, and what actions are available.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Optional
from datetime import datetime, timezone
import copy
import hashlib
import json


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Profile schema ────────────────────────────────────────────────────────────
@dataclass
class MetricSpec:
    """A single measurable quantity in a profile."""
    name:        str
    description: str        = ""
    unit:        str        = ""
    threshold:   Optional[float] = None   # alert if exceeded
    baseline:    Optional[float] = None   # expected value
    direction:   str        = "lower_is_better"  # lower_is_better | higher_is_better | target


@dataclass
class EvalSpec:
    """Reference to an eval bundle this profile requires."""
    bundle_id:   str
    required:    bool = True
    weight:      float = 1.0


@dataclass
class ActionSpec:
    """An action available for this profile."""
    action_id:   str
    delta_type:  str
    description: str   = ""
    auto_propose: bool = False   # auto-propose when triggered


@dataclass
class Profile:
    """
    A versioned behavioral specification.

    Profiles are the unit of configuration in Reliability OS.
    Each profile describes a surface, agent, or system component.
    """
    id:           str
    name:         str
    version:      str        = "1.0.0"
    description:  str        = ""
    tags:         list       = field(default_factory=list)
    metrics:      list[MetricSpec]  = field(default_factory=list)
    evals:        list[EvalSpec]    = field(default_factory=list)
    actions:      list[ActionSpec]  = field(default_factory=list)
    config:       dict       = field(default_factory=dict)
    created_at:   str        = field(default_factory=_now)
    updated_at:   str        = field(default_factory=_now)
    signature:    str        = ""   # filled by signing module

    def fingerprint(self) -> str:
        """SHA256 of canonical JSON."""
        canonical = json.dumps({
            "id": self.id, "name": self.name, "version": self.version,
            "metrics": [m.__dict__ for m in self.metrics],
            "evals":   [e.__dict__ for e in self.evals],
            "config":  self.config,
        }, sort_keys=True)
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "version": self.version,
            "description": self.description, "tags": self.tags,
            "metrics": [m.__dict__ for m in self.metrics],
            "evals":   [e.__dict__ for e in self.evals],
            "actions": [a.__dict__ for a in self.actions],
            "config":  self.config,
            "fingerprint": self.fingerprint(),
        }


# ── Profile loader ────────────────────────────────────────────────────────────
class ProfileLoader:
    """Load profiles from dicts, YAML strings, or files."""

    @staticmethod
    def from_dict(d: dict) -> Profile:
        metrics = [MetricSpec(**m) for m in d.get("metrics", [])]
        evals   = [EvalSpec(**e)   for e in d.get("evals",   [])]
        actions = [ActionSpec(**a) for a in d.get("actions", [])]
        return Profile(
            id          = d["id"],
            name        = d.get("name", d["id"]),
            version     = d.get("version", "1.0.0"),
            description = d.get("description", ""),
            tags        = d.get("tags", []),
            metrics     = metrics,
            evals       = evals,
            actions     = actions,
            config      = d.get("config", {}),
        )

    @staticmethod
    def from_yaml(text: str) -> Profile:
        try:
            import yaml
            d = yaml.safe_load(text)
        except ImportError:
            import json
            d = json.loads(text)
        return ProfileLoader.from_dict(d)

    @staticmethod
    def from_file(path: str) -> Profile:
        with open(path) as f:
            text = f.read()
        return ProfileLoader.from_yaml(text)


# ── Profile registry ──────────────────────────────────────────────────────────
class ProfileRegistry:
    """
    Registry of all loaded profiles.
    Supports versioned history per profile ID.
    """

    def __init__(self):
        self._current:  dict[str, Profile] = {}
        self._history:  dict[str, list[Profile]] = {}

    def register(self, profile: Profile) -> None:
        pid = profile.id
        if pid in self._current:
            self._history.setdefault(pid, []).append(self._current[pid])
        self._current[pid] = profile

    def get(self, profile_id: str) -> Optional[Profile]:
        return self._current.get(profile_id)

    def all(self) -> list[Profile]:
        return list(self._current.values())

    def history(self, profile_id: str) -> list[Profile]:
        return self._history.get(profile_id, [])

    def ids(self) -> list[str]:
        return list(self._current.keys())

    def __len__(self) -> int:
        return len(self._current)

    def __contains__(self, profile_id: str) -> bool:
        return profile_id in self._current


# ── Profile diff ──────────────────────────────────────────────────────────────
@dataclass
class ProfileDiff:
    profile_id:   str
    old_version:  str
    new_version:  str
    added_metrics:   list[str] = field(default_factory=list)
    removed_metrics: list[str] = field(default_factory=list)
    changed_metrics: list[str] = field(default_factory=list)
    added_evals:     list[str] = field(default_factory=list)
    removed_evals:   list[str] = field(default_factory=list)
    config_changed:  bool      = False
    summary:         str       = ""

    def is_empty(self) -> bool:
        return not any([
            self.added_metrics, self.removed_metrics, self.changed_metrics,
            self.added_evals, self.removed_evals, self.config_changed,
        ])


def diff_profiles(old: Profile, new: Profile) -> ProfileDiff:
    """Compute the diff between two versions of a profile."""
    old_metrics = {m.name: m for m in old.metrics}
    new_metrics = {m.name: m for m in new.metrics}

    added   = [n for n in new_metrics if n not in old_metrics]
    removed = [n for n in old_metrics if n not in new_metrics]
    changed = [
        n for n in old_metrics
        if n in new_metrics and old_metrics[n].__dict__ != new_metrics[n].__dict__
    ]

    old_evals = {e.bundle_id for e in old.evals}
    new_evals = {e.bundle_id for e in new.evals}

    d = ProfileDiff(
        profile_id      = new.id,
        old_version     = old.version,
        new_version     = new.version,
        added_metrics   = added,
        removed_metrics = removed,
        changed_metrics = changed,
        added_evals     = list(new_evals - old_evals),
        removed_evals   = list(old_evals - new_evals),
        config_changed  = old.config != new.config,
    )

    parts = []
    if added:   parts.append(f"+{len(added)} metrics")
    if removed: parts.append(f"-{len(removed)} metrics")
    if changed: parts.append(f"~{len(changed)} metrics changed")
    if d.added_evals:   parts.append(f"+{len(d.added_evals)} evals")
    if d.removed_evals: parts.append(f"-{len(d.removed_evals)} evals")
    if d.config_changed: parts.append("config changed")
    d.summary = ", ".join(parts) if parts else "no changes"

    return d
