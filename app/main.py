import json
from datetime import datetime, timedelta
from pathlib import Path

from pipeline import build_context
from engine import run_evaluation

# Slugs that are pre-fetched by pipeline/scripts/prefetch_markets.py
MARKET_SLUGS = [
    # Long-horizon — policy, geopolitics, macro
    "will-metamask-launch-a-token-by-june-30",
    "will-the-republican-party-hold-57-or-more-senate-seats-after-the-2026-midterm-elections",
    "will-apple-be-the-largest-company-in-the-world-by-market-cap-on-december-31-291",
    "will-russia-enter-druzkhivka-by-june-30-933-897",
    "will-juan-carlos-pinzn-win-the-1st-round-of-the-2026-colombian-presidential-election",
    # Speech — will person say/post X
    "will-jensen-huang-say-anthropic-at-the-nvidia-gtc-keynote",
    "elon-musk-of-tweets-march-13-march-20-40-59",
    "donald-trump-of-truth-social-posts-march-10-march-17-200plus",
]

# Agents reason from the current market price
LOOKBACK_DAYS = 0


def main():
    all_results = []
    Path("data").mkdir(exist_ok=True)

    for slug in MARKET_SLUGS:
        print(f"\nProcessing: {slug}")
        try:
            replay_ts = datetime.now() - timedelta(days=LOOKBACK_DAYS)
            context, market = build_context(slug, replay_ts)
            print(f"  Market type: {context.market_type}")
            print(f"  Question: {context.market_question[:60]}")

            results = run_evaluation(context, market)
            for r in results:
                print(f"  {r.agent_id}: {r.estimated_probability:.1%} | PnL: {r.simulated_pnl:+.4f}")
                all_results.append(vars(r))

        except Exception as e:
            print(f"  Failed: {e}")
            continue

    with open("data/results.json", "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\nResults written to data/results.json")
    print("Run: streamlit run app/dashboard.py")


if __name__ == "__main__":
    main()
