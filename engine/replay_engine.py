from dataclasses import dataclass
from datetime import datetime
from shared1.types import AdapterContext, MarketSnapshot, PricePoint


@dataclass
class ReplayState:
    context: AdapterContext             # Contains only past price history
    market: MarketSnapshot              # Full market including metadata
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
