"""
bench/projection.py  --  turn measured call counts into projected token/cost.

The split this module enforces:

    MEASURED   : how many agent calls happen with vs without a contract.
                 Reproducible by anyone running runner.py. This is the claim.

    PROJECTED  : tokens = calls * measured_tokens_per_call
                 cost   = tokens * USD_PER_TOKEN
                 Derived numbers. Always labelled as projections on the slide
                 and in the output. Never presented as something we measured
                 during the mock run (the mock run consumes zero tokens).

The per-call token figure comes from measure_tokens.py (real llama3.2 runs).
If you haven't run that yet, a clearly-flagged fallback is used so the demo
still runs -- but tokens_are_measured will be False, which the runner prints,
so you never accidentally show an unmeasured number on stage.
"""
import json
from pathlib import Path

# Only used if results/token_baseline.json does not exist yet.
# Conservative-ish so it never inflates the story. Flagged everywhere as
# NOT measured.
_FALLBACK_TOKENS_PER_CALL = 600.0

# Illustrative hosted-model pricing, ~$3 per million tokens.
# llama3.2 runs locally and costs essentially nothing; this answers the
# separate question "what would this loop have cost on a paid hosted model".
# Say exactly that on stage -- don't imply you were billed this.
USD_PER_TOKEN = 3e-6


def load_token_baseline(path: str = "results/token_baseline.json"):
    """Return (tokens_per_call, is_measured)."""
    p = Path(path)
    if p.exists():
        data = json.loads(p.read_text())
        return float(data["mean_tokens_per_call"]), True
    return _FALLBACK_TOKENS_PER_CALL, False


def project(call_count: int, tokens_per_call: float) -> dict:
    tokens = call_count * tokens_per_call
    return {
        "projected_tokens": round(tokens),
        "projected_cost_usd": round(tokens * USD_PER_TOKEN, 4),
    }


def pct_reduction(without: float, with_: float) -> float:
    """Honest reduction percentage. Returns e.g. 92.1, not a rounded-up 94."""
    if without == 0:
        return 0.0
    return round((without - with_) / without * 100, 1)