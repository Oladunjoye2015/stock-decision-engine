from abc import ABC, abstractmethod


class MarketDataProvider(ABC):
    @abstractmethod
    def context(self, symbol: str, timeframe: str) -> dict: ...

