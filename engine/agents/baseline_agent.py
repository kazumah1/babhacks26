from shared.types import AdapterContext, TradingSignal, EntryCondition, ExitCondition
from engine.agents.base_agent import BaseAgent


class MarketBaselineAgent(BaseAgent):
    agent_id = "market_baseline"

    def trade(self, context: AdapterContext) -> TradingSignal:
        return TradingSignal(
            agent_id=self.agent_id,
            market_id=context.market_id,
            estimated_probability=context.current_probability,
            direction="PASS",
            confidence=1.0,
            allocation=0.0,
            entry_condition=EntryCondition(trigger="immediate", threshold=None, rationale="Baseline"),
            exit_condition=ExitCondition(
                trigger="to_resolution", price_target=None,
                time_limit=None, stop_loss=None, rationale="Baseline"
            ),
            hold_horizon="to_resolution",
            rationale="Market baseline: echoes current market probability with no additional signal.",
            raw_response=""
        )
