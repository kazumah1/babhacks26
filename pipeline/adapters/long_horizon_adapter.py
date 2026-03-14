import os

from dotenv import load_dotenv
load_dotenv()

import anthropic
from datetime import datetime

from shared.types import AdapterContext, MarketSnapshot
from pipeline.adapters.base_adapter import BaseAdapter
from pipeline.adapters._utils import extract_json

_client = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


BRIEFING_PROMPT = """Build a research briefing for this prediction market.

Market Question: {question}
Analysis Date: {date}
Current Market Probability (YES): {probability:.1%}
Days to Resolution: {days}

Search for recent developments, base rates, expert views, and key uncertainties.
Focus your research on information available as of {date}.

Respond with a single JSON object and nothing else:
{{
  "summary": "<2-3 sentence overview of the situation>",
  "bull_case": "<key reasons YES is more likely>",
  "bear_case": "<key reasons NO is more likely>",
  "base_rate": "<historical frequency of similar events, or Not available>",
  "key_dates": ["<YYYY-MM-DD: event description>"],
  "uncertainty_factors": ["<factor>"]
}}"""


class LongHorizonAdapter(BaseAdapter):
    def build_context(
        self,
        market: MarketSnapshot,
        replay_timestamp: datetime,
    ) -> AdapterContext:
        client = _get_client()

        # Normalise datetimes to naive for arithmetic
        end = market.end_date
        replay = replay_timestamp
        if end is not None:
            if end.tzinfo is not None:
                end = end.replace(tzinfo=None)
            if replay.tzinfo is not None:
                replay = replay.replace(tzinfo=None)
            days_to_resolution = max((end - replay).days, 0)
        else:
            days_to_resolution = 90

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{
                "role": "user",
                "content": BRIEFING_PROMPT.format(
                    question=market.question,
                    date=replay_timestamp.strftime("%Y-%m-%d"),
                    probability=market.yes_price,
                    days=days_to_resolution,
                ),
            }],
        )

        # Concatenate all text blocks (web_search may produce multiple)
        all_text = "\n".join(
            b.text for b in response.content if hasattr(b, "text")
        )
        briefing = extract_json(all_text)

        past_history = [p for p in market.price_history if p.timestamp <= replay_timestamp]

        key_dates_lines = "\n".join(f"- {d}" for d in briefing.get("key_dates", []))
        uncertainty_lines = "\n".join(f"- {f}" for f in briefing.get("uncertainty_factors", []))

        return AdapterContext(
            market_id=market.market_id,
            market_question=market.question,
            market_type="long_horizon",
            current_probability=market.yes_price,
            price_history=past_history,
            context_documents=[
                f"SITUATION SUMMARY:\n{briefing.get('summary', 'No summary available.')}",
                f"BULL CASE (YES more likely):\n{briefing.get('bull_case', 'Not determined.')}",
                f"BEAR CASE (NO more likely):\n{briefing.get('bear_case', 'Not determined.')}",
                f"HISTORICAL BASE RATE:\n{briefing.get('base_rate', 'Not available')}",
                f"KEY DATES:\n{key_dates_lines}" if key_dates_lines else "KEY DATES:\nNone identified",
                f"KEY UNCERTAINTY FACTORS:\n{uncertainty_lines}" if uncertainty_lines else "KEY UNCERTAINTY FACTORS:\nNone identified",
            ],
            metadata={
                "days_to_resolution": days_to_resolution,
                "briefing": briefing,
            },
            replay_timestamp=replay_timestamp,
            resolution=market.resolution,
        )
