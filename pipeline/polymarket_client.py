import json
import httpx
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

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
        resolution=data.get("resolution"),
    )


def fetch_market(slug: str) -> MarketSnapshot:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = CACHE_DIR / f"{slug}.json"

    if cache_path.exists():
        with open(cache_path) as f:
            return _deserialize_market(json.load(f))

    # Fetch market metadata from Gamma API
    resp = httpx.get(f"{GAMMA_BASE}/markets", params={"slug": slug}, timeout=15)
    resp.raise_for_status()
    markets = resp.json()
    if not markets:
        raise ValueError(f"Market not found: {slug}")
    m = markets[0]

    # Parse outcome prices (JSON string "[\"0.55\", \"0.45\"]")
    outcome_prices_raw = m.get("outcomePrices", "[\"0.5\", \"0.5\"]")
    outcome_prices = json.loads(outcome_prices_raw) if isinstance(outcome_prices_raw, str) else outcome_prices_raw
    yes_price = float(outcome_prices[0]) if outcome_prices else 0.5

    # Parse outcomes (JSON string "[\"Yes\", \"No\"]")
    outcomes_raw = m.get("outcomes", "[\"Yes\", \"No\"]")
    outcomes = json.loads(outcomes_raw) if isinstance(outcomes_raw, str) else outcomes_raw

    # Parse clobTokenIds (JSON string) — first token = YES
    clob_ids_raw = m.get("clobTokenIds", "[]")
    clob_ids = json.loads(clob_ids_raw) if isinstance(clob_ids_raw, str) else clob_ids_raw
    yes_token_id = clob_ids[0] if clob_ids else None

    # Fetch price history from CLOB if we have a token id
    # The CLOB API uses 'market' (asset id) not 'token_id' as the param name
    price_history: list[PricePoint] = []
    if yes_token_id:
        hist_resp = httpx.get(
            f"{CLOB_BASE}/prices-history",
            params={"market": yes_token_id, "interval": "max", "fidelity": 60, "startTs": 1746057600},
            timeout=15,
        )
        if hist_resp.is_success:
            price_history = [
                PricePoint(
                    timestamp=datetime.fromtimestamp(p["t"]),
                    probability=float(p["p"])
                )
                for p in hist_resp.json().get("history", [])
            ]

    # Resolution
    resolution = None
    winner = m.get("winner") or m.get("winnerOutcome")
    if winner:
        resolution = winner.lower() in ("yes", "y", "true", "1")

    # End date — try multiple field names
    end_date = None
    for field in ("endDate", "end_date_iso", "endDateIso", "end_date"):
        val = m.get(field)
        if val:
            try:
                end_date = datetime.fromisoformat(val.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass
            break

    snapshot = MarketSnapshot(
        market_id=m.get("conditionId") or m.get("condition_id") or m.get("id", slug),
        question=m["question"],
        outcomes=outcomes,
        yes_price=yes_price,
        price_history=price_history,
        end_date=end_date,
        resolved=m.get("closed", False),
        resolution=resolution,
    )

    # Write to cache
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


def fetch_current_price(slug: str) -> float | None:
    """Fetch only the current YES price for a slug — no cache, no price history."""
    try:
        resp = httpx.get(f"{GAMMA_BASE}/markets", params={"slug": slug}, timeout=10)
        resp.raise_for_status()
        markets = resp.json()
        if not markets:
            return None
        m = markets[0]
        outcome_prices_raw = m.get("outcomePrices", "[\"0.5\", \"0.5\"]")
        outcome_prices = json.loads(outcome_prices_raw) if isinstance(outcome_prices_raw, str) else outcome_prices_raw
        return float(outcome_prices[0]) if outcome_prices else None
    except Exception:
        return None


if __name__ == "__main__":
    import sys
    slug = sys.argv[1] if len(sys.argv) > 1 else "will-the-fed-cut-rates-in-june-2025"
    m = fetch_market(slug)
    print(f"question: {m.question}")
    print(f"yes_price: {m.yes_price}")
    print(f"price_history points: {len(m.price_history)}")
    print(f"resolved: {m.resolved}, resolution: {m.resolution}")
