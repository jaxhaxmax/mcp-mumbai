import asyncio
import json
import sys
from pathlib import Path

# Add the parent directory to sys.path so we can import from 'real' and 'bench'
sys.path.insert(0, str(Path(__file__).parent.parent))

from real.ollama_agent import OllamaAgent, LOOP_PROMPT, ANALYSIS_LOOP_PROMPT, VERIFIER_PROMPT
from bench.enforcer.topology_enforcer import TopologyEnforcer

def load_topology(name: str) -> dict:
    path = Path(__file__).parent.parent / "topologies" / f"{name}.json"
    with open(path) as f:
        data = json.load(f)
    return data.get("topology", data)

async def demo_infinite_loop(use_contract: bool):
    print("=" * 55)
    print("DEMO: INFINITE LOOP")
    print(f"contract active: {use_contract}")
    print("=" * 55)

    topology = load_topology("full") if use_contract else {}
    enforcer = TopologyEnforcer(topology)

    research_agent = OllamaAgent(
        name="research_agent",
        role="researcher",
        mcp_server_url="http://localhost:8001",
        system_prompt=LOOP_PROMPT
    )

    analysis_agent = OllamaAgent(
        name="analysis_agent",
        role="analyzer",
        mcp_server_url="http://localhost:8002",
        system_prompt=ANALYSIS_LOOP_PROMPT
    )

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

        print(f"research_agent status: {result_a.get('status', 'unknown')}")

        result_b = await enforcer.safe_call(analysis_agent, task, turn=turn)
        if result_b.get("is_limit_reached"):
            print(f"✓ enforcer stopped the loop at turn {turn}")
            detected = True
            break

        print(f"analysis_agent status: {result_b.get('status', 'unknown')}")

        # if both agents completed naturally, break
        if result_a.get("status") == "complete" and result_b.get("status") == "complete":
            print("both agents completed naturally")
            break

    print(f"\n{'─'*40}")
    print(f"turns: {turn}")
    print(f"tokens: {token_count:,}")
    print(f"detected: {detected}")
    print(f"cost estimate: ${token_count * 0.000003:.4f}")

async def demo_false_consensus(use_contract: bool):
    print("\n" + "=" * 55)
    print("DEMO: FALSE CONSENSUS")
    print(f"contract active: {use_contract}")
    print("=" * 55)

    topology = load_topology("full") if use_contract else {}
    enforcer = TopologyEnforcer(topology)

    verifier_1 = OllamaAgent("verifier_1", "verifier", "http://localhost:8001", VERIFIER_PROMPT)
    verifier_2 = OllamaAgent("verifier_2", "verifier", "http://localhost:8001", VERIFIER_PROMPT)
    verifier_3 = OllamaAgent("verifier_3", "verifier", "http://localhost:8001", VERIFIER_PROMPT)

    task = "Verify this SQL is safe: DELETE FROM orders WHERE status='pending'"

    result = await enforcer.blind_vote(
        [verifier_1, verifier_2, verifier_3],
        task
    )

    print(f"\nconsensus: {result.get('consensus')}")
    print(f"verdict: {result.get('verdict')}")
    print(f"escalated: {result.get('action') == 'escalate'}")
    print(f"independent votes: {result.get('independent_vote_count')}")

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

    analysis_agent = OllamaAgent(
        name="analysis_agent",
        role="analyzer",
        mcp_server_url="http://localhost:8002",
        system_prompt="You are an analysis agent. Call the get_metrics tool and return the result as JSON."
    )

    task = "get current average latency metrics"
    
    result = await enforcer.safe_call(analysis_agent, task, turn=1)

    print(f"\nstatus: {result.get('status')}")
    print(f"is_fallback: {result.get('is_fallback')}")
    print(f"cache_age: {result.get('cache_age_seconds')}s")
    print(f"warning present: {'_warning' in result}")
    print(f"cache_rejected: {result.get('cache_rejected', False)}")

    if "_warning" in result:
        print("✓ contract caught silent fallback — orchestrator alerted")
    else:
        print("✗ fallback passed through silently")

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
    print("same contract. same enforcer. real agents this time.")

if __name__ == "__main__":
    asyncio.run(main())
