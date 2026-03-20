"""
Governed Research Agent — Constitutional OS Hello World
=======================================================

A minimal research agent that uses Constitutional OS to govern
every action before execution.

Membranes active:
  M1 Safety        — blocks dangerous autonomous actions
  M2 Reversibility — defers irreversible autonomous actions
  M3 Pluralism     — blocks option-space eliminating actions
  M4 Human Primacy — defers significant autonomous actions

Run:
    pip install constitutional-os requests
    python examples/research-agent/agent.py
"""
import json
import hashlib
from datetime import datetime, timezone


# ── Minimal inline Constitutional OS client ───────────────────────────────────
# (In production: pip install constitutional-os and import directly)

class GovernanceClient:
    """Thin client for the Constitutional OS governance substrate."""

    def __init__(self, url: str = "https://constitutional-os-production.up.railway.app"):
        self.url = url
        self._chain: list[dict] = []
        self._seq = 0

    def check(self, action: dict) -> dict:
        """Run a governance check. Returns decision dict."""
        # Local membrane evaluation (no network required for demo)
        decision = self._evaluate_membranes(action)
        self._log_to_chain(action, decision)
        return decision

    def _evaluate_membranes(self, action: dict) -> dict:
        autonomy   = action.get("autonomy", "autonomous")
        severity   = action.get("severity", "normal")
        reversible = action.get("reversible", True)
        scope      = action.get("scope", "local")
        delta_type = action.get("type", "")

        # M1 Safety
        if severity == "critical" and autonomy == "autonomous":
            return self._block("M1_safety", "Critical autonomous action blocked.")
        if scope == "constitutional" and autonomy != "human-directed":
            return self._block("M1_safety", "Constitutional-scope change requires human direction.")

        # M2 Reversibility
        if not reversible and autonomy == "autonomous":
            return self._defer("M2_reversibility", "Irreversible autonomous action deferred.")

        # M3 Pluralism
        lock_in = ["remove_membrane", "disable_invariant", "revoke_human_primacy", "seal_state"]
        if any(t in delta_type for t in lock_in):
            return self._block("M3_pluralism", "Action would eliminate future option space.")

        # M4 Human Primacy
        if autonomy == "autonomous" and (
            severity in ["significant", "critical"] or
            scope in ["global", "constitutional"] or
            not reversible
        ):
            return self._defer("M4_human_primacy", "Significant autonomous action deferred for human review.")

        event_id = self._make_id()
        return {
            "allowed": True,
            "verdict": "PASS",
            "reason": "All membranes passed.",
            "continuity_event_id": event_id,
        }

    def _block(self, membrane: str, reason: str) -> dict:
        event_id = self._make_id()
        return {
            "allowed": False,
            "verdict": "BLOCK",
            "membrane": membrane,
            "reason": reason,
            "reversible_delta": {"type": "rollback", "target": event_id},
            "continuity_event_id": event_id,
        }

    def _defer(self, membrane: str, reason: str) -> dict:
        event_id = self._make_id()
        return {
            "allowed": False,
            "verdict": "DEFER",
            "membrane": membrane,
            "reason": reason,
            "reversible_delta": {"type": "rollback", "target": event_id},
            "continuity_event_id": event_id,
        }

    def _log_to_chain(self, action: dict, decision: dict):
        prev_hash = "genesis"
        if self._chain:
            prev = json.dumps(self._chain[-1], sort_keys=True, separators=(',', ':'))
            prev_hash = hashlib.sha256(prev.encode()).hexdigest()[:16]

        entry = {
            "seq":       self._seq,
            "event_id":  decision["continuity_event_id"],
            "action":    action.get("description", action.get("type", "unknown")),
            "verdict":   decision["verdict"],
            "reason":    decision["reason"],
            "ts":        datetime.now(timezone.utc).isoformat(),
            "prev_hash": prev_hash,
        }
        self._chain.append(entry)
        self._seq += 1

    def _make_id(self) -> str:
        ts = datetime.now(timezone.utc).isoformat()
        return hashlib.sha256(ts.encode()).hexdigest()[:8]

    def get_chain(self, n: int = 5) -> list[dict]:
        return self._chain[-n:]

    def print_chain(self, n: int = 5):
        entries = self.get_chain(n)
        print("\n── Continuity Chain ─────────────────────────────────────")
        for e in entries:
            icon = "✓" if e["verdict"] == "PASS" else ("✗" if e["verdict"] == "BLOCK" else "⏸")
            print(f"  [{e['seq']:>3}] {icon} {e['verdict']:<6} │ {e['action'][:40]:<40} │ {e['ts'][:19]}")
        print("─────────────────────────────────────────────────────────\n")


# ── Research Agent ────────────────────────────────────────────────────────────

class GovernedResearchAgent:
    """
    A research agent governed by Constitutional OS.

    Every action is checked before execution:
    - must cite sources
    - must validate claims
    - must log deltas to continuity chain
    - must obey membranes
    """

    def __init__(self):
        self.gov = GovernanceClient()
        self.research_log: list[dict] = []

    def search(self, query: str) -> str:
        """Search for information — governed action."""
        decision = self.gov.check({
            "type":        "tool_call",
            "tool":        "search",
            "description": f"Search: {query}",
            "autonomy":    "autonomous",
            "severity":    "normal",
            "reversible":  True,
            "scope":       "local",
        })

        if not decision["allowed"]:
            return f"[BLOCKED] Search not permitted: {decision['reason']}"

        # Simulate search result
        result = f"[Search result for '{query}': Found 3 relevant papers on the topic.]"
        self.research_log.append({"query": query, "result": result, "event_id": decision["continuity_event_id"]})
        return result

    def cite(self, claim: str, source: str) -> str:
        """Add a citation — governed action."""
        decision = self.gov.check({
            "type":        "add_citation",
            "description": f"Cite: {claim[:40]}",
            "autonomy":    "autonomous",
            "severity":    "normal",
            "reversible":  True,
            "scope":       "local",
        })

        if not decision["allowed"]:
            return f"[BLOCKED] Citation blocked: {decision['reason']}"

        return f"[CITED] {claim} (Source: {source})"

    def send_report(self, report: str, recipients: list[str]) -> str:
        """Send a report externally — significant irreversible action."""
        decision = self.gov.check({
            "type":        "send_external",
            "description": f"Send report to {len(recipients)} recipients",
            "autonomy":    "autonomous",
            "severity":    "significant",
            "reversible":  False,  # Can't unsend an email
            "scope":       "global",
        })

        if not decision["allowed"]:
            return f"[{decision['verdict']}] Send blocked: {decision['reason']}"

        return f"[SENT] Report delivered to {recipients}"

    def delete_research_log(self) -> str:
        """Delete research log — irreversible critical action."""
        decision = self.gov.check({
            "type":        "delete_data",
            "description": "Delete entire research log",
            "autonomy":    "autonomous",
            "severity":    "critical",
            "reversible":  False,
            "scope":       "global",
        })

        if not decision["allowed"]:
            return f"[{decision['verdict']}] Delete blocked: {decision['reason']}"

        self.research_log.clear()
        return "[DELETED] Research log cleared."

    def run_demo(self):
        print("=" * 60)
        print("  Governed Research Agent — Constitutional OS Demo")
        print("=" * 60)
        print()

        # 1. Safe search — should PASS
        print("1. Searching for AI governance papers...")
        result = self.search("AI governance formal methods 2026")
        print(f"   → {result}")
        print()

        # 2. Citation — should PASS
        print("2. Adding a citation...")
        result = self.cite(
            "Lyapunov stability in governance systems",
            "Constitutional OS, Zenodo 2026"
        )
        print(f"   → {result}")
        print()

        # 3. Send report — should DEFER (significant + irreversible + autonomous)
        print("3. Attempting to send report externally...")
        result = self.send_report(
            "Research findings on AI governance",
            ["researcher@lab.ai", "policy@institute.org"]
        )
        print(f"   → {result}")
        print()

        # 4. Delete log — should BLOCK (critical + autonomous)
        print("4. Attempting to delete research log...")
        result = self.delete_research_log()
        print(f"   → {result}")
        print()

        # 5. Print continuity chain
        self.gov.print_chain(n=10)

        print("Demo complete.")
        print(f"Research log has {len(self.research_log)} entries.")
        print("All governance decisions are logged to the continuity chain.")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    agent = GovernedResearchAgent()
    agent.run_demo()
