"""
position_ledger.py — persistent position state across refresh cycles.

Manages data/positions.json which tracks each agent's open/closed positions
per market. On each refresh cycle, open positions are checked against the
new market price and may be exited; agents without a position are re-asked
whether they want to enter.

Schema of data/positions.json:
{
  "claude-sonnet": {
    "will-metamask-launch-a-token-by-june-30": {
      "status": "open" | "closed" | "none",
      "direction": "YES" | "NO" | "PASS",
      "allocation": 150.0,
      "entry_price": 0.12,
      "entry_time": "2026-03-14T10:00:00",
      "exit_price": null,
      "exit_time": null,
      "exit_reason": null,
      "pnl_dollars": 0.0,
      "current_price": 0.14,
      "exit_condition": {
        "trigger": "price_target" | "time_limit" | "stop_loss" | "to_resolution",
        "price_target": float | null,
        "time_limit": "ISO string" | null,
        "stop_loss": float | null
      }
    }
  }
}
"""

import json
from datetime import datetime
from pathlib import Path

LEDGER_PATH = Path("data/positions.json")


def load_positions() -> dict:
    if LEDGER_PATH.exists():
        return json.loads(LEDGER_PATH.read_text())
    return {}


def save_positions(positions: dict) -> None:
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    LEDGER_PATH.write_text(json.dumps(positions, indent=2, default=str))


def get_position(positions: dict, agent_id: str, slug: str) -> dict | None:
    return positions.get(agent_id, {}).get(slug)


def open_position(positions: dict, agent_id: str, slug: str,
                  direction: str, allocation: float, entry_price: float,
                  exit_condition: dict) -> None:
    positions.setdefault(agent_id, {})[slug] = {
        "status": "open",
        "direction": direction,
        "allocation": allocation,
        "entry_price": entry_price,
        "entry_time": datetime.now().isoformat(),
        "exit_price": None,
        "exit_time": None,
        "exit_reason": None,
        "pnl_dollars": 0.0,
        "current_price": entry_price,
        "exit_condition": exit_condition,
    }


def close_position(positions: dict, agent_id: str, slug: str,
                   exit_price: float, exit_reason: str) -> None:
    pos = positions.get(agent_id, {}).get(slug)
    if pos is None:
        return
    pos["status"] = "closed"
    pos["exit_price"] = exit_price
    pos["exit_time"] = datetime.now().isoformat()
    pos["exit_reason"] = exit_reason
    pos["current_price"] = exit_price
    pos["pnl_dollars"] = _calc_pnl_dollars(pos, exit_price)


def mark_to_market(positions: dict, agent_id: str, slug: str, current_price: float) -> None:
    """Update unrealized PnL for an open position at the new market price."""
    pos = positions.get(agent_id, {}).get(slug)
    if pos and pos["status"] == "open":
        pos["current_price"] = current_price
        pos["pnl_dollars"] = _calc_pnl_dollars(pos, current_price)


def _calc_pnl_dollars(pos: dict, price: float) -> float:
    ep = pos.get("entry_price")
    alloc = float(pos.get("allocation", 0))
    direction = pos.get("direction", "PASS")
    if ep is None or direction == "PASS":
        return 0.0
    pnl_frac = (price - ep) if direction == "YES" else (ep - price)
    return round(alloc * pnl_frac, 4)


def check_exit(pos: dict, current_price: float, current_time: datetime) -> str | None:
    """
    Returns an exit_reason string if the position's exit condition is triggered
    at the given price/time, else None.
    """
    if pos["status"] != "open":
        return None
    direction = pos["direction"]
    entry_price = pos["entry_price"]
    ec = pos.get("exit_condition", {})
    trigger = ec.get("trigger")

    if trigger == "price_target" and ec.get("price_target") is not None:
        pt = float(ec["price_target"])
        if direction == "YES" and current_price >= pt:
            return "price_target"
        if direction == "NO" and current_price <= pt:
            return "price_target"

    if ec.get("stop_loss") is not None and entry_price is not None:
        sl = float(ec["stop_loss"])
        if direction == "YES" and current_price <= entry_price - sl:
            return "stop_loss"
        if direction == "NO" and current_price >= entry_price + sl:
            return "stop_loss"

    if trigger == "time_limit" and ec.get("time_limit") is not None:
        try:
            tl = datetime.fromisoformat(ec["time_limit"])
            if current_time >= tl:
                return "time_limit"
        except (ValueError, TypeError):
            pass

    return None
