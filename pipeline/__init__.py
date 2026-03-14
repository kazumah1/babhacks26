import json
from datetime import datetime
from pathlib import Path

from shared.types import AdapterContext, MarketSnapshot, PricePoint
from pipeline.polymarket_client import fetch_market
from pipeline.classifier import classify_market
from pipeline.adapters.long_horizon_adapter import LongHorizonAdapter
from pipeline.adapters.speech_adapter import SpeechAdapter

_ADAPTERS = {
    "long_horizon": LongHorizonAdapter(),
    "speech": SpeechAdapter(),
}

CONTEXT_CACHE_DIR = Path("data/cache")


def _save_context_cache(path: Path, context: AdapterContext) -> None:
    data = {
        "market_id": context.market_id,
        "market_question": context.market_question,
        "market_type": context.market_type,
        "current_probability": context.current_probability,
        "price_history": [
            {"t": p.timestamp.timestamp(), "p": p.probability}
            for p in context.price_history
        ],
        "context_documents": context.context_documents,
        "metadata": context.metadata,
        "replay_timestamp": context.replay_timestamp.isoformat(),
        "resolution": context.resolution,
    }
    path.write_text(json.dumps(data, indent=2, default=str))


def _load_context_cache(path: Path) -> AdapterContext:
    data = json.loads(path.read_text())
    return AdapterContext(
        market_id=data["market_id"],
        market_question=data["market_question"],
        market_type=data["market_type"],
        current_probability=float(data["current_probability"]),
        price_history=[
            PricePoint(
                timestamp=datetime.fromtimestamp(p["t"]),
                probability=float(p["p"]),
            )
            for p in data.get("price_history", [])
        ],
        context_documents=data["context_documents"],
        metadata=data["metadata"],
        replay_timestamp=datetime.fromisoformat(data["replay_timestamp"]),
        resolution=data.get("resolution"),
    )


def build_context(
    slug: str,
    replay_timestamp: datetime,
) -> tuple[AdapterContext, MarketSnapshot]:
    """
    Fetches market data for `slug`, classifies the market type,
    runs the appropriate adapter, and returns a fully populated
    AdapterContext alongside the raw MarketSnapshot.

    Adapter context (classifier + LLM research) is cached to
    data/cache/{slug}_context.json — delete to force a rebuild.
    """
    CONTEXT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = CONTEXT_CACHE_DIR / f"{slug}_context.json"

    market = fetch_market(slug)

    if cache_path.exists():
        context = _load_context_cache(cache_path)
        return context, market

    classification = classify_market(market.question)
    market_type = classification.get("market_type", "long_horizon")
    adapter = _ADAPTERS.get(market_type, _ADAPTERS["long_horizon"])
    context = adapter.build_context(market, replay_timestamp)

    _save_context_cache(cache_path, context)
    return context, market
