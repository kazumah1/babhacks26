# AGENTS.md — Workstream C: `app/`

## Your Job

You own the entrypoint and the dashboard. You wire Workstreams A and B together
in `main.py`, and you build the Streamlit leaderboard in `dashboard.py`.

You can build the entire dashboard before either of the other workstreams finishes
by using mock data. You do not need to understand how adapters or agents work
internally -- you only call their public interfaces.

## What You Build

```
app/
├── __init__.py
├── main.py          # Entrypoint: calls build_context() and run_evaluation(), writes results
├── dashboard.py     # Streamlit leaderboard UI, reads from data/results.json
└── tests/
    └── test_integration.py
```

## The Two Calls You Make

These are the only imports you need from the other workstreams:

```python
from pipeline import build_context     # Workstream A
from engine import run_evaluation      # Workstream B
```

Everything else comes from `shared.types` or the standard library.

## main.py

```python
# app/main.py

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from pipeline import build_context
from engine import run_evaluation

# Markets to evaluate — use real Polymarket slugs
# Workstream A will confirm which slugs are pre-fetched and working
MARKET_SLUGS = [
    "will-the-fed-cut-rates-in-june-2025",
    "will-apple-release-a-new-mac-pro-in-2025",
    "will-trump-say-tariff-in-his-next-press-conference",
    "will-powell-say-inflation-in-the-next-fomc-presser",
]

# How far back from the latest price point the agent reasons from
LOOKBACK_DAYS = 7

def main():
    all_results = []
    Path("data").mkdir(exist_ok=True)

    for slug in MARKET_SLUGS:
        print(f"\nProcessing: {slug}")
        try:
            # Workstream A: fetch and adapt
            replay_ts = datetime.now() - timedelta(days=LOOKBACK_DAYS)
            context, market = build_context(slug, replay_ts)
            print(f"  Market type: {context.market_type}")
            print(f"  Question: {context.market_question[:60]}")

            # Workstream B: evaluate agents
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
```

## dashboard.py

Build this against mock data first. Replace mock data with the real
`data/results.json` path once `main.py` is working end-to-end.

### Mock Data for Independent Development

```python
# Use this while waiting for Workstreams A and B to finish

MOCK_RESULTS = [
    {
        "agent_id": "claude-sonnet",
        "market_id": "market-001",
        "market_question": "Will the Fed cut rates in June 2025?",
        "market_type": "long_horizon",
        "brier_score": 0.18,
        "edge_vs_market": 0.12,
        "directional_correct": True,
        "simulated_pnl": 0.15,
        "resolution_pnl": 0.22,
        "exit_reason": "price_target",
        "estimated_probability": 0.65,
        "market_probability": 0.53,
        "final_resolution": True,
        "rationale": "Recent CPI data showed cooling inflation. The Fed has signaled openness to cuts. Labor market softening supports the case for easing."
    },
    {
        "agent_id": "gpt-4o",
        "market_id": "market-001",
        "market_question": "Will the Fed cut rates in June 2025?",
        "market_type": "long_horizon",
        "brier_score": 0.24,
        "edge_vs_market": 0.04,
        "directional_correct": True,
        "simulated_pnl": 0.08,
        "resolution_pnl": 0.12,
        "exit_reason": "to_resolution",
        "estimated_probability": 0.57,
        "market_probability": 0.53,
        "final_resolution": True,
        "rationale": "Inflation is moderating but the Fed may want more data before cutting."
    },
    {
        "agent_id": "market_baseline",
        "market_id": "market-001",
        "market_question": "Will the Fed cut rates in June 2025?",
        "market_type": "long_horizon",
        "brier_score": 0.22,
        "edge_vs_market": 0.0,
        "directional_correct": None,
        "simulated_pnl": 0.0,
        "resolution_pnl": 0.47,
        "exit_reason": "no_entry",
        "estimated_probability": 0.53,
        "market_probability": 0.53,
        "final_resolution": True,
        "rationale": "Market baseline: echoes current market probability."
    },
]
```

### Dashboard Structure

```python
# app/dashboard.py

import streamlit as st
import pandas as pd
import json
from pathlib import Path

st.set_page_config(
    page_title="MarketAdapters Arena",
    page_icon="🦞",
    layout="wide"
)

st.title("MarketAdapters Arena")
st.caption("Market-type-aware AI trading agent evaluation on Polymarket")

# Load results
RESULTS_PATH = Path("data/results.json")

if RESULTS_PATH.exists():
    with open(RESULTS_PATH) as f:
        results = json.load(f)
else:
    st.info("No results yet. Using mock data for development.")
    results = MOCK_RESULTS   # replace with import from above during dev

df = pd.DataFrame(results)

# --- Tabs ---
tab1, tab2, tab3 = st.tabs(["Leaderboard", "Market Breakdown", "By Type"])

with tab1:
    st.header("Agent Leaderboard")

    leaderboard = (
        df.groupby("agent_id")
        .agg(
            avg_brier=("brier_score", "mean"),
            avg_edge=("edge_vs_market", "mean"),
            total_pnl=("simulated_pnl", "sum"),
            resolution_pnl=("resolution_pnl", "sum"),
            directional_acc=("directional_correct", "mean"),
            markets=("market_id", "count")
        )
        .reset_index()
        .sort_values("avg_brier")
    )

    leaderboard.columns = [
        "Agent", "Avg Brier", "Avg Edge vs Market",
        "Simulated PnL", "Resolution PnL", "Directional Acc", "Markets"
    ]

    st.dataframe(
        leaderboard.style.format({
            "Avg Brier": "{:.4f}",
            "Avg Edge vs Market": "{:+.4f}",
            "Simulated PnL": "{:+.4f}",
            "Resolution PnL": "{:+.4f}",
            "Directional Acc": lambda x: f"{x:.1%}" if x is not None else "N/A",
        }),
        use_container_width=True
    )

    st.caption(
        "Brier Score: lower is better (0 = perfect). "
        "Edge vs Market: positive means agent was more accurate than market. "
        "Simulated PnL: uses agent's own entry/exit timing."
    )

with tab2:
    st.header("Per-Market Reasoning Traces")

    questions = df["market_question"].unique().tolist()
    selected = st.selectbox("Select market", questions)
    market_df = df[df["market_question"] == selected]

    # Show market context bar
    sample = market_df.iloc[0]
    col1, col2, col3 = st.columns(3)
    col1.metric("Market Type", sample["market_type"].replace("_", " ").title())
    col2.metric("Market Probability at Replay", f"{sample['market_probability']:.1%}")
    resolution = sample.get("final_resolution")
    col3.metric(
        "Resolution",
        "YES" if resolution is True else ("NO" if resolution is False else "Unresolved")
    )

    st.divider()

    for _, row in market_df.iterrows():
        direction_color = {"YES": "🟢", "NO": "🔴", "PASS": "⚪"}.get(
            "YES" if row["estimated_probability"] > row["market_probability"] else "NO", "⚪"
        )
        label = (
            f"{row['agent_id']} — "
            f"P(YES): {row['estimated_probability']:.1%} | "
            f"Edge: {row['edge_vs_market']:+.3f} | "
            f"PnL: {row['simulated_pnl']:+.4f} | "
            f"Exit: {row['exit_reason']}"
        )
        with st.expander(label):
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Agent P(YES)", f"{row['estimated_probability']:.1%}")
            c2.metric("Market P(YES)", f"{row['market_probability']:.1%}")
            c3.metric("Simulated PnL", f"{row['simulated_pnl']:+.4f}")
            c4.metric("Resolution PnL", f"{row['resolution_pnl']:+.4f}")

            if row.get("brier_score") is not None:
                st.metric("Brier Score", f"{row['brier_score']:.4f}")

            st.markdown("**Reasoning:**")
            st.write(row["rationale"])

with tab3:
    st.header("Performance by Market Type")

    type_df = (
        df.groupby(["agent_id", "market_type"])
        .agg(
            avg_brier=("brier_score", "mean"),
            total_pnl=("simulated_pnl", "sum"),
            count=("market_id", "count")
        )
        .reset_index()
    )
    st.dataframe(type_df, use_container_width=True)
```

## Rules

- Do not import from `pipeline/` internals or `engine/` internals.
  Only call `build_context()` and `run_evaluation()` from their `__init__.py`.
- Do not define dataclasses. Use `shared.types` or plain dicts for JSON serialization.
- Dashboard must work with mock data before A and B are ready.
- `main.py` must catch exceptions per market and continue -- one bad market
  should not abort the whole run.
- Serialize `AgentEvalResult` to JSON using `vars(r)` with `default=str`
  to handle datetime fields.

## Coordination Checklist

These are the things you need to confirm with the other workstreams
before the final integration run:

- [ ] Confirm list of pre-fetched market slugs with Workstream A
- [ ] Confirm `build_context()` signature and return type with Workstream A
- [ ] Confirm `run_evaluation()` signature and return type with Workstream B
- [ ] Confirm all `AgentEvalResult` field names match what the dashboard expects
- [ ] Do a dry run of `main.py` with at least one market from each adapter type
- [ ] Confirm `data/results.json` is populated before running `streamlit run`

## Running the Full Stack

```bash
# 1. Pre-fetch markets (Workstream A must do this first)
python pipeline/scripts/prefetch_markets.py

# 2. Run evaluation
python app/main.py

# 3. Launch dashboard
streamlit run app/dashboard.py
```
