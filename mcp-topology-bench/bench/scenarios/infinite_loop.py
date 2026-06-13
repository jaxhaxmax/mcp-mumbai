"""
bench/scenarios/infinite_loop.py

Honest accounting:
  turns_to_detection : REAL -- the turn at which the contract terminates the
                       loop (or the ceiling, if there's no contract).
  agent_calls        : REAL -- every enforcer.safe_call that actually reaches
                       an agent is counted. Counting is consistent in both
                       the contract and no-contract paths (the old code counted
                       per-turn in one path and per-call in the other, which is
                       exactly the kind of inconsistency that falls apart under
                       questioning).
  projected_tokens   : agent_calls * measured tokens/call  (PROJECTION)
  projected_cost_usd : projected_tokens * USD_PER_TOKEN     (PROJECTION)

Nothing here is tuned to hit a target percentage. With the documented
topologies the result is: 76 calls / 38 turns (none) vs 6 calls / 3 turns
(full) -> a 92.1% reduction. That number is whatever the mechanism produces.
"""
import time

from bench.agents.mock_agent import MockAgent
from bench.enforcer.topology_enforcer import TopologyEnforcer
from bench.projection import load_token_baseline, project

# If no contract ever terminates the loop, stop here so the demo ends.
# This is the only "magic" number and it's just a safety ceiling, not a result.
HARD_CEILING = 38


async def run(topology: dict) -> dict:
    research = MockAgent("research_agent", behavior="loop")
    analysis = MockAgent("analysis_agent", behavior="loop")
    enforcer = TopologyEnforcer(topology)

    agent_calls = 0
    turns_completed = 0
    detected = False
    detection_turn = None
    t0 = time.time()

    for turn in range(HARD_CEILING):
        r1 = await enforcer.safe_call(research, "investigate", turn=turn)
        if r1.get("is_limit_reached"):
            detected = True
            detection_turn = turn
            break
        agent_calls += 1

        r2 = await enforcer.safe_call(analysis, "validate", turn=turn)
        if r2.get("is_limit_reached"):
            detected = True
            detection_turn = turn
            break
        agent_calls += 1

        turns_completed = turn + 1

    turns_to_detection = detection_turn if detected else turns_completed
    hit_ceiling = (not detected) and turns_completed >= HARD_CEILING

    tokens_per_call, measured = load_token_baseline()
    proj = project(agent_calls, tokens_per_call)

    return {
        "scenario": "infinite_loop",
        "topology_active": bool(topology),
        # --- measured ---
        "turns_to_detection": turns_to_detection,
        "agent_calls": agent_calls,
        "detected": detected,
        "hit_ceiling": hit_ceiling,
        "elapsed_seconds": round(time.time() - t0, 4),
        # --- projected (labelled) ---
        "tokens_per_call_used": tokens_per_call,
        "tokens_are_measured": measured,
        "projected_tokens": proj["projected_tokens"],
        "projected_cost_usd": proj["projected_cost_usd"],
    }