"""
prefetch_markets.py — run this before the demo to cache all market data.

Usage:
    python3 -m pipeline.scripts.prefetch_markets

Writes JSON to data/cache/<slug>.json. The fetch_market() function will use
these cached files and skip any live API calls during the presentation.
"""

from pipeline.polymarket_client import fetch_market

# ── Long-horizon markets ─────────────────────────────────────────────────────
# Active markets fitting the long-horizon adapter: policy, geopolitics, macro
LONG_HORIZON_SLUGS = [
    "will-the-democratic-party-control-the-senate-after-the-2026-midterm-elections",
    "will-the-republicans-win-the-2028-us-presidential-election",
    "netanyahu-out-before-2027-684",
    "russia-x-ukraine-ceasefire-before-2027",
    "will-jd-vance-win-the-2028-republican-presidential-nomination",
    "will-the-iranian-regime-fall-by-the-end-of-2026",
    "us-x-iran-ceasefire-by-june-30-752",
]

# ── Speech markets ────────────────────────────────────────────────────────────
# Active markets fitting the speech adapter: will person say/post X
SPEECH_SLUGS = [
    "will-jensen-huang-say-anthropic-at-the-nvidia-gtc-keynote",
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
