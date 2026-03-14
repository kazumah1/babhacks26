from abc import ABC, abstractmethod
from shared.types import AdapterContext, TradingSignal


class BaseAgent(ABC):
    agent_id: str

    @abstractmethod
    def trade(self, context: AdapterContext) -> TradingSignal:
        ...
