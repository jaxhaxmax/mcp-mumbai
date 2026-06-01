import json
import httpx
import threading
from typing import Optional

class OllamaAgent:
    def __init__(self, role: str, mcp_url: str, ollama_url: str = "http://localhost:11434", model: str = "llama3.2"):
        self.role = role
        self.mcp_url = mcp_url.rstrip("/")
        self.ollama_url = ollama_url.rstrip("/")
        self.model = model
        self.history = []
        self.session_id = None
        self.tools = []
        self._sse_client = None  # keeps the connection alive

        if role == "research":
            system_prompt = (
                "You are a research agent. Your job is to search for information "
                "using the search tool. Always call the search tool when given a "
                "topic. After getting results, summarize what you found and ask "
                "if you need to delegate to the analysis agent for deeper analysis. "
                "Keep responses concise."
            )
        elif role == "analysis":
            system_prompt = (
                "You are an analysis agent. Your job is to analyze data using the "
                "analyze tool and fetch metrics using get_metrics. Always call "
                "tools when given data to analyze. After analysis, provide a "
                "recommendation. Keep responses concise."
            )
        else:
            system_prompt = "You are a helpful assistant. Keep responses concise."

        self.history.append({"role": "system", "content": system_prompt})

    def connect(self):
        print(f"[{self.role}] connecting to MCP server at {self.mcp_url}")

        # We need to keep the SSE connection open — session dies the moment it closes
        self._sse_client = httpx.Client(timeout=None)
        
        with self._sse_client.stream("GET", f"{self.mcp_url}/sse") as r:
            for line in r.iter_lines():
                if line.startswith("data:") and "session_id=" in line:
                    self.session_id = line.split("session_id=")[1].strip()
                    break
            
            if not self.session_id:
                raise Exception("Failed to extract session_id from SSE stream")

            print(f"[{self.role}] session established: {self.session_id[:8]}...")

            # Fetch tools while SSE is still open — session is alive here
            self.tools = self._fetch_tools()
            tool_names = ", ".join([t["function"]["name"] for t in self.tools]) if self.tools else "none"
            print(f"[{self.role}] tools available: {tool_names}")

            # Keep SSE open in background thread so session stays valid
            self._keep_alive_thread = threading.Thread(
                target=self._drain_sse, args=(r,), daemon=True
            )
            self._keep_alive_thread.start()

    def _drain_sse(self, response):
        # Just read and discard — keeps the connection alive so session stays valid
        try:
            for _ in response.iter_lines():
                pass
        except Exception:
            pass

    def _fetch_tools(self) -> list:
        endpoint = f"{self.mcp_url}/messages/?session_id={self.session_id}"
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {}
        }
        try:
            r = httpx.post(endpoint, json=payload, timeout=5.0)
            data = r.json()
            mcp_tools = data.get("result", {}).get("tools", [])
            ollama_tools = []
            for mt in mcp_tools:
                ollama_tools.append({
                    "type": "function",
                    "function": {
                        "name": mt.get("name"),
                        "description": mt.get("description", ""),
                        "parameters": mt.get("inputSchema", {})
                    }
                })
            return ollama_tools
        except Exception as e:
            print(f"[{self.role}] warning: failed to fetch tools: {e}")
            return []

    def get_tools(self) -> list:
        return self.tools

    def call_tool(self, tool_name: str, arguments: dict) -> str:
        print(f"[{self.role}] → calling tool: {tool_name}({arguments})")
        endpoint = f"{self.mcp_url}/messages/?session_id={self.session_id}"
        payload = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments}
        }
        try:
            r = httpx.post(endpoint, json=payload, timeout=10.0)
            data = r.json()
            content_blocks = data.get("result", {}).get("content", [])
            result_str = ""
            for block in content_blocks:
                if block.get("type") == "text":
                    result_str += block.get("text", "")
            if not result_str and "result" in data:
                result_str = json.dumps(data["result"])
            preview = result_str[:80] + "..." if len(result_str) > 80 else result_str
            print(f"[{self.role}] ← tool result: {preview}")
            return result_str
        except Exception as e:
            err = f"tool call failed: {e}"
            print(f"[{self.role}] ← {err}")
            return err

    def think(self, user_message: str) -> str:
        self.history.append({"role": "user", "content": user_message})
        endpoint = f"{self.ollama_url}/api/chat"

        while True:
            payload = {
                "model": self.model,
                "messages": self.history,
                "stream": False
            }
            if self.tools:
                payload["tools"] = self.tools

            try:
                r = httpx.post(endpoint, json=payload, timeout=60.0)
                data = r.json()
            except Exception as e:
                return f"ollama api failed: {e}"

            msg = data.get("message", {})

            if msg.get("tool_calls"):
                self.history.append(msg)
                for tc in msg["tool_calls"]:
                    func = tc.get("function", {})
                    name = func.get("name")
                    args = func.get("arguments", {})
                    result = self.call_tool(name, args)
                    self.history.append({
                        "role": "tool",
                        "content": result,
                        "name": name
                    })
                continue

            content = msg.get("content")
            if content:
                self.history.append(msg)
                preview = content.replace('\n', ' ')
                preview = preview[:120] + "..." if len(preview) > 120 else preview
                print(f"[{self.role}] response: {preview}")
                return content

            return "no response"