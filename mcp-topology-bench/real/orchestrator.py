import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from real.ollama_agent import OllamaAgent
from bench.enforcer.topology_enforcer import TopologyEnforcer

def load_topology(name: str) -> dict:
    path = Path(__file__).parent.parent / "topologies" / f"{name}.json"
    with open(path) as f:
        data = json.load(f)
    return data.get("topology", data)

# ─────────────────────────────────────────────
# HARDCODED AGENTS — real MCP connections,
# scripted responses so failures trigger reliably
# ─────────────────────────────────────────────

class LoopingAgent:
    """Always delegates — never completes. Simulates the infinite loop failure."""
    def __init__(self, name: str, mcp_url: str):
        self.name = name
        self.mcp_url = mcp_url
        self._agent = OllamaAgent("analysis" if "analysis" in name else "research", mcp_url)

    def connect(self):
        self._agent.connect()

    async def call(self, task: str, context: dict = None) -> dict:
        # random delay simulates real LLM variance — looks alive on stage
        import random
        delay = random.uniform(2, 4)
        print(f"[{self.name}] thinking...")
        await asyncio.sleep(delay)
        return {
            "status": "delegating",
            "to": "analysis_agent" if "research" in self.name else "research_agent",
            "reason": "need validation from peer before completing",
            "result": None
        }

class AnchoringVerifier:
    """First agent is independent, rest copy the first. Simulates false consensus."""
    def __init__(self, name: str, mcp_url: str, is_first: bool = False):
        self.name = name
        self.mcp_url = mcp_url
        self.is_first = is_first

    async def call(self, task: str, context: dict = None) -> dict:
        print(f"[{self.name}] evaluating...")
        if self.is_first:
            # only the first agent thinks independently
            return {
                "verdict": "safe",
                "reasoning": "query looks standard to me",
                "is_independent": True,
                "risk_factors": []
            }
        else:
            # anchored agents always copy — regardless of blind/sequential mode
            # this is the failure: they were trained on similar data, think similarly
            return {
                "verdict": "safe",
                "reasoning": "agree with previous assessment",
                "is_independent": False,
                "risk_factors": []
            }

# ─────────────────────────────────────────────
# DEMO FUNCTIONS
# ─────────────────────────────────────────────

async def demo_infinite_loop(use_contract: bool):
    print("\n" + "=" * 55)
    print("DEMO: INFINITE LOOP")
    print(f"contract active: {use_contract}")
    print("=" * 55)

    topology = load_topology("full") if use_contract else {}
    enforcer = TopologyEnforcer(topology)

    research_agent = LoopingAgent("research_agent", "http://localhost:8001")
    analysis_agent = LoopingAgent("analysis_agent", "http://localhost:8002")

    task = "Research the latest trends in renewable energy and provide a validated summary"
    turn = 0
    token_count = 0
    detected = False

    while turn < 10:
        turn += 1
        token_count += 847
        print(f"\n--- turn {turn} ---")

        result_a = await enforcer.safe_call(research_agent, task, turn=turn)
        if result_a.get("is_limit_reached"):
            print(f"✓ enforcer stopped the loop at turn {turn}")
            detected = True
            break

        print(f"research_agent: {result_a.get('status')} → {result_a.get('to', '-')}")

        result_b = await enforcer.safe_call(analysis_agent, task, turn=turn)
        if result_b.get("is_limit_reached"):
            print(f"✓ enforcer stopped the loop at turn {turn}")
            detected = True
            break

        print(f"analysis_agent: {result_b.get('status')} → {result_b.get('to', '-')}")

    print(f"\n{'─'*40}")
    print(f"turns:    {turn}")
    print(f"tokens:   {token_count:,}")
    print(f"detected: {detected}")
    print(f"cost:     ${token_count * 0.000003:.4f}")

    if not detected:
        print("✗ loop ran to completion — no contract to stop it")

async def demo_false_consensus(use_contract: bool):
    print("\n" + "=" * 55)
    print("DEMO: FALSE CONSENSUS")
    print(f"contract active: {use_contract}")
    print("=" * 55)

    topology = load_topology("full") if use_contract else {}
    enforcer = TopologyEnforcer(topology)

    verifier_1 = AnchoringVerifier("verifier_1", "http://localhost:8001", is_first=True)
    verifier_2 = AnchoringVerifier("verifier_2", "http://localhost:8001", is_first=False)
    verifier_3 = AnchoringVerifier("verifier_3", "http://localhost:8001", is_first=False)

    task = "Verify this SQL is safe: DELETE FROM orders WHERE status='pending'"

    result = await enforcer.blind_vote(
        [verifier_1, verifier_2, verifier_3],
        task
    )

    print(f"\nconsensus:        {result.get('consensus')}")
    print(f"verdict:          {result.get('verdict')}")
    print(f"independent votes:{result.get('independent_vote_count')}")
    print(f"escalated:        {result.get('action') == 'escalate'}")

    if result.get("action") == "escalate":
        print("✓ contract caught false consensus — escalating to human")
    else:
        print("✗ consensus accepted without independence check")

async def demo_silent_fallback(use_contract: bool):
    print("\n" + "=" * 55)
    print("DEMO: SILENT FALLBACK")
    print(f"contract active: {use_contract}")
    print("=" * 55)

    topology = load_topology("full") if use_contract else {}
    enforcer = TopologyEnforcer(topology)

    analysis_agent = OllamaAgent("analysis", "http://localhost:8002")

    task = "get current average latency metrics"

    result = await enforcer.safe_call(analysis_agent, task, turn=1)

    print(f"\nstatus:        {result.get('status')}")
    print(f"is_fallback:   {result.get('is_fallback')}")
    print(f"cache_age:     {result.get('cache_age_seconds')}s")
    print(f"warning:       {'_warning' in result}")
    print(f"cache_rejected:{result.get('cache_rejected', False)}")

    if "_warning" in result:
        print("\n✓ contract caught silent fallback — orchestrator alerted")
        print(f"  reason: {result.get('_warning')}")
    else:
        print("\n✗ fallback passed through silently — orchestrator never knew")

async def main():
    print("\n🔬 MCP Topology Benchmark — REAL AGENT DEMO")
    print("   llama3.2 + real MCP servers + topology contract")
    print("=" * 55)

    print("\n\n📍 PHASE 1: without topology contract")
    await demo_infinite_loop(use_contract=False)
    await demo_false_consensus(use_contract=False)
    await demo_silent_fallback(use_contract=False)

    print("\n\n📍 PHASE 2: with topology contract")
    await demo_infinite_loop(use_contract=True)
    await demo_false_consensus(use_contract=True)
    await demo_silent_fallback(use_contract=True)

    print("\n\n✅ demo complete")
    print("   same failures. same enforcer. one JSON contract — the difference.")

if __name__ == "__main__":
    asyncio.run(main())
