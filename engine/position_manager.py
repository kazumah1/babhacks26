from shared1.types import TradingSignal, SimulatedPosition
from engine.replay_engine import ReplayState


def simulate_position(signal: TradingSignal, replay_state: ReplayState) -> SimulatedPosition:
    if signal.direction == "PASS":
        return SimulatedPosition(
            agent_id=signal.agent_id, market_id=signal.market_id,
            direction="PASS", entry_price=None, exit_price=None,
            entry_timestamp=None, exit_timestamp=None,
            exit_reason="no_entry", pnl=0.0, resolution_pnl=0.0
        )

    future = replay_state.future_price_history
    resolution = replay_state.final_resolution
    entry_cond = signal.entry_condition
    exit_cond = signal.exit_condition

    # Entry
    entry_price, entry_timestamp = None, None
    if entry_cond.trigger == "immediate":
        entry_price = replay_state.probability_at_replay
        entry_timestamp = replay_state.replay_timestamp
    elif entry_cond.trigger == "price_threshold" and entry_cond.threshold is not None:
        for p in future:
            if signal.direction == "YES" and p.probability <= entry_cond.threshold:
                entry_price, entry_timestamp = p.probability, p.timestamp
                break
            elif signal.direction == "NO" and p.probability >= entry_cond.threshold:
                entry_price, entry_timestamp = p.probability, p.timestamp
                break

    if entry_price is None:
        return SimulatedPosition(
            agent_id=signal.agent_id, market_id=signal.market_id,
            direction=signal.direction, entry_price=None, exit_price=None,
            entry_timestamp=None, exit_timestamp=None,
            exit_reason="no_entry", pnl=0.0, resolution_pnl=0.0
        )

    # Exit
    exit_price, exit_timestamp, exit_reason = None, None, "resolution"
    post_entry = [p for p in future if entry_timestamp and p.timestamp > entry_timestamp]

    for p in post_entry:
        hit_target = (
            exit_cond.trigger == "price_target" and exit_cond.price_target is not None and (
                (signal.direction == "YES" and p.probability >= exit_cond.price_target) or
                (signal.direction == "NO" and p.probability <= exit_cond.price_target)
            )
        )
        hit_stop = (
            exit_cond.stop_loss is not None and (
                (signal.direction == "YES" and p.probability <= entry_price - exit_cond.stop_loss) or
                (signal.direction == "NO" and p.probability >= entry_price + exit_cond.stop_loss)
            )
        )
        hit_time = (
            exit_cond.time_limit is not None and p.timestamp >= exit_cond.time_limit
        )

        if hit_target:
            exit_price, exit_timestamp, exit_reason = p.probability, p.timestamp, "price_target"
            break
        if hit_stop:
            exit_price, exit_timestamp, exit_reason = p.probability, p.timestamp, "stop_loss"
            break
        if hit_time:
            exit_price, exit_timestamp, exit_reason = p.probability, p.timestamp, "time_limit"
            break

    if exit_price is None:
        if resolution is not None:
            exit_price = 1.0 if resolution else 0.0
            exit_reason = "resolution"
        elif future:
            exit_price = future[-1].probability
            exit_reason = "last_known_price"

    def calc_pnl(ep, xp, direction):
        if ep is None or xp is None:
            return 0.0
        return round((xp - ep) if direction == "YES" else (ep - xp), 4)

    res_exit = (1.0 if resolution else 0.0) if resolution is not None else exit_price

    return SimulatedPosition(
        agent_id=signal.agent_id, market_id=signal.market_id,
        direction=signal.direction, entry_price=entry_price, exit_price=exit_price,
        entry_timestamp=entry_timestamp, exit_timestamp=exit_timestamp,
        exit_reason=exit_reason,
        pnl=calc_pnl(entry_price, exit_price, signal.direction),
        resolution_pnl=calc_pnl(entry_price, res_exit, signal.direction)
    )
