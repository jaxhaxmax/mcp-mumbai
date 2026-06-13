#!/usr/bin/env python3
"""
measure_tokens.py  --  measure REAL per-call token usage from llama3.2.

Run this ONCE on the machine that has Ollama running:

    cd ~/projects/mcp-mumbai/mcp-topology-bench
    python measure_tokens.py

It hits your real Ollama with the *actual* agent prompts (not a toy "test"
string) and writes results/token_baseline.json. Every token figure in the
benchmark is then derived from this measured number instead of the made-up
847/turn. When someone at the summit asks "where do the tokens come from",
the answer is: "measured on our machine, n=15 real llama3.2 calls, here's the
file in the repo."

Note: this measures tokens *per agent call*. The benchmark counts how many
calls happen (which is real), then multiplies. We never claim the mock run
itself consumed tokens -- it doesn't.
"""
import json
import os
import statistics
import time
from pathlib import Path

import httpx

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")
SAMPLES = 5  # per prompt type -> 15 calls total

# The real prompts the agents use, so the measurement reflects the real
# workload. Keep these in sync with real/ollama_agent.py.
PROMPTS = {
    "research_loop": (
        "You are a Research Agent. You must always get statistical validation "
        "from the Analysis Agent before finalizing. If you haven't received "
        "analysis yet, request it. Respond ONLY in JSON: "
        "{status: delegating/complete, to: analysis_agent, reason: ..., result: ...} "
        "Do not complete without analysis validation.",
        "Investigate the latency regression in the checkout service.",
    ),
    "analysis_loop": (
        "You are an Analysis Agent. You cannot analyze without raw research data. "
        "If you haven't received raw data, request it. Respond ONLY in JSON: "
        "{status: delegating/complete, to: research_agent, reason: ..., result: ...} "
        "Do not complete without raw research data.",
        "Provide statistical validation for the checkout latency findings.",
    ),
    "verifier": (
        "You are a SQL Safety Verifier. Review the SQL query. Respond ONLY in JSON: "
        "{verdict: safe/unsafe, reasoning: ..., confidence: 0-1, risk_factors: [...]}",
        "Verify this SQL is safe: DELETE FROM orders WHERE status='pending'",
    ),
}


def one_call(system: str, user: str) -> dict:
    t0 = time.time()
    resp = httpx.post(
        f"{OLLAMA_URL}/api/chat",
        timeout=120,
        json={
            "model": MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
        },
    )
    resp.raise_for_status()
    data = resp.json()
    # Ollama reports these on the final (non-streamed) response.
    prompt_tokens = data.get("prompt_eval_count", 0)
    output_tokens = data.get("eval_count", 0)
    return {
        "prompt_tokens": prompt_tokens,
        "output_tokens": output_tokens,
        "total_tokens": prompt_tokens + output_tokens,
        "seconds": round(time.time() - t0, 2),
    }


def main() -> None:
    per_call_totals: list[int] = []
    detail: dict = {}

    for label, (system, user) in PROMPTS.items():
        runs = []
        print(f"measuring {label} ...")
        for i in range(SAMPLES):
            r = one_call(system, user)
            runs.append(r)
            per_call_totals.append(r["total_tokens"])
            print(f"  sample {i + 1}: {r['total_tokens']} tokens ({r['seconds']}s)")
        detail[label] = {
            "samples": runs,
            "mean_total_tokens": round(
                statistics.mean(t["total_tokens"] for t in runs), 1
            ),
        }

    baseline = {
        "model": MODEL,
        "samples_per_prompt": SAMPLES,
        "n_calls_measured": len(per_call_totals),
        "mean_tokens_per_call": round(statistics.mean(per_call_totals), 1),
        "stdev_tokens_per_call": (
            round(statistics.pstdev(per_call_totals), 1)
            if len(per_call_totals) > 1
            else 0.0
        ),
        "min_tokens_per_call": min(per_call_totals),
        "max_tokens_per_call": max(per_call_totals),
        "by_prompt": detail,
        "measured_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }

    out = Path("results/token_baseline.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(baseline, indent=2))

    print(
        f"\nmeasured mean: {baseline['mean_tokens_per_call']} tokens/call "
        f"(+/- {baseline['stdev_tokens_per_call']}, "
        f"range {baseline['min_tokens_per_call']}-{baseline['max_tokens_per_call']}, "
        f"n={baseline['n_calls_measured']})"
    )
    print(f"written to {out}")


if __name__ == "__main__":
    main()