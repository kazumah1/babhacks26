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
    replay_timestamp: datetime,
) -> tuple[AdapterContext, MarketSnapshot]:
    """
    Fetches market data for `slug`, classifies the market type,
    runs the appropriate adapter, and returns a fully populated
    AdapterContext alongside the raw MarketSnapshot.

    `replay_timestamp` is the point in time the agent will reason from.
    Price history in the returned AdapterContext is filtered to
    replay_timestamp and earlier — future prices are not leaked.
    """
    market = fetch_market(slug)
    classification = classify_market(market.question)
    market_type = classification.get("market_type", "long_horizon")
    adapter = _ADAPTERS.get(market_type, _ADAPTERS["long_horizon"])
    context = adapter.build_context(market, replay_timestamp)
    return context, market
