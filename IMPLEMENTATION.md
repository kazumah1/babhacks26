# IMPLEMENTATION.md — MarketAdapters Arena

## Overview

Three people work in parallel across three nested folders. The only shared
dependency is `shared/types.py`, which defines all dataclasses. Nobody touches
another workstream's folder directly.

```
Person A  →  pipeline/     (data fetching, adapters, classifier)
Person B  →  engine/       (agents, replay, position manager, metrics)
Person C  →  app/          (main entrypoint, Streamlit dashboard)
```

Integration happens only through two function signatures defined on day one.
Once those are agreed, all three can work independently until the final merge.

---

## Day One: Do These First (All Three People Together, ~30 min)

1. Copy `shared/types.py` from the root `AGENTS.md` into the repo. Do not modify it
   without coordinating with everyone.

2. Agree on the two integration signatures:

```python
# pipeline/__init__.py
def build_context(slug: str, replay_timestamp: datetime) -> tuple[AdapterContext, MarketSnapshot]:
    ...

# engine/__init__.py
def run_evaluation(context: AdapterContext, market: MarketSnapshot) -> list[AgentEvalResult]:
    ...
```

3. Set up `.env` with both API keys:
```
ANTHROPIC_API_KEY=...
OPENAI_API_KEY=...
```

4. Install deps:
```bash
pip install anthropic openai httpx streamlit pandas python-dotenv
```

5. Person A: find 3-5 real Polymarket slugs for each adapter type and share the list
   with Person C (who needs them for `main.py`). Use resolved markets where possible.

---

## Workstream A: `pipeline/`

### Step A1 — Polymarket Client

```python
# pipeline/polymarket_client.py

import json
import httpx
from datetime import datetime
from pathlib import Path
from shared.types import MarketSnapshot, PricePoint

CLOB_BASE = "https://clob.polymarket.com"
GAMMA_BASE = "https://gamma-api.polymarket.com"
CACHE_DIR = Path("data/cache")


def _deserialize_market(data: dict) -> MarketSnapshot:
    price_history = [
        PricePoint(
            timestamp=datetime.fromtimestamp(p["t"]),
            probability=float(p["p"])
        )
        for p in data.get("price_history", [])
    ]
    return MarketSnapshot(
        market_id=data["market_id"],
        question=data["question"],
        outcomes=data.get("outcomes", ["Yes", "No"]),
        yes_price=float(data["yes_price"]),
        price_history=price_history,
        end_date=datetime.fromisoformat(data["end_date"]) if data.get("end_date") else None,
        resolved=data.get("resolved", False),
        resolution=data.get("resolution")
    )


def fetch_market(slug: str) -> MarketSnapshot:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = CACHE_DIR / f"{slug}.json"

    if cache_path.exists():
        with open(cache_path) as f:
            return _deserialize_market(json.load(f))

    # Fetch from Gamma API
    resp = httpx.get(f"{GAMMA_BASE}/markets", params={"slug": slug}, timeout=15)
    resp.raise_for_status()
    markets = resp.json()
    if not markets:
        raise ValueError(f"Market not found: {slug}")
    m = markets[0]

    # Fetch price history from CLOB
    yes_token_id = m["tokens"][0]["token_id"]
    hist_resp = httpx.get(
        f"{CLOB_BASE}/prices-history",
        params={"token_id": yes_token_id, "interval": "1d", "fidelity": 60},
        timeout=15
    )
    history_raw = hist_resp.json().get("history", [])

    price_history = [
        PricePoint(
            timestamp=datetime.fromtimestamp(p["t"]),
            probability=float(p["p"])
        )
        for p in history_raw
    ]

    resolution = None
    if m.get("winner"):
        resolution = m["winner"] == "Yes"

    snapshot = MarketSnapshot(
        market_id=m["condition_id"],
        question=m["question"],
        outcomes=["Yes", "No"],
        yes_price=float(m["tokens"][0]["price"]),
        price_history=price_history,
        end_date=datetime.fromisoformat(m["end_date_iso"]) if m.get("end_date_iso") else None,
        resolved=m.get("closed", False),
        resolution=resolution
    )

    # Serialize to cache
    cache_data = {
        "market_id": snapshot.market_id,
        "question": snapshot.question,
        "outcomes": snapshot.outcomes,
        "yes_price": snapshot.yes_price,
        "price_history": [{"t": p.timestamp.timestamp(), "p": p.probability} for p in price_history],
        "end_date": snapshot.end_date.isoformat() if snapshot.end_date else None,
        "resolved": snapshot.resolved,
        "resolution": snapshot.resolution,
    }
    with open(cache_path, "w") as f:
        json.dump(cache_data, f, indent=2)

    return snapshot
```

### Step A2 — Classifier

```python
# pipeline/classifier.py

import anthropic
import json

client = anthropic.Anthropic()

CLASSIFIER_PROMPT = """
Classify this prediction market question into one of these categories:
- long_horizon: macro reasoning, policy, tech releases, multi-week events
- speech: predicts whether a word/phrase will appear in a speech, debate, or interview
- unknown: does not fit above

Respond ONLY with JSON: {{"market_type": "<category>", "confidence": <0.0-1.0>, "reasoning": "<one sentence>"}}

Market question: {question}
"""

def classify_market(question: str) -> dict:
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=256,
        messages=[{"role": "user", "content": CLASSIFIER_PROMPT.format(question=question)}]
    )
    raw = response.content[0].text.strip().replace("```json", "").replace("```", "")
    result = json.loads(raw)
    # Fall back to long_horizon if confidence is low or type is unknown
    if result.get("confidence", 0) < 0.6 or result.get("market_type") == "unknown":
        result["market_type"] = "long_horizon"
    return result
```

### Step A3 — Base Adapter

```python
# pipeline/adapters/base_adapter.py

from abc import ABC, abstractmethod
from datetime import datetime
from shared.types import AdapterContext, MarketSnapshot

class BaseAdapter(ABC):
    @abstractmethod
    def build_context(
        self,
        market: MarketSnapshot,
        replay_timestamp: datetime
    ) -> AdapterContext:
        ...
```

### Step A4 — Long-Horizon Adapter

```python
# pipeline/adapters/long_horizon_adapter.py

import anthropic
import json
from datetime import datetime
from shared.types import AdapterContext, MarketSnapshot
from pipeline.adapters.base_adapter import BaseAdapter

client = anthropic.Anthropic()

BRIEFING_PROMPT = """
Build a research briefing for this prediction market.

Market Question: {question}
Analysis Date: {date}
Current Market Probability: {probability:.1%}
Days to Resolution: {days}

Search for recent developments, base rates, expert views, and key uncertainties.

Return JSON only:
{{
  "summary": "<2-3 sentence overview>",
  "bull_case": "<key reasons YES is more likely>",
  "bear_case": "<key reasons NO is more likely>",
  "base_rate": "<historical frequency of similar events, or 'Not available'>",
  "key_dates": ["<date: event>"],
  "uncertainty_factors": ["<factor>"]
}}
"""

class LongHorizonAdapter(BaseAdapter):
    def build_context(self, market: MarketSnapshot, replay_timestamp: datetime) -> AdapterContext:
        days_to_resolution = (
            (market.end_date - replay_timestamp).days if market.end_date else 90
        )

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{
                "role": "user",
                "content": BRIEFING_PROMPT.format(
                    question=market.question,
                    date=replay_timestamp.strftime("%Y-%m-%d"),
                    probability=market.yes_price,
                    days=days_to_resolution
                )
            }]
        )

        briefing_text = next(
            (b.text for b in response.content if b.type == "text"), "{}"
        )
        try:
            briefing = json.loads(briefing_text.replace("```json", "").replace("```", "").strip())
        except json.JSONDecodeError:
            briefing = {"summary": briefing_text}

        past_history = [p for p in market.price_history if p.timestamp <= replay_timestamp]

        return AdapterContext(
            market_id=market.market_id,
            market_question=market.question,
            market_type="long_horizon",
            current_probability=market.yes_price,
            price_history=past_history,
            context_documents=[
                f"SITUATION SUMMARY:\n{briefing.get('summary', '')}",
                f"BULL CASE (YES more likely):\n{briefing.get('bull_case', '')}",
                f"BEAR CASE (NO more likely):\n{briefing.get('bear_case', '')}",
                f"HISTORICAL BASE RATE:\n{briefing.get('base_rate', 'Not available')}",
                "KEY UNCERTAINTY FACTORS:\n" + "\n".join(
                    f"- {f}" for f in briefing.get("uncertainty_factors", [])
                ),
            ],
            metadata={"days_to_resolution": days_to_resolution, "briefing": briefing},
            replay_timestamp=replay_timestamp,
            resolution=market.resolution
        )
```

### Step A5 — Speech Adapter

```python
# pipeline/adapters/speech_adapter.py

import anthropic
import json
from datetime import datetime
from shared.types import AdapterContext, MarketSnapshot
from pipeline.adapters.base_adapter import BaseAdapter

client = anthropic.Anthropic()

METADATA_PROMPT = """
Extract metadata from this prediction market question about speech content.
Return JSON only:
{{"speaker": "<name or null>", "target_phrase": "<word or phrase>", "event_type": "<speech|debate|interview|press_conference|other>"}}

Question: {question}
"""

ANALYSIS_PROMPT = """
Analyze a speaker's linguistic patterns to predict whether a specific word/phrase
will appear in an upcoming {event_type}.

Speaker: {speaker}
Target Phrase: {target_phrase}
Analysis Date: {date}

Search for recent transcripts of this speaker. Analyze:
1. How frequently they use this word/phrase
2. Contexts where they use it
3. Whether current events make it more or less likely

Return JSON only:
{{
  "historical_frequency": "<description>",
  "usage_contexts": ["<context>"],
  "current_relevance": "<explanation>",
  "recent_examples": ["<date: example>"],
  "base_rate_estimate": <float 0.0-1.0>,
  "key_factors": ["<factor>"]
}}
"""

class SpeechAdapter(BaseAdapter):
    def build_context(self, market: MarketSnapshot, replay_timestamp: datetime) -> AdapterContext:
        # Step 1: extract metadata
        meta_resp = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=256,
            messages=[{"role": "user", "content": METADATA_PROMPT.format(question=market.question)}]
        )
        try:
            meta = json.loads(meta_resp.content[0].text.strip().replace("```json","").replace("```",""))
        except json.JSONDecodeError:
            meta = {"speaker": "Unknown", "target_phrase": "the target phrase", "event_type": "speech"}

        # Step 2: analyze linguistic patterns
        analysis_resp = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{
                "role": "user",
                "content": ANALYSIS_PROMPT.format(
                    event_type=meta.get("event_type", "speech"),
                    speaker=meta.get("speaker") or "Unknown",
                    target_phrase=meta.get("target_phrase") or "the target phrase",
                    date=replay_timestamp.strftime("%Y-%m-%d")
                )
            }]
        )

        analysis_text = next(
            (b.text for b in analysis_resp.content if b.type == "text"), "{}"
        )
        try:
            analysis = json.loads(analysis_text.replace("```json","").replace("```","").strip())
        except json.JSONDecodeError:
            analysis = {}

        past_history = [p for p in market.price_history if p.timestamp <= replay_timestamp]

        return AdapterContext(
            market_id=market.market_id,
            market_question=market.question,
            market_type="speech",
            current_probability=market.yes_price,
            price_history=past_history,
            context_documents=[
                f"TARGET PHRASE: '{meta.get('target_phrase', '')}'",
                f"SPEAKER: {meta.get('speaker', 'Unknown')}",
                f"HISTORICAL USAGE FREQUENCY: {analysis.get('historical_frequency', 'Unknown')}",
                "TYPICAL USAGE CONTEXTS:\n" + "\n".join(
                    f"- {c}" for c in analysis.get("usage_contexts", [])
                ),
                f"CURRENT EVENT RELEVANCE:\n{analysis.get('current_relevance', '')}",
                "RECENT EXAMPLES:\n" + "\n".join(
                    f"- {e}" for e in analysis.get("recent_examples", [])
                ),
                f"ADAPTER BASE RATE ESTIMATE: {analysis.get('base_rate_estimate', 'N/A')}",
            ],
            metadata={"speaker": meta.get("speaker"), "target_phrase": meta.get("target_phrase"), "analysis": analysis},
            replay_timestamp=replay_timestamp,
            resolution=market.resolution
        )
```

### Step A6 — Public Interface + Prefetch Script

```python
# pipeline/__init__.py

from datetime import datetime
from shared.types import AdapterContext, MarketSnapshot
from pipeline.polymarket_client import fetch_market
from pipeline.classifier import classify_market
from pipeline.adapters.long_horizon_adapter import LongHorizonAdapter
from pipeline.adapters.speech_adapter import SpeechAdapter

_ADAPTERS = {
    "long_horizon": LongHorizonAdapter(),
    "speech": SpeechAdapter(),
}

def build_context(
    slug: str,
    replay_timestamp: datetime
) -> tuple[AdapterContext, MarketSnapshot]:
    market = fetch_market(slug)
    classification = classify_market(market.question)
    market_type = classification.get("market_type", "long_horizon")
    adapter = _ADAPTERS.get(market_type, _ADAPTERS["long_horizon"])
    context = adapter.build_context(market, replay_timestamp)
    return context, market
```

```python
# pipeline/scripts/prefetch_markets.py
# Run this before the demo to cache all markets

from pipeline.polymarket_client import fetch_market

SLUGS = [
    # Replace with real slugs from polymarket.com
    "will-the-fed-cut-rates-in-june-2025",
    "will-apple-release-a-new-mac-pro-in-2025",
    "will-trump-say-tariff-in-his-next-press-conference",
]

for slug in SLUGS:
    print(f"Fetching {slug}...")
    try:
        m = fetch_market(slug)
        print(f"  OK: {m.question[:60]} | {len(m.price_history)} price points")
    except Exception as e:
        print(f"  FAILED: {e}")
```

---

## Workstream B: `engine/`

### Step B1 — Replay Engine

```python
# engine/replay_engine.py

from dataclasses import dataclass
from datetime import datetime
from shared.types import AdapterContext, MarketSnapshot, PricePoint

@dataclass
class ReplayState:
    context: AdapterContext
    market: MarketSnapshot
    replay_timestamp: datetime
    probability_at_replay: float
    future_price_history: list[PricePoint]
    final_resolution: bool | None

def build_replay_state(context: AdapterContext, market: MarketSnapshot) -> ReplayState:
    replay_ts = context.replay_timestamp
    past = [p for p in market.price_history if p.timestamp <= replay_ts]
    future = [p for p in market.price_history if p.timestamp > replay_ts]

    if not past:
        raise ValueError("No price history at or before replay timestamp")

    probability_at_replay = past[-1].probability

    # Agent-facing context: past prices only, resolution hidden
    agent_context = AdapterContext(
        market_id=context.market_id,
        market_question=context.market_question,
        market_type=context.market_type,
        current_probability=probability_at_replay,
        price_history=past,
        context_documents=context.context_documents,
        metadata=context.metadata,
        replay_timestamp=replay_ts,
        resolution=None
    )

    return ReplayState(
        context=agent_context,
        market=market,
        replay_timestamp=replay_ts,
        probability_at_replay=probability_at_replay,
        future_price_history=future,
        final_resolution=market.resolution
    )
```

### Step B2 — Agents

```python
# engine/agents/base_agent.py
from abc import ABC, abstractmethod
from shared.types import AdapterContext, TradingSignal

class BaseAgent(ABC):
    agent_id: str

    @abstractmethod
    def trade(self, context: AdapterContext) -> TradingSignal:
        ...
```

```python
# engine/agents/baseline_agent.py
from datetime import datetime
from shared.types import AdapterContext, TradingSignal, EntryCondition, ExitCondition
from engine.agents.base_agent import BaseAgent

class MarketBaselineAgent(BaseAgent):
    agent_id = "market_baseline"

    def trade(self, context: AdapterContext) -> TradingSignal:
        return TradingSignal(
            agent_id=self.agent_id,
            market_id=context.market_id,
            estimated_probability=context.current_probability,
            direction="PASS",
            confidence=1.0,
            entry_condition=EntryCondition(trigger="immediate", threshold=None, rationale="Baseline"),
            exit_condition=ExitCondition(
                trigger="to_resolution", price_target=None,
                time_limit=None, stop_loss=None, rationale="Baseline"
            ),
            hold_horizon="to_resolution",
            rationale="Market baseline: echoes current market probability with no additional signal.",
            raw_response=""
        )
```

```python
# engine/agents/llm_agent.py
import json
from datetime import datetime
from shared.types import AdapterContext, TradingSignal, EntryCondition, ExitCondition
from engine.agents.base_agent import BaseAgent

AGENT_PROMPT = """You are a prediction market trading agent. Output valid JSON only, no preamble.

Market Question: {question}
Market Type: {market_type}
Current Market Probability (YES): {probability:.1%}
Analysis Date: {date}
Days to Resolution: {days}

--- CONTEXT ---
{context}
--- END CONTEXT ---

1. Estimate true probability of YES resolution.
2. Decide YES, NO, or PASS.
3. Specify entry: immediate, or wait for price threshold.
4. Specify exit: price target, time limit, stop loss, or hold to resolution.
5. Rationale: 3-5 sentences.

Respond ONLY with:
{{
  "estimated_probability": float,
  "direction": "YES"|"NO"|"PASS",
  "confidence": float,
  "entry_condition": {{"trigger": "immediate"|"price_threshold"|"time_threshold", "threshold": float|null, "rationale": string}},
  "exit_condition": {{"trigger": "price_target"|"time_limit"|"stop_loss"|"to_resolution", "price_target": float|null, "time_limit": "ISO string"|null, "stop_loss": float|null, "rationale": string}},
  "hold_horizon": "immediate"|"short"|"long"|"to_resolution",
  "rationale": string
}}"""

class LLMAgent(BaseAgent):
    def __init__(self, agent_id: str, model: str, provider: str = "anthropic"):
        self.agent_id = agent_id
        self.model = model
        self.provider = provider

    def trade(self, context: AdapterContext) -> TradingSignal:
        days = context.metadata.get("days_to_resolution", 30)
        prompt = AGENT_PROMPT.format(
            question=context.market_question,
            market_type=context.market_type,
            probability=context.current_probability,
            date=context.replay_timestamp.strftime("%Y-%m-%d"),
            days=days,
            context="\n\n---\n\n".join(context.context_documents)
        )

        if self.provider == "anthropic":
            import anthropic
            client = anthropic.Anthropic()
            resp = client.messages.create(
                model=self.model, max_tokens=1024,
                messages=[{"role": "user", "content": prompt}]
            )
            raw = resp.content[0].text.strip()
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
            estimated_probability=d["estimated_probability"],
            direction=d["direction"],
            confidence=d["confidence"],
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
```

### Step B3 — Position Manager

```python
# engine/position_manager.py

from datetime import datetime
from shared.types import TradingSignal, SimulatedPosition, PricePoint
from engine.replay_engine import ReplayState

def simulate_position(signal: TradingSignal, replay_state: ReplayState) -> SimulatedPosition:
    if signal.direction == "PASS":
        return SimulatedPosition(
            agent_id=signal.agent_id, market_id=signal.market_id,
            direction="PASS", entry_price=None, exit_price=None,
            entry_timestamp=None, exit_timestamp=None,
            exit_reason="no_entry", pnl=0.0, resolution_pnl=0.0
        )

    future = replay_state.future_price_history
    resolution = replay_state.final_resolution
    entry_cond = signal.entry_condition
    exit_cond = signal.exit_condition

    # Entry
    entry_price, entry_timestamp = None, None
    if entry_cond.trigger == "immediate":
        entry_price = replay_state.probability_at_replay
        entry_timestamp = replay_state.replay_timestamp
    elif entry_cond.trigger == "price_threshold" and entry_cond.threshold is not None:
        for p in future:
            if signal.direction == "YES" and p.probability <= entry_cond.threshold:
                entry_price, entry_timestamp = p.probability, p.timestamp
                break
            elif signal.direction == "NO" and p.probability >= entry_cond.threshold:
                entry_price, entry_timestamp = p.probability, p.timestamp
                break

    if entry_price is None:
        return SimulatedPosition(
            agent_id=signal.agent_id, market_id=signal.market_id,
            direction=signal.direction, entry_price=None, exit_price=None,
            entry_timestamp=None, exit_timestamp=None,
            exit_reason="no_entry", pnl=0.0, resolution_pnl=0.0
        )

    # Exit
    exit_price, exit_timestamp, exit_reason = None, None, "resolution"
    post_entry = [p for p in future if entry_timestamp and p.timestamp > entry_timestamp]

    for p in post_entry:
        hit_target = (
            exit_cond.trigger == "price_target" and exit_cond.price_target is not None and (
                (signal.direction == "YES" and p.probability >= exit_cond.price_target) or
                (signal.direction == "NO" and p.probability <= exit_cond.price_target)
            )
        )
        hit_stop = (
            exit_cond.stop_loss is not None and (
                (signal.direction == "YES" and p.probability <= entry_price - exit_cond.stop_loss) or
                (signal.direction == "NO" and p.probability >= entry_price + exit_cond.stop_loss)
            )
        )
        hit_time = (
            exit_cond.time_limit is not None and p.timestamp >= exit_cond.time_limit
        )

        if hit_target:
            exit_price, exit_timestamp, exit_reason = p.probability, p.timestamp, "price_target"
            break
        if hit_stop:
            exit_price, exit_timestamp, exit_reason = p.probability, p.timestamp, "stop_loss"
            break
        if hit_time:
            exit_price, exit_timestamp, exit_reason = p.probability, p.timestamp, "time_limit"
            break

    if exit_price is None:
        if resolution is not None:
            exit_price = 1.0 if resolution else 0.0
            exit_reason = "resolution"
        elif future:
            exit_price = future[-1].probability
            exit_reason = "last_known_price"

    def calc_pnl(ep, xp, direction):
        if ep is None or xp is None:
            return 0.0
        return round((xp - ep) if direction == "YES" else (ep - xp), 4)

    res_exit = (1.0 if resolution else 0.0) if resolution is not None else exit_price

    return SimulatedPosition(
        agent_id=signal.agent_id, market_id=signal.market_id,
        direction=signal.direction, entry_price=entry_price, exit_price=exit_price,
        entry_timestamp=entry_timestamp, exit_timestamp=exit_timestamp,
        exit_reason=exit_reason,
        pnl=calc_pnl(entry_price, exit_price, signal.direction),
        resolution_pnl=calc_pnl(entry_price, res_exit, signal.direction)
    )
```

### Step B4 — Metrics

```python
# engine/metrics.py

from shared.types import TradingSignal, SimulatedPosition, AgentEvalResult
from engine.replay_engine import ReplayState

def evaluate_agent(
    signal: TradingSignal,
    position: SimulatedPosition,
    replay_state: ReplayState
) -> AgentEvalResult:
    resolution = replay_state.final_resolution
    market_prob = replay_state.probability_at_replay

    brier = None
    if resolution is not None:
        brier = round((signal.estimated_probability - float(resolution)) ** 2, 6)

    directional_correct = None
    if replay_state.future_price_history and signal.direction != "PASS":
        final_price = replay_state.future_price_history[-1].probability
        market_moved_up = final_price > market_prob
        agent_said_yes = signal.direction == "YES"
        directional_correct = (market_moved_up == agent_said_yes)

    return AgentEvalResult(
        agent_id=signal.agent_id,
        market_id=signal.market_id,
        market_question=replay_state.market.question,
        market_type=replay_state.context.market_type,
        brier_score=brier,
        edge_vs_market=round(signal.estimated_probability - market_prob, 4),
        directional_correct=directional_correct,
        simulated_pnl=position.pnl,
        resolution_pnl=position.resolution_pnl,
        exit_reason=position.exit_reason,
        estimated_probability=signal.estimated_probability,
        market_probability=market_prob,
        final_resolution=resolution,
        rationale=signal.rationale
    )
```

### Step B5 — Public Interface

```python
# engine/__init__.py

from shared.types import AdapterContext, MarketSnapshot, AgentEvalResult
from engine.replay_engine import build_replay_state
from engine.agents.llm_agent import LLMAgent
from engine.agents.baseline_agent import MarketBaselineAgent
from engine.position_manager import simulate_position
from engine.metrics import evaluate_agent

AGENTS = [
    LLMAgent("claude-sonnet", "claude-sonnet-4-20250514", provider="anthropic"),
    LLMAgent("gpt-4o", "gpt-4o", provider="openai"),
    MarketBaselineAgent(),
]

def run_evaluation(
    context: AdapterContext,
    market: MarketSnapshot,
) -> list[AgentEvalResult]:
    replay_state = build_replay_state(context, market)
    results = []
    for agent in AGENTS:
        try:
            signal = agent.trade(replay_state.context)
            position = simulate_position(signal, replay_state)
            result = evaluate_agent(signal, position, replay_state)
            results.append(result)
        except Exception as e:
            print(f"  Agent {agent.agent_id} failed: {e}")
    return results
```

---

## Workstream C: `app/`

See `app/AGENTS.md` for the full dashboard code.
`main.py` and `dashboard.py` are fully specified there.

---

## Final Integration Checklist

Run through this in order when merging all three workstreams:

- [ ] `python pipeline/scripts/prefetch_markets.py` completes with no errors
- [ ] `from pipeline import build_context` works in a Python shell
- [ ] `from engine import run_evaluation` works in a Python shell
- [ ] `python app/main.py` runs end-to-end on at least one market per adapter type
- [ ] `data/results.json` contains at least one result per agent per market
- [ ] `streamlit run app/dashboard.py` loads without errors
- [ ] Leaderboard shows all three agents with correct metrics
- [ ] At least one reasoning trace is visible in the Market Breakdown tab
- [ ] One resolved market shows correct Brier score (not None)

## Demo Script

1. Show the classifier routing one long-horizon and one speech market to different adapters
2. Show the adapter context output for each type side by side
3. Open the dashboard leaderboard -- all three agents, sortable by Brier score
4. Click into one market and show reasoning traces side by side
5. Highlight one case where an agent's estimated probability diverged significantly
   from the market and point to what it saw that the market had not priced in
6. Show the early exit efficiency column -- did taking profit early beat holding to resolution?

Keep the entire demo on pre-cached data. No live API calls during the presentation.
