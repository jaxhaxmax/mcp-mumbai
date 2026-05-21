import asyncio

class TopologyEnforcer:
    def __init__(self, topology: dict):
        self.topology = topology

    async def safe_call(self, agent, task: str, turn: int = 0) -> dict:
        # enforce termination contract if present
        termination = self.topology.get("termination", {})
        if termination:
            max_turns = termination.get("max_turns", 999)
            if turn >= max_turns:
                return {
                    "result": None,
                    "is_limit_reached": True,
                    "turn": turn,
                    "message": "hit the turn limit — returning what we have"
                }

        result = await agent.call(task)

        # enforce propagation contract if present
        propagation = self.topology.get("propagation", {})
        if propagation and propagation.get("fallback_must_be_flagged"):
            if result.get("is_fallback"):
                # caught a fallback that tried to pass silently
                result["_warning"] = "data is stale or came from a fallback mechanism"
                
                max_age = propagation.get("cache_max_age_seconds", 0)
                if result.get("cache_age_seconds", 0) > max_age:
                    result["cache_rejected"] = True

        return result

    async def blind_vote(self, agents: list, task: str) -> dict:
        dissent = self.topology.get("dissent")
        
        if not dissent:
            # no contract — agents see each other's answers here — that's the whole problem
            votes = []
            prior = None
            for agent in agents:
                context = {"prior_vote": prior} if prior else {}
                vote = await agent.call(task, context=context)
                votes.append(vote)
                prior = vote   # chained context leads right back to anchoring
            
            verdicts = [v.get("verdict", "safe") for v in votes]
            return {
                "consensus": True,
                "verdict": max(set(verdicts), key=verdicts.count),
                "independent_vote_count": 1,  # physically honest — we're admitting this
                "votes": votes
            }
            
        elif dissent.get("voting_mode") == "blind":
            # blind mode forces them into parallel execution tracks
            votes = await asyncio.gather(*[a.call(task, context={}) for a in agents])
            
            verdicts = [v.get("verdict", "safe") for v in votes]
            unique_verdicts = set(verdicts)
            
            independent_count = sum(1 for v in votes if v.get("is_independent", True))
            min_ind = dissent.get("min_independent_votes", 1)
            
            # check dissent first — if verdicts differ, escalate regardless
            if len(unique_verdicts) > dissent.get("veto_threshold", 1):
                return {
                    "consensus": False,
                    "action": "escalate",
                    "verdicts": verdicts,
                    "independent_vote_count": len(votes),  # total agents polled
                    "message": "dissent detected — escalating to orchestrator"
                }
            
            # then check independence
            if independent_count < min_ind:
                return {
                    "consensus": False,
                    "action": "escalate",
                    "verdicts": verdicts,
                    "independent_vote_count": len(votes),
                    "message": f"only {independent_count} independent votes, need {min_ind} — escalating"
                }
            
            return {
                "consensus": True,
                "verdict": verdicts[0],
                "independent_vote_count": independent_count,
                "votes": votes
            }
