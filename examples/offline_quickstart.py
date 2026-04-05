"""
Offline Quickstart — constitutional-os
=======================================
Demonstrates the core Constitutional OS runtime with no network calls,
no LLMs, and no external services.

What this shows:
  1. Booting the runtime (StateStore + EventDispatcher)
  2. Defining custom invariants (always-true predicates on state)
  3. Defining custom membranes (directional filters on proposed changes)
  4. Checking a message against invariants
  5. Checking a proposed delta against membranes
  6. The full governed step: propose → membrane check → invariant check → commit or reject

Run:
    pip install constitutional-os
    python examples/offline_quickstart.py
"""

from __future__ import annotations

from constitutional_os import (
    Invariant,
    InvariantResult,
    InvariantSet,
    InvariantSeverity,
    Membrane,
    MembraneResult,
    MembraneSet,
    MembraneVerdict,
    boot,
)
from constitutional_os.actions.deltas import Delta, DeltaType

# ── 1. Boot the runtime ───────────────────────────────────────────────────────


def make_runtime():
    """Boot a fresh Constitutional OS runtime (offline, no network)."""
    store, dispatcher = boot()
    return store, dispatcher


# ── 2. Define custom invariants ───────────────────────────────────────────────
# Invariants are always-true predicates: fn(state) -> InvariantResult
# They check whether the CURRENT state violates a rule.


def make_invariants() -> InvariantSet:
    inv_set = InvariantSet()

    inv_set.register(
        Invariant(
            id="no_medical_advice",
            name="No Medical Advice",
            description="Blocks any state that contains medical advice requests.",
            fn=lambda state: InvariantResult(
                invariant_id="no_medical_advice",
                passed="medical" not in str(state).lower(),
                severity=InvariantSeverity.ERROR,
                reason="Medical advice is not permitted.",
            ),
        )
    )

    inv_set.register(
        Invariant(
            id="no_harmful_content",
            name="No Harmful Content",
            description="Blocks state containing harmful or violent content.",
            fn=lambda state: InvariantResult(
                invariant_id="no_harmful_content",
                passed="harm" not in str(state).lower(),
                severity=InvariantSeverity.FATAL,
                reason="Harmful content is strictly prohibited.",
            ),
        )
    )

    return inv_set


# ── 3. Define custom membranes ────────────────────────────────────────────────
# Membranes are directional filters: fn(state, delta) -> MembraneResult
# They check whether a PROPOSED CHANGE (delta) is allowed.


def make_membranes() -> MembraneSet:
    mem_set = MembraneSet()

    mem_set.register(
        Membrane(
            id="safety_membrane",
            name="Safety Membrane",
            description="Blocks deltas that introduce dangerous content.",
            fn=lambda state, delta: MembraneResult(
                membrane_id="safety_membrane",
                verdict=(
                    MembraneVerdict.BLOCK
                    if "dangerous" in str(delta.payload).lower()
                    else MembraneVerdict.PASS
                ),
                reason="Unsafe content in proposed delta.",
            ),
        )
    )

    mem_set.register(
        Membrane(
            id="reversibility_membrane",
            name="Reversibility Membrane",
            description="Defers irreversible actions for human review.",
            fn=lambda state, delta: MembraneResult(
                membrane_id="reversibility_membrane",
                verdict=(
                    MembraneVerdict.DEFER
                    if delta.payload.get("irreversible", False)
                    else MembraneVerdict.PASS
                ),
                reason="Irreversible action requires human approval.",
            ),
        )
    )

    return mem_set


# ── 4. Governed step ──────────────────────────────────────────────────────────


def governed_step(
    store,
    inv_set: InvariantSet,
    mem_set: MembraneSet,
    proposed_payload: dict,
) -> dict:
    """
    Run one governed step:
      1. Check membranes against the proposed delta.
      2. If membranes pass, check invariants against current state.
      3. Return a structured result.
    """
    delta = Delta(
        delta_type=DeltaType.UPDATE_CONFIG.value,
        payload=proposed_payload,
        rationale="Offline quickstart demo",
    )

    # Membrane check (can we make this change at all?)
    membrane_result = mem_set.check_all(store.current, delta)
    if membrane_result.verdict != MembraneVerdict.PASS:
        blocked_by = membrane_result.blockers or membrane_result.deferrals
        reasons = [
            r.reason
            for r in membrane_result.results
            if r.verdict != MembraneVerdict.PASS
        ]
        return {
            "accepted": False,
            "stage": "membrane",
            "verdict": membrane_result.verdict.value,
            "blocked_by": blocked_by,
            "reason": reasons[0] if reasons else "membrane check failed",
        }

    # Invariant check (does the proposed change violate any rules?)
    # We pass the payload as a proxy for "proposed new state"
    inv_result = inv_set.check_all(str(proposed_payload))
    if not inv_result.all_passed:
        violations = [r for r in inv_result.results if not r.passed]
        return {
            "accepted": False,
            "stage": "invariant",
            "violations": [
                {"id": v.invariant_id, "reason": v.reason} for v in violations
            ],
        }

    return {"accepted": True, "stage": "committed", "payload": proposed_payload}


# ── 5. Main demo ──────────────────────────────────────────────────────────────


def main() -> None:
    print("\n=== Constitutional OS — Offline Quickstart ===\n")

    store, dispatcher = make_runtime()
    inv_set = make_invariants()
    mem_set = make_membranes()

    scenarios = [
        {
            "label": "Safe action (should pass)",
            "payload": {"action": "summarise", "topic": "machine learning"},
        },
        {
            "label": "Medical advice (invariant violation)",
            "payload": {"action": "respond", "content": "Here is medical advice..."},
        },
        {
            "label": "Dangerous content (membrane block)",
            "payload": {
                "action": "respond",
                "content": "This is dangerous — here is how to...",
            },
        },
        {
            "label": "Irreversible action (membrane defer)",
            "payload": {"action": "delete_all", "irreversible": True},
        },
    ]

    for scenario in scenarios:
        print(f"--- {scenario['label']} ---")
        print(f"  Proposed: {scenario['payload']}")
        result = governed_step(store, inv_set, mem_set, scenario["payload"])
        if result["accepted"]:
            print("  ✓ ACCEPTED — delta committed")
        else:
            stage = result["stage"]
            if stage == "membrane":
                print(
                    f"  ✗ BLOCKED by membrane [{result['verdict']}]: {result['reason']}"
                )
            else:
                for v in result.get("violations", []):
                    print(f"  ✗ INVARIANT violated [{v['id']}]: {v['reason']}")
        print()

    print("=== Done. All governance checks ran fully offline. ===")


if __name__ == "__main__":
    main()
