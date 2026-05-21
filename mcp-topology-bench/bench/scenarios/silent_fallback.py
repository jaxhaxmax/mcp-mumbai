from bench.agents.mock_agent import MockAgent
from bench.enforcer.topology_enforcer import TopologyEnforcer

async def run(topology: dict) -> dict:
    agent = MockAgent("analysis_agent", behavior="silent_fallback")
    enforcer = TopologyEnforcer(topology)
    
    task = "get_current_avg_latency"
    
    result = await enforcer.safe_call(agent, task, turn=1)
    
    fallback_occurred = result.get("is_fallback", False)
    fallback_surfaced = "_warning" in result
    cache_age_seconds = result.get("cache_age_seconds", 0)
    
    cache_rejected = result.get("cache_rejected", False)
    
    # data is only trustworthy if no fallback occurred at all
    data_trustworthy = not fallback_occurred
    
    return {
        "scenario": "Silent Fallback",
        "topology_active": bool(topology),
        "fallback_occurred": fallback_occurred,
        "fallback_surfaced_to_orchestrator": fallback_surfaced,
        "cache_age_seconds": cache_age_seconds,
        "cache_rejected": cache_rejected,
        "data_trustworthy": data_trustworthy
    }
