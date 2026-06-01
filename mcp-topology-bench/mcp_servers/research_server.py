import json
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("research-agent")

@mcp.resource("topology://research-agent/card")
def get_server_card() -> str:
    # the contract lives right on the server — this is how we make topologies discoverable 
    contract = {
      "server_id": "research-agent",
      "schema_version": "0.1.0",
      "description": "Research agent — searches and summarizes information",
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
def search(query: str) -> str:
    """Search for information on a given topic"""
    print(f"research_server: search called with query: {query}")
    
    query_lower = query.lower()
    
    # fake realistic data to make the multi-agent flows look grounded
    if "quantum" in query_lower:
        results = [
            {"title": "Quantum Error Correction Trends", "summary": "New topological codes reduce overhead.", "source": "Nature Physics", "relevance_score": 0.95},
            {"title": "Qubit Fidelity Milestones", "summary": "2-qubit gate fidelities pass 99.9%.", "source": "PRX Quantum", "relevance_score": 0.88},
            {"title": "Scaling Quantum Hardware", "summary": "Wiring constraints in dilution refrigerators.", "source": "IEEE", "relevance_score": 0.82}
        ]
    elif "energy" in query_lower:
        results = [
            {"title": "Solid State Battery Density", "summary": "Energy density surpasses 500 Wh/kg.", "source": "Joule", "relevance_score": 0.96},
            {"title": "Grid Storage Deployments", "summary": "California adds 2GW of battery storage.", "source": "Energy.gov", "relevance_score": 0.91},
            {"title": "Solar Perovskite Efficiency", "summary": "Tandem cells reach 33% efficiency in lab.", "source": "Science", "relevance_score": 0.85}
        ]
    elif "climate" in query_lower:
        results = [
            {"title": "Ocean Temperature Anomalies", "summary": "North Atlantic surface temperatures peak.", "source": "NOAA", "relevance_score": 0.98},
            {"title": "Arctic Ice Minimums", "summary": "September ice extent tracks below average.", "source": "NSIDC", "relevance_score": 0.94},
            {"title": "Carbon Capture Costs", "summary": "Direct air capture costs drop below $200/ton.", "source": "Nature Climate", "relevance_score": 0.86}
        ]
    else:
        results = [
            {"title": "Generic Research Result A", "summary": "An exploration of general methodologies.", "source": "Journal of General Studies", "relevance_score": 0.70},
            {"title": "Foundational Studies", "summary": "A review of foundational literature in the field.", "source": "Annual Reviews", "relevance_score": 0.65},
            {"title": "Recent Advancements", "summary": "Key papers published in the last quarter.", "source": "arXiv", "relevance_score": 0.60}
        ]
        
    return json.dumps(results)

if __name__ == "__main__":
    print("research MCP server starting on port 8001")
    print("topology contract embedded in server card")
    print("tools available: search")
    import uvicorn
    uvicorn.run(mcp.sse_app(), host="0.0.0.0", port=8001)
