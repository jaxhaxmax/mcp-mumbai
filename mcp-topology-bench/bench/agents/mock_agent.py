class MockAgent:
    def __init__(self, name: str, behavior: str = "normal"):
        self.name = name
        self.behavior = behavior
        self.call_count = 0
        
    async def call(self, task: str, context: dict = None) -> dict:
        if context is None:
            context = {}
            
        self.call_count += 1
        
        if self.behavior == "loop":
            # agent never takes final responsibility, always delegates
            return {
                "status": "delegating",
                "to": "peer_node",
                "reason": "need more context first",
                "verdict": "unknown"
            }
            
        elif self.behavior == "anchor":
            # the agent that anchors on whatever it saw first
            prior = context.get("prior_vote")
            if prior:
                return {
                    "status": "success",
                    "verdict": prior.get("verdict", "safe"),
                    "is_independent": False, # honest flag for testing
                    "reason": "looks good to me too"
                }
            return {
                "status": "success",
                "verdict": "safe",
                "is_independent": False # still not independent, it's an anchor by nature
            }
            
        elif self.behavior == "silent_fallback":
            # simulates a tool timeout internally but returns fake success
            return {
                "status": "success",
                "result": 142.3,
                "is_fallback": True,
                "cache_age_seconds": 7200,
                "verdict": "safe"
            }
            
        # normal behavior default
        return {
            "status": "success",
            "result": "completed",
            "verdict": "safe",
            "is_independent": True
        }
