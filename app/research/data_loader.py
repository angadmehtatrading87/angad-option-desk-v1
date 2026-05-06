"""
Historical OHLC data loader.

Format: HistData.com / Dukascopy-style CSV, one bar per row:
    timestamp,open,high,low,close,volume

Where timestamp is ISO-8601 (UTC) or `YYYYMMDD HHMMSS`. Volume is optional.

Files live at `data/historical/<SYMBOL>_<INTERVAL>.csv`, e.g.
`data/historical/EURUSD_1H.csv`.

Pure stdlib — no pandas dependency to keep deploy footprint small.
"""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterator

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HISTORICAL_DIR = os.path.join(BASE_DIR, "data", "historical")


@dataclass
class Bar:
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


def _parse_ts(value: str) -> datetime | None:
    """Accept ISO-8601 (with or without timezone) and HistData's
    YYYYMMDD HHMMSS format."""
    value = value.strip()
    if not value:
        return None
    # Try ISO-8601
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        pass
    # Try YYYYMMDD HHMMSS (HistData)
    try:
        dt = datetime.strptime(value, "%Y%m%d %H%M%S")
        return dt.replace(tzinfo=timezone.utc)
    except Exception:
        pass
    # Try YYYYMMDD;HHMMSS;... (HistData ASCII format)
    try:
        ymd, hms = value.split()[0], value.split()[1] if " " in value else ""
        if not hms and ";" in value:
            parts = value.split(";")
            if len(parts) >= 2:
                ymd, hms = parts[0], parts[1]
        if hms:
            dt = datetime.strptime(f"{ymd} {hms}", "%Y%m%d %H%M%S")
            return dt.replace(tzinfo=timezone.utc)
    except Exception:
        pass
    return None


def historical_path(symbol: str, interval: str = "1H") -> str:
    return os.path.join(HISTORICAL_DIR, f"{symbol.upper()}_{interval}.csv")


def load_bars(
    symbol: str,
    interval: str = "1H",
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[Bar]:
    """Load all bars from `data/historical/<SYMBOL>_<INTERVAL>.csv` between
    `start` and `end` (inclusive). Returns empty list if file missing."""
    path = historical_path(symbol, interval)
    if not os.path.exists(path):
        return []

    bars: list[Bar] = []
    with open(path, "r", newline="") as f:
        # Try to sniff the dialect — HistData uses semicolons, Dukascopy uses commas
        sample = f.read(2048)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except Exception:
            dialect = csv.excel
        reader = csv.reader(f, dialect=dialect)
        for row in reader:
            if not row or len(row) < 5:
                continue
            ts = _parse_ts(row[0])
            if ts is None:
                # Skip header row
                continue
            try:
                o = float(row[1])
                h = float(row[2])
                lo = float(row[3])
                c = float(row[4])
                vol = float(row[5]) if len(row) > 5 and row[5].strip() else 0.0
            except (ValueError, IndexError):
                continue
            if start is not None and ts < start:
                continue
            if end is not None and ts > end:
                break
            bars.append(Bar(ts=ts, open=o, high=h, low=lo, close=c, volume=vol))
    return bars


def iter_bars(
    symbol: str,
    interval: str = "1H",
    start: datetime | None = None,
    end: datetime | None = None,
) -> Iterator[Bar]:
    """Streaming variant for large files."""
    for bar in load_bars(symbol, interval, start, end):
        yield bar


def list_available() -> list[tuple[str, str]]:
    """Returns [(symbol, interval), ...] of all historical CSVs present."""
    if not os.path.isdir(HISTORICAL_DIR):
        return []
    out = []
    for f in os.listdir(HISTORICAL_DIR):
        if not f.endswith(".csv"):
            continue
        stem = f[:-4]
        if "_" not in stem:
            continue
        sym, interval = stem.rsplit("_", 1)
        out.append((sym, interval))
    return sorted(out)
