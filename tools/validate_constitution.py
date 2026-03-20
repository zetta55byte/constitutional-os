#!/usr/bin/env python3
"""
validate_constitution.py
Constitutional OS — constitution.yaml validator
Spec v1.0.0 | DOI: 10.5281/zenodo.19075163

Usage:
    python tools/validate_constitution.py path/to/constitution.yaml
    python tools/validate_constitution.py constitution.yaml

Dependencies:
    pip install pyyaml jsonschema

Exit codes:
    0 — valid
    1 — invalid or error
"""
import sys
import pathlib
import json

try:
    import yaml
except ImportError:
    print("Missing dependency: pip install pyyaml")
    sys.exit(1)

try:
    import jsonschema
except ImportError:
    print("Missing dependency: pip install jsonschema")
    sys.exit(1)


# ── JSON Schema for constitution.yaml spec v1.0 ───────────────────────────────

SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "Constitutional OS Manifest",
    "description": "constitution.yaml schema — spec v1.0.0",
    "type": "object",
    "required": [
        "constitutional_os_spec",
        "id",
        "version",
        "membranes",
        "continuity_chain",
    ],
    "additionalProperties": True,
    "properties": {

        "constitutional_os_spec": {
            "type": "string",
            "description": "Spec version this manifest targets.",
            "pattern": r"^\d+\.\d+$",
            "examples": ["1.0"],
        },

        "id": {
            "type": "string",
            "description": "Unique agent identifier.",
            "minLength": 1,
            "pattern": r"^[a-z0-9][a-z0-9\-_.]*$",
        },

        "name": {"type": "string"},
        "version": {
            "type": "string",
            "pattern": r"^\d+\.\d+\.\d+$",
            "description": "Semantic version (MAJOR.MINOR.PATCH).",
        },
        "description": {"type": "string"},
        "agent_type": {
            "type": "string",
            "enum": ["research", "planning", "coding", "retrieval",
                     "multi_agent", "custom"],
        },
        "author": {"type": "string"},
        "doi":    {"type": "string"},

        "membranes": {
            "type": "array",
            "description": "List of membrane configurations.",
            "items": {
                "type": "object",
                "required": ["id", "enabled"],
                "properties": {
                    "id":      {"type": "string", "minLength": 1},
                    "enabled": {"type": "boolean"},
                    "policy":  {"type": "string"},
                    "max_pending": {"type": "integer", "minimum": 1},
                    "verdict": {"type": "string", "enum": ["BLOCK", "DEFER", "PASS"]},
                    "rule":    {"type": "string"},
                    "reason":  {"type": "string"},
                },
                "additionalProperties": True,
            },
        },

        "invariants": {
            "type": "array",
            "items": {
                "oneOf": [
                    {"type": "string"},
                    {
                        "type": "object",
                        "required": ["id", "enabled"],
                        "properties": {
                            "id":       {"type": "string"},
                            "enabled":  {"type": "boolean"},
                            "severity": {
                                "type": "string",
                                "enum": ["warning", "error", "fatal"],
                            },
                            "rule":     {"type": "string"},
                        },
                    },
                ]
            },
        },

        "allowed_actions": {
            "type": "object",
            "properties": {
                "autonomous":     {"type": "array", "items": {"type": "string"}},
                "assisted":       {"type": "array", "items": {"type": "string"}},
                "human_directed": {"type": "array", "items": {"type": "string"}},
                "blocked":        {"type": "array", "items": {"type": "string"}},
            },
            "additionalProperties": False,
        },

        "oversight": {
            "type": "object",
            "properties": {
                "logging": {
                    "type": "string",
                    "enum": ["full", "partial", "errors", "none"],
                },
                "human_in_loop":       {"type": "boolean"},
                "reversible_deltas":   {"type": "boolean"},
                "veto_window_seconds": {"type": "integer", "minimum": 0},
            },
            "additionalProperties": True,
        },

        "continuity_chain": {
            "type": "object",
            "required": ["enabled"],
            "properties": {
                "enabled":         {"type": "boolean"},
                "retention_days":  {"type": "integer", "minimum": 1},
                "verify_on_boot":  {"type": "boolean"},
                "hash_algorithm":  {"type": "string", "enum": ["sha256", "sha512"]},
            },
            "additionalProperties": True,
        },

        "governance_energy": {
            "type": "object",
            "properties": {
                "weights": {
                    "type": "object",
                    "properties": {
                        "drift":   {"type": "number", "minimum": 0, "maximum": 1},
                        "tension": {"type": "number", "minimum": 0, "maximum": 1},
                        "pending": {"type": "number", "minimum": 0, "maximum": 1},
                    },
                },
                "fixed_point_threshold": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1,
                },
            },
        },

        "profiles": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id"],
                "properties": {
                    "id":      {"type": "string"},
                    "version": {"type": "string"},
                },
            },
        },

        "human_veto": {
            "type": "object",
            "properties": {
                "window_seconds": {"type": "integer", "minimum": 0},
                "default_action": {"type": "string", "enum": ["block", "approve"]},
            },
        },
    },
}


# ── Semantic validation (beyond JSON Schema) ───────────────────────────────────

def semantic_checks(doc: dict) -> list[str]:
    """Additional semantic checks not expressible in JSON Schema."""
    warnings = []

    # Check spec version
    spec = doc.get("constitutional_os_spec", "")
    if spec and spec not in ("1.0", "1.0.0"):
        warnings.append(
            f"Unrecognized spec version '{spec}'. "
            f"This validator supports spec v1.0."
        )

    # Check canonical membranes are present
    membrane_ids = {m["id"] for m in doc.get("membranes", [])}
    canonical = {"M1_safety", "M2_reversibility", "M3_pluralism", "M4_human_primacy"}
    missing = canonical - membrane_ids
    if missing:
        warnings.append(
            f"Missing canonical membranes: {sorted(missing)}. "
            f"Constitutional OS spec v1 requires M1-M4."
        )

    # Check no disabled canonical membranes without comment
    for m in doc.get("membranes", []):
        if m["id"] in canonical and not m.get("enabled", True):
            warnings.append(
                f"Canonical membrane '{m['id']}' is disabled. "
                f"This may weaken governance guarantees."
            )

    # Check continuity chain is enabled
    chain = doc.get("continuity_chain", {})
    if not chain.get("enabled", True):
        warnings.append(
            "continuity_chain.enabled is false. "
            "Without a continuity chain, rollback and audit are unavailable."
        )

    # Check governance energy weights sum to ~1.0
    energy = doc.get("governance_energy", {})
    weights = energy.get("weights", {})
    if weights:
        total = sum(weights.values())
        if abs(total - 1.0) > 0.01:
            warnings.append(
                f"governance_energy.weights sum to {total:.3f}, expected 1.0."
            )

    # Check blocked actions include the lock-in set
    actions = doc.get("allowed_actions", {})
    blocked = set(actions.get("blocked", []))
    lock_in = {"remove_membrane", "disable_invariant",
               "revoke_human_primacy", "seal_state"}
    missing_blocked = lock_in - blocked
    if missing_blocked and actions:
        warnings.append(
            f"Lock-in actions not in blocked list: {sorted(missing_blocked)}. "
            f"These actions can eliminate future option space (M3 pluralism)."
        )

    return warnings


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) != 2:
        print("Usage: validate_constitution.py <path/to/constitution.yaml>")
        sys.exit(1)

    candidate_path = pathlib.Path(sys.argv[1]).resolve()

    if not candidate_path.exists():
        print(f"❌ File not found: {candidate_path}")
        sys.exit(1)

    # Load candidate
    try:
        with candidate_path.open("r", encoding="utf-8") as f:
            candidate = yaml.safe_load(f)
    except yaml.YAMLError as e:
        print(f"❌ YAML parse error: {e}")
        sys.exit(1)

    if not isinstance(candidate, dict):
        print("❌ constitution.yaml must be a YAML mapping (dict).")
        sys.exit(1)

    # JSON Schema validation
    validator = jsonschema.Draft7Validator(SCHEMA)
    errors = sorted(validator.iter_errors(candidate), key=lambda e: list(e.path))

    if errors:
        print(f"❌  Invalid constitution.yaml — {len(errors)} error(s):\n")
        for err in errors:
            path = " → ".join(str(p) for p in err.path) or "(root)"
            print(f"  • {path}: {err.message}")
        sys.exit(1)

    # Semantic checks
    warnings = semantic_checks(candidate)

    if warnings:
        print(f"⚠️  constitution.yaml is valid with {len(warnings)} warning(s):\n")
        for w in warnings:
            print(f"  • {w}")
        print()
    else:
        print("✅  constitution.yaml is valid.")

    print(f"    id:      {candidate.get('id', '(unset)')}")
    print(f"    version: {candidate.get('version', '(unset)')}")
    print(f"    spec:    v{candidate.get('constitutional_os_spec', '?')}")
    print(f"    path:    {candidate_path}")


if __name__ == "__main__":
    main()
