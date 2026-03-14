from shared.types import TradingSignal, SimulatedPosition, AgentEvalResult
from engine.replay_engine import ReplayState


def evaluate_agent(
    signal: TradingSignal,
    position: SimulatedPosition,
    replay_state: ReplayState
) -> AgentEvalResult:
    resolution = replay_state.final_resolution
    market_prob = replay_state.probability_at_replay

    brier = None
    if resolution is not None:
        brier = round((signal.estimated_probability - float(resolution)) ** 2, 6)

    directional_correct = None
    if replay_state.future_price_history and signal.direction != "PASS":
        final_price = replay_state.future_price_history[-1].probability
        market_moved_up = final_price > market_prob
        agent_said_yes = signal.direction == "YES"
        directional_correct = (market_moved_up == agent_said_yes)

    return AgentEvalResult(
        agent_id=signal.agent_id,
        market_id=signal.market_id,
        market_question=replay_state.market.question,
        market_type=replay_state.context.market_type,
        brier_score=brier,
        edge_vs_market=round(signal.estimated_probability - market_prob, 4),
        directional_correct=directional_correct,
        simulated_pnl=position.pnl,
        resolution_pnl=position.resolution_pnl,
        exit_reason=position.exit_reason,
        estimated_probability=signal.estimated_probability,
        market_probability=market_prob,
        final_resolution=resolution,
        rationale=signal.rationale
    )
