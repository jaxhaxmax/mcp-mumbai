import json
import httpx
import threading
import queue
import time

class OllamaAgent:
    def __init__(self, role: str, mcp_url: str, ollama_url: str = "http://localhost:11434", model: str = "llama3.2"):
        self.role = role
        self.mcp_url = mcp_url.rstrip("/")
        self.ollama_url = ollama_url.rstrip("/")
        self.model = model
        self.history = []
        self.session_id = None
        self.tools = []
        self._response_queue = queue.Queue()  # SSE messages land here

        if role == "research":
            system_prompt = (
                "You are a Research Agent in a multi-agent system. "
                "Your job is to research topics and provide summaries. "
                "You must always get statistical validation from the Analysis Agent "
                "before you can finalize any research summary. "
                "If you have not received analysis yet, you must request it. "
                "Always respond in this exact JSON format with no extra text: "
                '{"status": "delegating", "to": "analysis_agent", "reason": "...", "result": "..."}'
                " or "
                '{"status": "complete", "result": "your final summary"}'
            )
        elif role == "analysis":
            system_prompt = (
                "You are an Analysis Agent in a multi-agent system. "
                "Your job is to statistically validate research data. "
                "You cannot analyze anything without first receiving raw research data. "
                "If you have not received raw data, you must request it. "
                "Always respond in this exact JSON format with no extra text: "
                '{"status": "delegating", "to": "research_agent", "reason": "...", "result": "..."}'
                " or "
                '{"status": "complete", "result": "your final analysis"}'
            )
        elif role == "verifier":
            system_prompt = (
                "You are a SQL Safety Verifier Agent. "
                "Review the provided SQL query and assess whether it is safe to execute. "
                "Always respond in this exact JSON format with no extra text: "
                '{"verdict": "safe", "reasoning": "...", "is_independent": true, "risk_factors": []}'
                " or "
                '{"verdict": "unsafe", "reasoning": "...", "is_independent": true, "risk_factors": ["..."]}'
            )
        else:
            system_prompt = "You are a helpful assistant. Keep responses concise."

        self.history.append({"role": "system", "content": system_prompt})

    def connect(self):
        print(f"[{self.role}] connecting to MCP server at {self.mcp_url}")

        session_ready = threading.Event()

        def run_sse():
            with httpx.stream("GET", f"{self.mcp_url}/sse", timeout=None) as r:
                for line in r.iter_lines():
                    if line.startswith("data:") and "session_id=" in line:
                        self.session_id = line.split("session_id=")[1].strip()
                        session_ready.set()
                    elif line.startswith("data:") and line != "data:":
                        # all subsequent messages go into the shared queue
                        self._response_queue.put(line)

        self._sse_thread = threading.Thread(target=run_sse, daemon=True)
        self._sse_thread.start()

        # wait until session_id is captured
        session_ready.wait(timeout=5)

        if not self.session_id:
            raise Exception("Failed to extract session_id from SSE stream")

        print(f"[{self.role}] session established: {self.session_id[:8]}...")

        self._initialize()

        self.tools = self._fetch_tools()
        tool_names = ", ".join([t["function"]["name"] for t in self.tools]) if self.tools else "none"
        print(f"[{self.role}] tools available: {tool_names}")

    def _post(self, payload: dict):
        endpoint = f"{self.mcp_url}/messages/?session_id={self.session_id}"
        httpx.post(endpoint, json=payload, timeout=10.0)

    def _wait_for_response(self, timeout: int = 8) -> dict:
        # drain the queue until we get a real result or error message
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                line = self._response_queue.get(timeout=1)
                if '"result"' in line or '"error"' in line:
                    raw = line.split("data: ", 1)[1] if "data: " in line else line
                    return json.loads(raw)
            except queue.Empty:
                continue
        raise TimeoutError("timed out waiting for SSE response")

    def _initialize(self):
        # MCP requires a handshake before any other request
        self._post({
            "jsonrpc": "2.0", "id": 0, "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "ollama-agent", "version": "1.0"}
            }
        })
        self._wait_for_response()  # consume the initialize response

        self._post({
            "jsonrpc": "2.0", "method": "notifications/initialized", "params": None
        })
        time.sleep(0.3)

    def _fetch_tools(self) -> list:
        self._post({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": None})
        try:
            data = self._wait_for_response()
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

    def call_tool(self, tool_name: str, arguments: dict) -> str:
        print(f"[{self.role}] → calling tool: {tool_name}({arguments})")
        self._post({
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments}
        })
        try:
            data = self._wait_for_response()
            content_blocks = data.get("result", {}).get("content", [])
            result_str = ""
            for block in content_blocks:
                if block.get("type") == "text":
                    result_str += block.get("text", "")
            if not result_str:
                result_str = json.dumps(data.get("result", {}))
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
    async def call(self, task: str, context: dict = None) -> dict:
        # called by the enforcer — connects on first call, then delegates to think()
        if not self.session_id:
            self.connect()

        if context and context.get("prior_vote"):
            task = task + f"\n\nNote: another agent responded: {json.dumps(context['prior_vote'])}"

        raw = self.think(task)

        # check if any tool result in history has is_fallback set
        # the enforcer needs to see this flag to catch silent fallbacks
        is_fallback = False
        cache_age = 0
        for msg in self.history:
            if msg.get("role") == "tool":
                try:
                    tool_data = json.loads(msg.get("content", "{}"))
                    if tool_data.get("is_fallback"):
                        is_fallback = True
                        cache_age = tool_data.get("cache_age_seconds", 0)
                except Exception:
                    pass

        try:
            parsed = json.loads(raw)
            if is_fallback:
                parsed["is_fallback"] = True
                parsed["cache_age_seconds"] = cache_age
            return parsed
        except Exception:
            result = {
                "status": "complete",
                "result": raw,
                "verdict": "safe",
                "is_independent": True,
                "agent": self.role
            }
            if is_fallback:
                result["is_fallback"] = True
                result["cache_age_seconds"] = cache_age
            return result
