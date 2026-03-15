import json
import os
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

from shared.types import AdapterContext, TradingSignal, EntryCondition, ExitCondition
from engine.agents.base_agent import BaseAgent

AGENT_PROMPT = """You are a Polymarket trading agent. Output valid JSON only, no preamble.

Market Question: {question}
Market Type: {market_type}
Current Market Price (YES): {probability:.1%}
Analysis Date: {date}
Days to Resolution: {days}

--- LIVE RESEARCH (your own web search results) ---
{context}
--- END RESEARCH ---

You have a $1,000 total budget spread across all markets you are evaluating today.
The market price above is the current price — you are buying YES or NO shares at that price.
Rules:
- Allocate $0–$200 per market (stay diversified).
- PASS (allocation = 0) if you have no edge or conviction.
- Your total allocations across all markets must not exceed $1,000.

1. Decide YES, NO, or PASS based on your read of the market.
2. Choose how many dollars to allocate (0 if PASS).
3. Specify entry: immediate, or wait for a price threshold.
4. Specify exit: price target, time limit, stop loss, or hold to resolution.
5. Rationale: 3-5 sentences citing specifics from the research above.

Respond ONLY with:
{{
  "direction": "YES"|"NO"|"PASS",
  "allocation": float,
  "confidence": float,
  "entry_condition": {{"trigger": "immediate"|"price_threshold"|"time_threshold", "threshold": float|null, "rationale": string}},
  "exit_condition": {{"trigger": "price_target"|"time_limit"|"stop_loss"|"to_resolution", "price_target": float|null, "time_limit": "ISO string"|null, "stop_loss": float|null, "rationale": string}},
  "hold_horizon": "immediate"|"short"|"long"|"to_resolution",
  "rationale": string
}}"""


def _tavily_search(query: str, max_results: int = 5) -> str:
    """Run a Tavily search and return formatted snippets for the agent prompt."""
    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
        resp = client.search(query=query, max_results=max_results, search_depth="basic")
        snippets = []
        for r in resp.get("results", []):
            title = r.get("title", "")
            content = r.get("content", "")
            url = r.get("url", "")
            snippets.append(f"[{title}] {content}\nSource: {url}")
        return "\n\n".join(snippets) if snippets else "No results found."
    except Exception as e:
        return f"Search unavailable: {e}"


class LLMAgent(BaseAgent):
    def __init__(self, agent_id: str, model: str, provider: str = "anthropic"):
        self.agent_id = agent_id
        self.model = model
        self.provider = provider

    def trade(self, context: AdapterContext) -> TradingSignal:
        days = context.metadata.get("days_to_resolution", 30)

        # Each agent does its own Tavily search — produces unique context per model
        search_query = f"{context.market_question} prediction market analysis {datetime.now().year}"
        live_research = _tavily_search(search_query)

        prompt = AGENT_PROMPT.format(
            question=context.market_question,
            market_type=context.market_type,
            probability=context.current_probability,
            date=context.replay_timestamp.strftime("%Y-%m-%d"),
            days=days,
            context=live_research,
        )

        if self.provider == "anthropic":
            import anthropic
            client = anthropic.Anthropic()
            resp = client.messages.create(
                model=self.model, max_tokens=1024,
                messages=[{"role": "user", "content": prompt}]
            )
            raw = resp.content[0].text.strip()
        elif self.provider == "openrouter":
            import openai, os
            client = openai.OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=os.environ["OPENROUTER_API_KEY"],
            )
            resp = client.chat.completions.create(
                model=self.model, max_tokens=1024,
                messages=[{"role": "user", "content": prompt}]
            )
            raw = resp.choices[0].message.content.strip()
        else:
            import openai
            client = openai.OpenAI()
            resp = client.chat.completions.create(
                model=self.model, max_tokens=1024,
                messages=[{"role": "user", "content": prompt}]
            )
            raw = resp.choices[0].message.content.strip()

        clean = raw.replace("```json", "").replace("```", "").strip()
        d = json.loads(clean)

        # Normalize confidence if returned as 0-100
        if d.get("confidence", 0) > 1:
            d["confidence"] = d["confidence"] / 100.0

        # Clamp allocation to [0, 200], default 100 if missing
        allocation = float(d.get("allocation", 100.0))
        if d.get("direction", "PASS").upper() == "PASS":
            allocation = 0.0
        allocation = max(0.0, min(200.0, allocation))

        def parse_time_limit(val):
            if val is None:
                return None
            try:
                return datetime.fromisoformat(val)
            except (ValueError, TypeError):
                return None

        return TradingSignal(
            agent_id=self.agent_id,
            market_id=context.market_id,
            estimated_probability=context.current_probability,  # accept market price
            direction=d.get("direction", "PASS"),
            confidence=d.get("confidence", 0.5),
            allocation=allocation,
            entry_condition=EntryCondition(**d["entry_condition"]),
            exit_condition=ExitCondition(
                trigger=d["exit_condition"]["trigger"],
                price_target=d["exit_condition"].get("price_target"),
                time_limit=parse_time_limit(d["exit_condition"].get("time_limit")),
                stop_loss=d["exit_condition"].get("stop_loss"),
                rationale=d["exit_condition"]["rationale"]
            ),
            hold_horizon=d["hold_horizon"],
            rationale=d["rationale"],
            raw_response=raw
        )
