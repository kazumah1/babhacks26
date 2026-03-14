"""Shared utilities for adapter implementations."""

import json
import re


def extract_json(text: str) -> dict:
    """
    Robustly extract a JSON object from a string that may contain:
    - prose before/after the JSON
    - markdown code fences (```json ... ```)
    - raw JSON

    Falls back to an empty dict if nothing parseable is found.
    """
    # 1. Try a fenced block first: ```json ... ```
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1))
        except json.JSONDecodeError:
            pass

    # 2. Find the first { and the matching closing }
    start = text.find("{")
    if start != -1:
        # Walk forward counting braces to find the matching close
        depth = 0
        for i, ch in enumerate(text[start:], start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : i + 1])
                    except json.JSONDecodeError:
                        break

    # 3. Give up — return an empty dict; caller will handle gracefully
    return {}
