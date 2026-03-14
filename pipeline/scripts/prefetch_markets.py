"""
prefetch_markets.py — run this before the demo to cache all market data.

Usage:
    python3 -m pipeline.scripts.prefetch_markets

Writes JSON to data/cache/<slug>.json. The fetch_market() function will use
these cached files and skip any live API calls during the presentation.
"""

from pipeline.polymarket_client import fetch_market

# ── Long-horizon markets ─────────────────────────────────────────────────────
# Macro events, policy decisions, product launches — multi-week reasoning
LONG_HORIZON_SLUGS = [
    "will-metamask-launch-a-token-by-june-30",
    "gustavo-petro-out-as-leader-of-colombia-by-june-30",
    "will-fannie-maes-market-cap-be-between-300b-and-350b-at-market-close-on-ipo-day",
    "will-the-republican-party-hold-57-or-more-senate-seats-after-the-2026-midterm-elections",
    "will-lebron-james-announce-a-presidential-run-before-2027",
]

# ── Speech markets ────────────────────────────────────────────────────────────
# Predicts whether a specific word/phrase will appear in a speech or event
SPEECH_SLUGS = [
    "will-president-biden-say-folks-in-his-first-joint-address",
    "will-president-biden-mention-coronavirus-3-or-more-times-in-his-first-joint-address",
    "will-president-biden-mention-donald-trump-in-his-first-joint-address",
    "will-elon-musk-mention-doge-in-his-snl-appearance",
    "white-house-of-tweets-march-17-march-24-2026-100-119",
]

ALL_SLUGS = [
    ("long_horizon", s) for s in LONG_HORIZON_SLUGS
] + [
    ("speech", s) for s in SPEECH_SLUGS
]


def prefetch_all() -> None:
    ok, failed = 0, 0
    for adapter_type, slug in ALL_SLUGS:
        print(f"[{adapter_type}] {slug} ...", end=" ", flush=True)
        try:
            m = fetch_market(slug)
            pts = len(m.price_history)
            resolved = f"resolved={m.resolution}" if m.resolved else "open"
            print(f"OK  | {pts} price pts | {resolved} | {m.question[:55]}")
            ok += 1
        except Exception as e:
            print(f"FAIL | {e}")
            failed += 1

    print(f"\nDone: {ok} succeeded, {failed} failed.")


if __name__ == "__main__":
    prefetch_all()
