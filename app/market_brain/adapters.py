from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol


class InstrumentType(str, Enum):
    FOREX = "forex"
    INDEX = "index"
    COMMODITY = "commodity"
    EQUITY = "equity"
    OPTION = "option"
    FUTURE = "future"


class MarketDataAdapter(Protocol):
    def get_watchlist(self) -> list[dict[str, Any]]: ...
    def get_candles(self, epics: list[str]) -> dict[str, list[dict[str, Any]]]: ...


class BrokerAdapter(Protocol):
    def get_account(self) -> dict[str, Any]: ...
    def get_positions(self) -> list[dict[str, Any]]: ...


@dataclass
class IGAdapter:
    snapshot: dict[str, Any]

    def get_watchlist(self) -> list[dict[str, Any]]:
        return ((self.snapshot.get("watchlist") or {}).get("markets") or [])

    def get_candles(self, epics: list[str]) -> dict[str, list[dict[str, Any]]]:
        # No synthetic/fabricated candles. Return unavailable data unless a real candle source is connected.
        return {epic: [] for epic in epics}

    def get_account(self) -> dict[str, Any]:
        return self.snapshot.get("account") or {}

    def get_positions(self) -> list[dict[str, Any]]:
        return ((self.snapshot.get("positions") or {}).get("positions") or [])
