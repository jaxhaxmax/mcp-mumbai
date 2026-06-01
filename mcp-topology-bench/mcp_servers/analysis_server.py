import json
from datetime import datetime
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("analysis-agent")

SIMULATE_FAILURE = True

@mcp.resource("topology://analysis-agent/card")
def get_server_card() -> str:
    # embed the contract so the orchestrator can read it dynamically 
    contract = {
      "server_id": "analysis-agent",
      "schema_version": "0.1.0",
      "description": "Analysis agent — processes data and returns insights",
      "topology": {
        "termination": {
          "max_delegation_depth": 3,
          "max_turns": 3,
          "authority": "orchestrator",
          "on_limit_reached": "return_partial_with_flag"
        },
        "dissent": {
          "voting_mode": "blind",
          "min_independent_votes": 2,
          "allow_anchoring": False,
          "veto_threshold": 1,
          "on_consensus_failure": "escalate_to_orchestrator"
        },
        "propagation": {
          "fallback_allowed": True,
          "fallback_must_be_flagged": True,
          "flag_key": "is_fallback",
          "cache_max_age_seconds": 300,
          "on_tool_failure": "propagate_error_upstream"
        },
        "saturation": {
          "max_agents_in_topology": 5,
          "warn_at": 4,
          "reason": "coordination yields negative returns past threshold"
        }
      }
    }
    return json.dumps(contract, indent=2)

@mcp.tool()
def analyze(data: str) -> str:
    """Analyze data and return statistical insights"""
    
    # slice the data so the console doesn't flood if the orchestrator passes huge contexts
    preview = data if len(data) < 50 else data[:50] + "..."
    print(f"analysis_server: analyze called with data: {preview}")
    
    data_lower = data.lower()
    
    if "quantum" in data_lower:
        result = {
            "topic": "Quantum Computing",
            "confidence_score": 0.85,
            "recommendation": "Maintain cautious investment.",
            "risk_level": "High",
            "summary": "Hardware feasibility remains challenging due to decoherence."
        }
    elif "energy" in data_lower:
        result = {
            "topic": "Renewable Energy",
            "confidence_score": 0.92,
            "recommendation": "Accelerate grid-scale storage deployments.",
            "risk_level": "Low",
            "summary": "Storage density improvements drastically lower LCOE for renewables."
        }
    elif "climate" in data_lower:
        result = {
            "topic": "Climate Risk",
            "confidence_score": 0.89,
            "recommendation": "Update supply chain resiliency models.",
            "risk_level": "Critical",
            "summary": "Accelerating surface temperature anomalies increase disruption likelihood."
        }
    else:
        result = {
            "topic": "General Analysis",
            "confidence_score": 0.70,
            "recommendation": "Gather more specific domain data.",
            "risk_level": "Moderate",
            "summary": "Initial screening complete, awaiting deeper context."
        }
        
    return json.dumps(result)

@mcp.tool()
def get_metrics(metric_type: str) -> str:
    """Fetch current system metrics from the database"""
    
    status_label = "SIMULATING FALLBACK" if SIMULATE_FAILURE else "fresh data"
    print(f"analysis_server: get_metrics called — {status_label}")
    
    # This simulates a silent but graceful fallback where the database timed out 
    # and the system returned old data but falsely marked the status as 'success'.
    # This is exactly what the propagation contract is designed to catch!
    
    if SIMULATE_FAILURE:
        result = {
            "metric_type": metric_type,
            "value": 142.3, 
            "unit": "ms" if "latency" in metric_type.lower() else "units",
            "status": "success",
            "is_fallback": True,
            "cache_age_seconds": 7200,
            "timestamp": datetime.now().isoformat()
        }
    else:
        result = {
            "metric_type": metric_type,
            "value": 45.1,
            "unit": "ms" if "latency" in metric_type.lower() else "units",
            "status": "success", 
            "is_fallback": False,
            "cache_age_seconds": 0,
            "timestamp": datetime.now().isoformat()
        }
        
    return json.dumps(result)

if __name__ == "__main__":
    print("analysis MCP server starting on port 8002")
    print("topology contract embedded in server card")
    print("tools available: analyze, get_metrics")
    print(f"silent fallback simulation: {SIMULATE_FAILURE}")
    
    import uvicorn
    # Important: fastmcp requires running the internal Starlette app it binds to
    uvicorn.run(mcp.sse_app(), host="0.0.0.0", port=8002)
