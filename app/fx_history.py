import os
import sqlite3
from datetime import datetime, timezone
import yaml
import yfinance as yf
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "trades.db")

def load_yaml(path):
    with open(path, "r") as f:
        return yaml.safe_load(f)

def init_fx_tables():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS fx_daily_prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pair TEXT NOT NULL,
            date TEXT NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL,
            created_at TEXT NOT NULL,
            UNIQUE(pair, date)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS fx_regime_features (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pair TEXT NOT NULL,
            date TEXT NOT NULL,
            close REAL,
            return_5d REAL,
            return_20d REAL,
            volatility_20d REAL,
            trend_score REAL,
            volatility_score REAL,
            regime_label TEXT,
            created_at TEXT NOT NULL,
            UNIQUE(pair, date)
        )
    """)

    conn.commit()
    conn.close()

def safe_float(value, default=0.0):
    try:
        if isinstance(value, pd.Series):
            value = value.iloc[0]
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default

def clean_yfinance_df(df):
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns]
    return df

def fetch_fx_history():
    init_fx_tables()

    cfg = load_yaml(os.path.join(BASE_DIR, "config", "fx_pairs.yaml"))
    pairs = cfg["fx_pairs"]
    period = cfg["training"]["period"]
    interval = cfg["training"]["interval"]

    results = {}

    for pair, info in pairs.items():
        symbol = info["yahoo_symbol"]
        df = yf.download(symbol, period=period, interval=interval, progress=False, auto_adjust=False)

        if df.empty:
            results[pair] = {"status": "failed", "rows": 0}
            continue

        df = clean_yfinance_df(df)
        df = df.reset_index()

        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()

        rows = 0
        for _, row in df.iterrows():
            raw_date = row.get("Date") or row.get("Datetime")
            date = str(raw_date.date()) if hasattr(raw_date, "date") else str(raw_date)

            open_price = safe_float(row.get("Open"))
            high = safe_float(row.get("High"))
            low = safe_float(row.get("Low"))
            close = safe_float(row.get("Close"))
            volume = safe_float(row.get("Volume"))

            if close <= 0:
                continue

            cur.execute("""
                INSERT OR REPLACE INTO fx_daily_prices (
                    pair, date, open, high, low, close, volume, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                pair,
                date,
                open_price,
                high,
                low,
                close,
                volume,
                datetime.now(timezone.utc).isoformat()
            ))

            rows += 1

        conn.commit()
        conn.close()

        compute_fx_features(pair)
        results[pair] = {"status": "ok", "rows": rows}

    return results

def compute_fx_features(pair):
    cfg = load_yaml(os.path.join(BASE_DIR, "config", "fx_pairs.yaml"))
    thresholds = cfg["regime_thresholds"]

    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        "SELECT date, close FROM fx_daily_prices WHERE pair = ? ORDER BY date ASC",
        conn,
        params=(pair,)
    )

    if df.empty:
        conn.close()
        return

    df["close"] = df["close"].astype(float)
    df["return_5d"] = df["close"].pct_change(5)
    df["return_20d"] = df["close"].pct_change(20)
    df["daily_return"] = df["close"].pct_change()
    df["volatility_20d"] = df["daily_return"].rolling(20).std()

    cur = conn.cursor()

    for _, row in df.dropna().iterrows():
        ret20 = safe_float(row["return_20d"])
        vol20 = safe_float(row["volatility_20d"])

        trend_score = min(100, max(0, 50 + (ret20 / thresholds["strong_trend_return_20d"]) * 25))
        volatility_score = min(100, max(0, (vol20 / thresholds["high_volatility_20d"]) * 50))

        if vol20 >= thresholds["extreme_volatility_20d"]:
            regime = "FX_STRESS"
        elif ret20 >= thresholds["strong_trend_return_20d"]:
            regime = "USD_STRENGTH"
        elif ret20 <= -thresholds["strong_trend_return_20d"]:
            regime = "USD_WEAKNESS"
        elif vol20 >= thresholds["high_volatility_20d"]:
            regime = "FX_VOLATILE"
        else:
            regime = "FX_NEUTRAL"

        cur.execute("""
            INSERT OR REPLACE INTO fx_regime_features (
                pair, date, close, return_5d, return_20d, volatility_20d,
                trend_score, volatility_score, regime_label, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            pair,
            row["date"],
            safe_float(row["close"]),
            safe_float(row["return_5d"]),
            ret20,
            vol20,
            round(trend_score, 2),
            round(volatility_score, 2),
            regime,
            datetime.now(timezone.utc).isoformat()
        ))

    conn.commit()
    conn.close()

def latest_fx_regime():
    init_fx_tables()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    output = {}

    for pair in ["USDJPY", "USDCHF"]:
        cur.execute("""
            SELECT * FROM fx_regime_features
            WHERE pair = ?
            ORDER BY date DESC
            LIMIT 1
        """, (pair,))
        row = cur.fetchone()
        output[pair] = dict(row) if row else None

    conn.close()

    macro_score = 50
    notes = []

    usdjpy = output.get("USDJPY")
    usdchf = output.get("USDCHF")

    if usdjpy:
        if usdjpy["regime_label"] in ["FX_STRESS", "FX_VOLATILE"]:
            macro_score -= 15
            notes.append("USDJPY volatility/stress detected.")
        if usdjpy["regime_label"] == "USD_STRENGTH":
            macro_score -= 5
            notes.append("USDJPY shows USD strength / yield pressure.")
        if usdjpy["regime_label"] == "USD_WEAKNESS":
            macro_score += 5
            notes.append("USDJPY shows USD weakness / softer dollar pressure.")

    if usdchf:
        if usdchf["regime_label"] in ["FX_STRESS", "FX_VOLATILE"]:
            macro_score -= 15
            notes.append("USDCHF volatility/stress detected.")
        if usdchf["regime_label"] == "USD_STRENGTH":
            macro_score -= 5
            notes.append("USDCHF shows USD strength / possible safe-haven pressure.")
        if usdchf["regime_label"] == "USD_WEAKNESS":
            macro_score += 5
            notes.append("USDCHF shows USD weakness / calmer dollar backdrop.")

    macro_score = max(0, min(100, macro_score))

    if macro_score >= 65:
        macro_regime = "RISK_ON"
    elif macro_score >= 40:
        macro_regime = "NEUTRAL"
    else:
        macro_regime = "RISK_OFF"

    return {
        "macro_score": macro_score,
        "macro_regime": macro_regime,
        "notes": notes,
        "pairs": output
    }
