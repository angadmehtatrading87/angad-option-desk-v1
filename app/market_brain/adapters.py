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
    # Allow None so callers can construct an empty adapter and the worker
    # degrades cleanly instead of stack-tracing every loop. The v1 of this
    # adapter typed snapshot as a required dict and then a caller passed
    # snapshot=None — every method blew up with AttributeError.
    snapshot: dict[str, Any] | None = None

    def _snap(self) -> dict[str, Any]:
        return self.snapshot or {}

    def get_watchlist(self) -> list[dict[str, Any]]:
        return ((self._snap().get("watchlist") or {}).get("markets") or [])

    def get_candles(self, epics: list[str]) -> dict[str, list[dict[str, Any]]]:
        # No synthetic/fabricated candles. Return unavailable data unless a real candle source is connected.
        return {epic: [] for epic in epics}

    def get_account(self) -> dict[str, Any]:
        return self._snap().get("account") or {}

    def get_positions(self) -> list[dict[str, Any]]:
        return ((self._snap().get("positions") or {}).get("positions") or [])
