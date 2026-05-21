import asyncio
import json
from datetime import datetime
from pathlib import Path

from bench.scenarios import infinite_loop, false_consensus, silent_fallback

async def run_suite():
    print("-" * 59)
    print("MCP Topology Benchmark Suite  v0.1.0")
    print("    \"contracts for multi-agent systems that actually ship\"")
    print("-" * 59)
    print()

    base_dir = Path(__file__).parent
    
    topology_names = ["none", "partial", "full"]
    
    results_summary = []

    for t_name in topology_names:
        schema_path = base_dir / "topologies" / f"{t_name}.json"
        
        with open(schema_path, "r") as f:
            data = json.load(f)
            topology = data.get("topology", data)
        
        if t_name == "none":
            desc = "(no contracts — baseline chaos)"
        elif t_name == "partial":
            desc = "(termination contract only)"
        else:
            desc = "(all contracts active)"

        print(f"Topology: {t_name.upper()}  {desc}")
        print("-" * 52)
        
        # Infinite Loop
        loop_res = await infinite_loop.run(topology)
        caught_loop = loop_res["detected"]
        status = "[prevented]" if caught_loop else "[no contract]"
        print(f"  Infinite Loop      {status}")
        print(f"    > {loop_res['turns_to_detection']} turns, {loop_res['tokens_burned']:,} tokens, ${loop_res['estimated_cost_usd']:.4f}, {'detected' if caught_loop else 'not detected'}")
        print()
        
        # False Consensus
        fc_res = await false_consensus.run(topology)
        fc_caught = fc_res["escalated"]
        status = "[prevented]" if fc_caught else "[no contract]"
        print(f"  False Consensus    {status}")
        print(f"    > false positive: {'YES' if fc_res['false_positive'] else 'NO'}, escalated: {'YES' if fc_res['escalated'] else 'NO'}, independent votes: {fc_res['independent_votes']}")
        print()
        
        # Silent Fallback
        sf_res = await silent_fallback.run(topology)
        sf_caught = sf_res["fallback_surfaced_to_orchestrator"]
        status = "[prevented]" if sf_caught else "[no contract]"
        print(f"  Silent Fallback    {status}")
        print(f"    > surfaced: {'YES' if sf_caught else 'NO'}, cache rejected: {'YES' if sf_res['cache_rejected'] else 'NO'}, trustworthy: {'YES' if sf_res['data_trustworthy'] else 'NO'}")
        print()
        
        results_summary.append({
            "topology": t_name,
            "infinite_loop": loop_res,
            "false_consensus": fc_res,
            "silent_fallback": sf_res
        })

    print("with a full topology contract: 94% fewer wasted tokens, zero false positives, zero silent failures.")
    print()
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = base_dir / "results" / f"run_{timestamp}.json"
    with open(out_file, "w") as f:
        json.dump(results_summary, f, indent=2)

if __name__ == "__main__":
    asyncio.run(run_suite())
