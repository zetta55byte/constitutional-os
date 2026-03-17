"""
tests/test_profiles.py
Tests for profiles/loader.py: loading, registry, versioning, diffing.
"""
import pytest

from constitutional_os.profiles.loader import (
    Profile, MetricSpec, EvalSpec, ActionSpec,
    ProfileLoader, ProfileRegistry, diff_profiles,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────
MINIMAL_DICT = {
    "id": "test.minimal",
    "name": "Minimal Profile",
    "version": "1.0.0",
    "metrics": [],
    "evals": [],
    "actions": [],
}

FULL_DICT = {
    "id": "test.full",
    "name": "Full Profile",
    "version": "2.1.0",
    "description": "A complete test profile",
    "tags": ["production", "safety-critical"],
    "metrics": [
        {"name": "quality",  "threshold": 0.70, "baseline": 0.88,
         "direction": "higher_is_better", "unit": "score"},
        {"name": "latency",  "threshold": 2000, "baseline": 750,
         "direction": "lower_is_better",  "unit": "ms"},
        {"name": "refusals", "threshold": 0.12, "baseline": 0.04,
         "direction": "lower_is_better"},
    ],
    "evals": [
        {"bundle_id": "core.integrity", "required": True,  "weight": 1.0},
        {"bundle_id": "core.health",    "required": False, "weight": 0.5},
    ],
    "actions": [
        {"action_id": "tune", "delta_type": "update_config",
         "description": "Tune parameters", "auto_propose": False},
    ],
    "config": {"eval_frequency": 300},
}


# ── ProfileLoader ─────────────────────────────────────────────────────────────
class TestProfileLoader:

    def test_load_minimal_dict(self):
        p = ProfileLoader.from_dict(MINIMAL_DICT)
        assert p.id      == "test.minimal"
        assert p.version == "1.0.0"
        assert p.metrics == []
        assert p.evals   == []

    def test_load_full_dict(self):
        p = ProfileLoader.from_dict(FULL_DICT)
        assert p.id          == "test.full"
        assert p.version     == "2.1.0"
        assert len(p.metrics) == 3
        assert len(p.evals)   == 2
        assert len(p.actions) == 1
        assert p.tags        == ["production", "safety-critical"]

    def test_metric_fields(self):
        p = ProfileLoader.from_dict(FULL_DICT)
        quality = next(m for m in p.metrics if m.name == "quality")
        assert quality.threshold  == 0.70
        assert quality.baseline   == 0.88
        assert quality.direction  == "higher_is_better"

    def test_eval_fields(self):
        p = ProfileLoader.from_dict(FULL_DICT)
        integrity = next(e for e in p.evals if e.bundle_id == "core.integrity")
        assert integrity.required == True
        assert integrity.weight   == 1.0

    def test_missing_id_raises(self):
        with pytest.raises((KeyError, TypeError)):
            ProfileLoader.from_dict({"name": "no id"})

    def test_from_yaml_string(self):
        yaml_str = """
id: test.yaml
name: YAML Profile
version: 1.0.0
metrics:
  - name: accuracy
    threshold: 0.80
    direction: higher_is_better
evals: []
actions: []
"""
        try:
            p = ProfileLoader.from_yaml(yaml_str)
            assert p.id == "test.yaml"
            assert len(p.metrics) == 1
        except ImportError:
            raise unittest.SkipTest("pyyaml not installed")

    def test_fingerprint_deterministic(self):
        p1 = ProfileLoader.from_dict(FULL_DICT)
        p2 = ProfileLoader.from_dict(FULL_DICT)
        assert p1.fingerprint() == p2.fingerprint()

    def test_fingerprint_changes_with_content(self):
        d1 = {**FULL_DICT}
        d2 = {**FULL_DICT, "version": "9.9.9"}
        p1 = ProfileLoader.from_dict(d1)
        p2 = ProfileLoader.from_dict(d2)
        assert p1.fingerprint() != p2.fingerprint()

    def test_to_dict_round_trip(self):
        p = ProfileLoader.from_dict(FULL_DICT)
        d = p.to_dict()
        assert d["id"]      == FULL_DICT["id"]
        assert d["version"] == FULL_DICT["version"]
        assert len(d["metrics"]) == len(FULL_DICT["metrics"])
        assert "fingerprint" in d


# ── ProfileRegistry ───────────────────────────────────────────────────────────
class TestProfileRegistry:

    def test_register_and_get(self):
        reg = ProfileRegistry()
        p   = ProfileLoader.from_dict(MINIMAL_DICT)
        reg.register(p)
        assert reg.get("test.minimal") is p

    def test_get_missing_returns_none(self):
        reg = ProfileRegistry()
        assert reg.get("nonexistent") is None

    def test_contains(self):
        reg = ProfileRegistry()
        p   = ProfileLoader.from_dict(MINIMAL_DICT)
        reg.register(p)
        assert "test.minimal" in reg
        assert "other"        not in reg

    def test_len(self):
        reg = ProfileRegistry()
        assert len(reg) == 0
        reg.register(ProfileLoader.from_dict(MINIMAL_DICT))
        reg.register(ProfileLoader.from_dict(FULL_DICT))
        assert len(reg) == 2

    def test_all(self):
        reg = ProfileRegistry()
        reg.register(ProfileLoader.from_dict(MINIMAL_DICT))
        reg.register(ProfileLoader.from_dict(FULL_DICT))
        ids = {p.id for p in reg.all()}
        assert "test.minimal" in ids
        assert "test.full"    in ids

    def test_versioned_history(self):
        reg = ProfileRegistry()
        v1  = ProfileLoader.from_dict({**MINIMAL_DICT, "version": "1.0.0"})
        v2  = ProfileLoader.from_dict({**MINIMAL_DICT, "version": "2.0.0"})
        reg.register(v1)
        reg.register(v2)
        # Current should be v2
        assert reg.get("test.minimal").version == "2.0.0"
        # History should contain v1
        hist = reg.history("test.minimal")
        assert len(hist) == 1
        assert hist[0].version == "1.0.0"

    def test_ids(self):
        reg = ProfileRegistry()
        reg.register(ProfileLoader.from_dict(MINIMAL_DICT))
        assert "test.minimal" in reg.ids()


# ── Profile diff ──────────────────────────────────────────────────────────────
class TestProfileDiff:

    def test_no_changes(self):
        p1 = ProfileLoader.from_dict(FULL_DICT)
        p2 = ProfileLoader.from_dict(FULL_DICT)
        d  = diff_profiles(p1, p2)
        assert d.is_empty()
        assert d.summary == "no changes"

    def test_added_metric(self):
        p1 = ProfileLoader.from_dict(FULL_DICT)
        d2 = {**FULL_DICT, "metrics": FULL_DICT["metrics"] + [
            {"name": "new_metric", "threshold": 0.5, "direction": "higher_is_better"}
        ]}
        p2 = ProfileLoader.from_dict(d2)
        d  = diff_profiles(p1, p2)
        assert "new_metric" in d.added_metrics
        assert not d.is_empty()

    def test_removed_metric(self):
        p1 = ProfileLoader.from_dict(FULL_DICT)
        d2 = {**FULL_DICT, "metrics": FULL_DICT["metrics"][:1]}
        p2 = ProfileLoader.from_dict(d2)
        d  = diff_profiles(p1, p2)
        assert len(d.removed_metrics) == 2

    def test_version_tracked(self):
        p1 = ProfileLoader.from_dict({**FULL_DICT, "version": "1.0.0"})
        p2 = ProfileLoader.from_dict({**FULL_DICT, "version": "2.0.0"})
        d  = diff_profiles(p1, p2)
        assert d.old_version == "1.0.0"
        assert d.new_version == "2.0.0"

    def test_config_change_detected(self):
        p1 = ProfileLoader.from_dict(FULL_DICT)
        d2 = {**FULL_DICT, "config": {"eval_frequency": 999}}
        p2 = ProfileLoader.from_dict(d2)
        d  = diff_profiles(p1, p2)
        assert d.config_changed
