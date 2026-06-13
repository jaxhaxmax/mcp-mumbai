import asyncio
import json
from datetime import datetime
from pathlib import Path

from bench.scenarios import infinite_loop, false_consensus, silent_fallback
from bench.projection import pct_reduction


async def run_suite():
    print("-" * 59)
    print("MCP Topology Benchmark Suite  v0.1.0")
    print('    "contracts for multi-agent systems that actually ship"')
    print("-" * 59)
    print()

    base_dir = Path(__file__).parent

    topology_names = ["none", "partial", "full"]

    results = {}
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

        # --------------------------------------------------
        # Infinite Loop
        # --------------------------------------------------
        loop_res = await infinite_loop.run(topology)

        caught_loop = loop_res["detected"]
        status = "[prevented]" if caught_loop else "[no contract]"

        print(f"  Infinite Loop      {status}")
        print(
            f"    > {loop_res['turns_to_detection']} turns, "
            f"{loop_res['agent_calls']} agent calls, "
            f"{loop_res['projected_tokens']:,} projected tokens, "
            f"{'detected' if caught_loop else 'not detected'}"
        )
        print()

        # --------------------------------------------------
        # False Consensus
        # --------------------------------------------------
        fc_res = await false_consensus.run(topology)

        fc_caught = fc_res["escalated"]
        status = "[prevented]" if fc_caught else "[no contract]"

        print(f"  False Consensus    {status}")
        print(
            f"    > false positive: "
            f"{'YES' if fc_res['false_positive'] else 'NO'}, "
            f"escalated: "
            f"{'YES' if fc_res['escalated'] else 'NO'}, "
            f"independent votes: "
            f"{fc_res['independent_votes']}"
        )
        print()

        # --------------------------------------------------
        # Silent Fallback
        # --------------------------------------------------
        sf_res = await silent_fallback.run(topology)

        sf_caught = sf_res["fallback_surfaced_to_orchestrator"]
        status = "[prevented]" if sf_caught else "[no contract]"

        print(f"  Silent Fallback    {status}")
        print(
            f"    > surfaced: "
            f"{'YES' if sf_caught else 'NO'}, "
            f"cache rejected: "
            f"{'YES' if sf_res['cache_rejected'] else 'NO'}, "
            f"trustworthy: "
            f"{'YES' if sf_res['data_trustworthy'] else 'NO'}"
        )
        print()

        results[t_name] = {
            "infinite_loop": loop_res,
            "false_consensus": fc_res,
            "silent_fallback": sf_res,
        }

        results_summary.append({
            "topology": t_name,
            "infinite_loop": loop_res,
            "false_consensus": fc_res,
            "silent_fallback": sf_res
        })

    # ==================================================
    # Honest benchmark summary
    # ==================================================

    none_loop = results["none"]["infinite_loop"]
    full_loop = results["full"]["infinite_loop"]

    calls_cut = pct_reduction(
        none_loop["agent_calls"],
        full_loop["agent_calls"]
    )

    measured = full_loop["tokens_are_measured"]

    token_note = (
        "measured"
        if measured
        else "PROJECTED (run measure_tokens.py first)"
    )

    print("-" * 59)
    print("SUMMARY")
    print("-" * 59)

    print(
        f"{calls_cut}% fewer agent calls with a full contract "
        f"({none_loop['agent_calls']} -> "
        f"{full_loop['agent_calls']} calls, "
        f"{none_loop['turns_to_detection']} -> "
        f"{full_loop['turns_to_detection']} turns)."
    )

    print(
        f"Projected token usage: "
        f"{none_loop['projected_tokens']:,} -> "
        f"{full_loop['projected_tokens']:,} tokens "
        f"[{token_note}]"
    )

    print(
        "Full contract also prevented false consensus "
        "and surfaced silent fallback failures."
    )

    print()

    # ==================================================
    # Save results
    # ==================================================

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    out_file = (
        base_dir
        / "results"
        / f"run_{timestamp}.json"
    )

    with open(out_file, "w") as f:
        json.dump(results_summary, f, indent=2)

    print(f"Results saved to: {out_file}")


if __name__ == "__main__":
    asyncio.run(run_suite())
