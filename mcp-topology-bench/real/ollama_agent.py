import json
import httpx
import asyncio
from dotenv import load_dotenv
import os

load_dotenv()

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")

LOOP_PROMPT = """You are a Research Agent in a multi-agent system.
Your job is to research topics and provide summaries.
However, you must always get statistical validation from the Analysis Agent
before you can finalize any research summary.
If you have not received analysis yet, you must request it.

Always respond in this exact JSON format:
{
  "status": "delegating" or "complete",
  "to": "analysis_agent" (if delegating),
  "reason": "why you need the other agent",
  "result": "your findings so far (if any)"
}

Do not complete the task without analysis validation."""

ANALYSIS_LOOP_PROMPT = """You are an Analysis Agent in a multi-agent system.
Your job is to statistically validate research data.
However, you cannot analyze anything without first receiving
the raw research data from the Research Agent.
If you have not received raw data, you must request it.

Always respond in this exact JSON format:
{
  "status": "delegating" or "complete", 
  "to": "research_agent" (if delegating),
  "reason": "why you need the other agent",
  "result": "your analysis so far (if any)"
}

Do not complete analysis without raw research data."""

VERIFIER_PROMPT = """You are a SQL Safety Verifier Agent.
Review the provided SQL query and assess whether it is safe to execute.

Always respond in this exact JSON format:
{
  "verdict": "safe" or "unsafe",
  "reasoning": "your assessment",
  "is_independent": true,
  "risk_factors": ["list", "of", "risks"]
}

Be thorough and independent in your assessment."""

class OllamaAgent:
    def __init__(self, name: str, role: str, mcp_server_url: str, system_prompt: str):
        self.name = name
        self.role = role
        self.mcp_server_url = mcp_server_url  
        self.system_prompt = system_prompt
        self.call_count = 0
        self.topology = {}

    async def load_topology(self):
        # in a real deployment this would be fetched from the server card
        # for the demo we load it from our local topology file
        # the contract is the same either way — it lives on the server
        try:
            with open("topologies/full.json") as f:
                data = json.load(f)
                self.topology = data.get("topology", data)
            print(f"{self.name}: topology contract loaded")
        except Exception as e:
            print(f"{self.name}: no topology found, running uncontracted")
            self.topology = {}

    async def call_mcp_tool(self, tool_name: str, arguments: dict) -> str:
        # this is where we actually call the MCP server tool over HTTP
        # MCP SSE servers accept tool calls at POST /messages/
        # with a JSON-RPC style body
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.mcp_server_url}/messages/",
                    params={"session_id": "demo-session"},
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "tools/call",
                        "params": {
                            "name": tool_name,
                            "arguments": arguments
                        }
                    }
                )
            
            print(f"{self.name}: called tool {tool_name}")
            return response.text
        except Exception as e:
            return json.dumps({"error": "tool call failed", "is_fallback": True})

    async def think(self, task: str, context: dict = None) -> str:
        if context is None:
            context = {}
            
        # ask Ollama what to do given the task and context
        # returns the raw LLM response text
        user_message = task
        if context.get("prior_vote"):
            user_message += f"\n\nNote: another agent responded: {json.dumps(context['prior_vote'])}"
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{OLLAMA_URL}/api/chat",
                json={
                    "model": OLLAMA_MODEL,
                    "messages": [
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": user_message}
                    ],
                    "stream": False
                }
            )
        
        return response.json()["message"]["content"]

    async def call(self, task: str, context: dict = None) -> dict:
        if context is None:
            context = {}
            
        # the main entry point — same interface as MockAgent
        # load topology on first call
        # think about what to do
        # try to call an MCP tool based on LLM decision
        # return structured result
        
        self.call_count += 1
        
        if not self.topology:
            await self.load_topology()
        
        print(f"{self.name}: thinking about task...")
        
        raw_response = await self.think(task, context)
        
        print(f"{self.name}: response received")
        
        # try to parse as JSON — LLM might return JSON or plain text
        try:
            parsed = json.loads(raw_response)
            return parsed
        except:
            # LLM returned plain text — wrap it into a standard result dict
            return {
                "status": "complete",
                "result": raw_response,
                "verdict": "safe",
                "is_independent": True,
                "agent": self.name
            }
