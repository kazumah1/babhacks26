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


METADATA_PROMPT = """Extract metadata from this prediction market question about speech content.
Respond with a single JSON object and nothing else:
{{"speaker": "<full name or null>", "target_phrase": "<exact word or phrase being predicted>", "event_type": "<speech|debate|interview|press_conference|other>"}}

Question: {question}"""


ANALYSIS_PROMPT = """Analyze a speaker's linguistic patterns to predict whether a specific word/phrase
will appear in an upcoming {event_type}.

Speaker: {speaker}
Target Phrase: "{target_phrase}"
Analysis Date: {date}

Search for recent transcripts and recordings of this speaker.
Focus only on information available as of {date}.

Analyze:
1. How frequently they use this word/phrase
2. The contexts in which they use it
3. Whether current events make it more or less likely to appear

Respond with a single JSON object and nothing else:
{{
  "historical_frequency": "<e.g. frequently (multiple times per appearance), occasionally, rarely>",
  "usage_contexts": ["<context description>"],
  "current_relevance": "<why this phrase is or is not likely given current events>",
  "recent_examples": ["<YYYY-MM-DD: brief quote or context>"],
  "base_rate_estimate": <float 0.0-1.0>,
  "key_factors": ["<factor that raises or lowers likelihood>"]
}}"""


class SpeechAdapter(BaseAdapter):
    def build_context(
        self,
        market: MarketSnapshot,
        replay_timestamp: datetime,
    ) -> AdapterContext:
        client = _get_client()

        # Step 1: extract speaker / phrase / event metadata
        meta_resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=256,
            messages=[{
                "role": "user",
                "content": METADATA_PROMPT.format(question=market.question),
            }],
        )
        meta_text = meta_resp.content[0].text
        meta = extract_json(meta_text)
        if not meta:
            meta = {"speaker": "Unknown", "target_phrase": "the target phrase", "event_type": "speech"}

        speaker = meta.get("speaker") or "Unknown"
        target_phrase = meta.get("target_phrase") or "the target phrase"
        event_type = meta.get("event_type") or "speech"

        # Step 2: analyze linguistic patterns via web search
        analysis_resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{
                "role": "user",
                "content": ANALYSIS_PROMPT.format(
                    event_type=event_type,
                    speaker=speaker,
                    target_phrase=target_phrase,
                    date=replay_timestamp.strftime("%Y-%m-%d"),
                ),
            }],
        )

        all_text = "\n".join(
            b.text for b in analysis_resp.content if hasattr(b, "text")
        )
        analysis = extract_json(all_text)

        past_history = [p for p in market.price_history if p.timestamp <= replay_timestamp]

        usage_lines = "\n".join(f"- {c}" for c in analysis.get("usage_contexts", []))
        example_lines = "\n".join(f"- {e}" for e in analysis.get("recent_examples", []))
        factor_lines = "\n".join(f"- {f}" for f in analysis.get("key_factors", []))

        return AdapterContext(
            market_id=market.market_id,
            market_question=market.question,
            market_type="speech",
            current_probability=market.yes_price,
            price_history=past_history,
            context_documents=[
                f"TARGET PHRASE: '{target_phrase}'",
                f"SPEAKER: {speaker}",
                f"EVENT TYPE: {event_type}",
                f"HISTORICAL USAGE FREQUENCY: {analysis.get('historical_frequency', 'Unknown')}",
                f"TYPICAL USAGE CONTEXTS:\n{usage_lines}" if usage_lines else "TYPICAL USAGE CONTEXTS:\nNone found",
                f"CURRENT EVENT RELEVANCE:\n{analysis.get('current_relevance', 'Not determined.')}",
                f"RECENT EXAMPLES:\n{example_lines}" if example_lines else "RECENT EXAMPLES:\nNone found",
                f"ADAPTER BASE RATE ESTIMATE: {analysis.get('base_rate_estimate', 'N/A')}",
                f"KEY FACTORS:\n{factor_lines}" if factor_lines else "KEY FACTORS:\nNone identified",
            ],
            metadata={
                "speaker": speaker,
                "target_phrase": target_phrase,
                "event_type": event_type,
                "analysis": analysis,
            },
            replay_timestamp=replay_timestamp,
            resolution=market.resolution,
        )
