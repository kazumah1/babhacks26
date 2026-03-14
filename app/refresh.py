"""
refresh.py — one refresh cycle for all markets.

Called by main.py on first run and by the dashboard auto-refresh timer.
For each market:
  - Fetches the current live price from Polymarket
  - Checks open positions against exit conditions
  - Re-asks agents to enter if they have no open position
Updates data/positions.json in place.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
import json

from pipeline.polymarket_client import fetch_current_price
from pipeline import CONTEXT_CACHE_DIR, _load_context_cache
from engine import AGENTS
from engine.position_ledger import (
    load_positions, save_positions,
    get_position, open_position, close_position,
    mark_to_market, check_exit,
)

MARKET_SLUGS = [
    # Long-horizon — 35–55% odds, genuine uncertainty
    "will-the-democratic-party-control-the-senate-after-the-2026-midterm-elections",
    "will-the-republicans-win-the-2028-us-presidential-election",
    "netanyahu-out-before-2027-684",
    "russia-x-ukraine-ceasefire-before-2027",
    "will-jd-vance-win-the-2028-republican-presidential-nomination",
    # Speech — will person say/post X
    "will-jensen-huang-say-anthropic-at-the-nvidia-gtc-keynote",
    "elon-musk-of-tweets-march-13-march-20-40-59",
    "donald-trump-of-truth-social-posts-march-10-march-17-200plus",
]


def _exit_condition_dict(signal) -> dict:
    ec = signal.exit_condition
    return {
        "trigger": ec.trigger,
        "price_target": ec.price_target,
        "time_limit": ec.time_limit.isoformat() if ec.time_limit else None,
        "stop_loss": ec.stop_loss,
    }


def _refresh_market(slug: str, positions: dict) -> None:
    now = datetime.now()

    # Get live price — fall back to cached price if API fails
    current_price = fetch_current_price(slug)
    if current_price is None:
        # Try to get last known price from any existing position
        for agent_positions in positions.values():
            pos = agent_positions.get(slug)
            if pos and pos.get("current_price"):
                current_price = pos["current_price"]
                break
        if current_price is None:
            print(f"  [{slug[:40]}] could not fetch price, skipping")
            return

    print(f"  [{slug[:40]}] price={current_price:.1%}")

    # Load cached adapter context (has research briefing, market question, etc.)
    context_path = CONTEXT_CACHE_DIR / f"{slug}_context.json"
    if not context_path.exists():
        print(f"  [{slug[:40]}] no context cache, skipping")
        return
    context = _load_context_cache(context_path)
    # Update context with the live price so agents see current odds
    context.current_probability = current_price

    def _handle_agent(agent):
        agent_id = agent.agent_id
        pos = get_position(positions, agent_id, slug)

        if pos and pos["status"] == "open":
            # Check if exit condition triggers at new price
            exit_reason = check_exit(pos, current_price, now)
            if exit_reason:
                close_position(positions, agent_id, slug, current_price, exit_reason)
                print(f"    {agent_id}: CLOSED ({exit_reason}) @ {current_price:.1%}")
            else:
                mark_to_market(positions, agent_id, slug, current_price)
        elif pos is None or pos["status"] in ("closed", "none"):
            # No open position — ask agent if they want to enter
            if agent_id == "market_baseline":
                return  # baseline never enters
            try:
                signal = agent.trade(context)
                if signal.direction != "PASS" and signal.allocation > 0:
                    open_position(
                        positions, agent_id, slug,
                        direction=signal.direction,
                        allocation=signal.allocation,
                        entry_price=current_price,
                        exit_condition=_exit_condition_dict(signal),
                    )
                    print(f"    {agent_id}: ENTERED {signal.direction} ${signal.allocation:.0f} @ {current_price:.1%}")
                else:
                    positions.setdefault(agent_id, {})[slug] = {
                        "status": "none", "direction": "PASS",
                        "allocation": 0, "entry_price": None,
                        "entry_time": None, "exit_price": None,
                        "exit_time": None, "exit_reason": None,
                        "pnl_dollars": 0.0, "current_price": current_price,
                        "exit_condition": {},
                    }
            except Exception as e:
                print(f"    {agent_id}: failed — {e}")

    # Run all agents for this market in parallel
    with ThreadPoolExecutor(max_workers=len(AGENTS)) as ex:
        list(ex.map(_handle_agent, AGENTS))


def run_refresh() -> None:
    """Run one full refresh cycle across all markets. Updates positions.json."""
    positions = load_positions()
    print(f"\n[refresh] {datetime.now().strftime('%H:%M:%S')} — {len(MARKET_SLUGS)} markets\n")

    with ThreadPoolExecutor(max_workers=len(MARKET_SLUGS)) as executor:
        futures = {executor.submit(_refresh_market, slug, positions): slug
                   for slug in MARKET_SLUGS}
        for future in as_completed(futures):
            slug = futures[future]
            try:
                future.result()
            except Exception as e:
                print(f"  [{slug}] ERROR: {e}")

    save_positions(positions)
    print(f"\n[refresh] done — positions saved to data/positions.json")
