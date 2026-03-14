import json
import os
import time

from dotenv import load_dotenv
load_dotenv()

import anthropic
from pipeline.adapters._utils import extract_json

_client = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


CLASSIFIER_PROMPT = """Classify this prediction market question into exactly one category:
- long_horizon: macro reasoning, policy, tech releases, multi-week events
- speech: predicts whether a specific word/phrase will appear in a speech, debate, press conference, or interview
- unknown: does not fit the above categories

Respond with a single JSON object and nothing else:
{{"market_type": "<category>", "confidence": <0.0-1.0>, "reasoning": "<one sentence>"}}

Market question: {question}
"""


def classify_market(question: str) -> dict:
    client = _get_client()

    for attempt in range(3):
        try:
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=256,
                messages=[{"role": "user", "content": CLASSIFIER_PROMPT.format(question=question)}],
            )
            raw = response.content[0].text
            result = extract_json(raw)
            if not result:
                result = {"market_type": "long_horizon", "confidence": 0.5, "reasoning": "JSON parse failed"}
            # Fallback: low-confidence or unknown → long_horizon
            if result.get("confidence", 0) < 0.6 or result.get("market_type") == "unknown":
                result["market_type"] = "long_horizon"
            return result
        except anthropic.RateLimitError:
            if attempt < 2:
                wait = 60 * (attempt + 1)
                print(f"[classifier] Rate limited — waiting {wait}s before retry {attempt + 2}/3")
                time.sleep(wait)
            else:
                raise


if __name__ == "__main__":
    import sys
    q = sys.argv[1] if len(sys.argv) > 1 else \
        "Will Jerome Powell say 'inflation' at the June 2025 Fed press conference?"
    result = classify_market(q)
    print(result)
