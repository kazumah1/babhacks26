from abc import ABC, abstractmethod
from datetime import datetime

from shared.types import AdapterContext, MarketSnapshot


class BaseAdapter(ABC):
    @abstractmethod
    def build_context(
        self,
        market: MarketSnapshot,
        replay_timestamp: datetime,
    ) -> AdapterContext:
        ...
