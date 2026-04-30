import os
import json
import sqlite3
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "trades.db")
STATE_PATH = os.path.join(BASE_DIR, "data", "daily_adaptation_state.json")
DXB = ZoneInfo("Asia/Dubai")

def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def recent_learning_rows(limit=300):
    conn = _conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT *
        FROM learning_log
        ORDER BY id DESC
        LIMIT ?
    """, (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def _split_tags(value):
    if not value:
        return []
    return [x.strip() for x in str(value).split(",") if x.strip()]

def build_adaptation_state():
    rows = recent_learning_rows(400)

    symbol_stats = defaultdict(lambda: {
        "trades": 0,
        "wins": 0,
        "losses": 0,
        "net_pnl": 0.0,
        "mistakes": defaultdict(int),
        "qualities": defaultdict(int),
        "tomorrow_notes": [],
    })

    strategy_stats = defaultdict(lambda: {
        "trades": 0,
        "wins": 0,
        "losses": 0,
        "net_pnl": 0.0,
        "mistakes": defaultdict(int),
        "qualities": defaultdict(int),
    })

    regime_stats = defaultdict(lambda: {
        "trades": 0,
        "wins": 0,
        "losses": 0,
        "net_pnl": 0.0,
    })

    for r in rows:
        symbol = str(r.get("symbol") or "").upper()
        strategy = str(r.get("strategy") or "").lower()
        regime = str(r.get("regime") or "UNKNOWN").upper()
        pnl = float(r.get("realized_pnl") or 0.0)
        mistakes = _split_tags(r.get("mistake_tags"))
        qualities = _split_tags(r.get("quality_tags"))
        tomorrow_note = str(r.get("tomorrow_note") or "").strip()

        if symbol:
            s = symbol_stats[symbol]
            s["trades"] += 1
            s["net_pnl"] += pnl
            if pnl > 0:
                s["wins"] += 1
            elif pnl < 0:
                s["losses"] += 1
            for t in mistakes:
                s["mistakes"][t] += 1
            for t in qualities:
                s["qualities"][t] += 1
            if tomorrow_note:
                s["tomorrow_notes"].append(tomorrow_note)

        if strategy:
            st = strategy_stats[strategy]
            st["trades"] += 1
            st["net_pnl"] += pnl
            if pnl > 0:
                st["wins"] += 1
            elif pnl < 0:
                st["losses"] += 1
            for t in mistakes:
                st["mistakes"][t] += 1
            for t in qualities:
                st["qualities"][t] += 1

        rg = regime_stats[regime]
        rg["trades"] += 1
        rg["net_pnl"] += pnl
        if pnl > 0:
            rg["wins"] += 1
        elif pnl < 0:
            rg["losses"] += 1

    def finalize_symbol(symbol, data):
        trades = data["trades"]
        wins = data["wins"]
        losses = data["losses"]
        net = round(data["net_pnl"], 2)
        win_rate = round((wins / trades) * 100, 2) if trades else 0.0

        bias = "neutral"
        score_adj = 0
        if trades >= 2:
            if net > 0 and win_rate >= 50:
                bias = "promote"
                score_adj = min(12, int(net // 1000) + 3)
            elif net < 0:
                bias = "penalize"
                score_adj = max(-12, -int(abs(net) // 1000) - 3)

        top_mistakes = sorted(data["mistakes"].items(), key=lambda x: x[1], reverse=True)[:5]
        top_qualities = sorted(data["qualities"].items(), key=lambda x: x[1], reverse=True)[:5]

        return {
            "symbol": symbol,
            "trades": trades,
            "wins": wins,
            "losses": losses,
            "win_rate": win_rate,
            "net_pnl": net,
            "bias": bias,
            "score_adjustment": score_adj,
            "top_mistakes": top_mistakes,
            "top_qualities": top_qualities,
            "tomorrow_notes": data["tomorrow_notes"][:5],
        }

    def finalize_strategy(strategy, data):
        trades = data["trades"]
        wins = data["wins"]
        losses = data["losses"]
        net = round(data["net_pnl"], 2)
        win_rate = round((wins / trades) * 100, 2) if trades else 0.0

        bias = "neutral"
        score_adj = 0
        if trades >= 2:
            if net > 0 and win_rate >= 50:
                bias = "promote"
                score_adj = min(10, int(net // 1000) + 2)
            elif net < 0:
                bias = "penalize"
                score_adj = max(-10, -int(abs(net) // 1000) - 2)

        return {
            "strategy": strategy,
            "trades": trades,
            "wins": wins,
            "losses": losses,
            "win_rate": win_rate,
            "net_pnl": net,
            "bias": bias,
            "score_adjustment": score_adj,
            "top_mistakes": sorted(data["mistakes"].items(), key=lambda x: x[1], reverse=True)[:5],
            "top_qualities": sorted(data["qualities"].items(), key=lambda x: x[1], reverse=True)[:5],
        }

    symbols_out = [finalize_symbol(k, v) for k, v in symbol_stats.items()]
    strategies_out = [finalize_strategy(k, v) for k, v in strategy_stats.items()]

    symbols_out = sorted(symbols_out, key=lambda x: (x["score_adjustment"], x["net_pnl"]), reverse=True)
    strategies_out = sorted(strategies_out, key=lambda x: (x["score_adjustment"], x["net_pnl"]), reverse=True)

    adaptation = {
        "generated_at_dxb": datetime.now(DXB).isoformat(),
        "symbols": symbols_out,
        "strategies": strategies_out,
        "regimes": regime_stats,
        "summary": {
            "promoted_symbols": [x["symbol"] for x in symbols_out if x["bias"] == "promote"][:10],
            "penalized_symbols": [x["symbol"] for x in symbols_out if x["bias"] == "penalize"][:10],
            "promoted_strategies": [x["strategy"] for x in strategies_out if x["bias"] == "promote"][:10],
            "penalized_strategies": [x["strategy"] for x in strategies_out if x["bias"] == "penalize"][:10],
        }
    }

    with open(STATE_PATH, "w") as f:
        json.dump(adaptation, f, indent=2, default=str)

    return adaptation

def load_adaptation_state():
    if not os.path.exists(STATE_PATH):
        return build_adaptation_state()
    with open(STATE_PATH, "r") as f:
        return json.load(f)

def symbol_score_adjustment(symbol):
    state = load_adaptation_state()
    symbol = str(symbol or "").upper()
    for row in state.get("symbols", []):
        if row.get("symbol") == symbol:
            return int(row.get("score_adjustment", 0))
    return 0

def strategy_score_adjustment(strategy):
    state = load_adaptation_state()
    strategy = str(strategy or "").lower()
    for row in state.get("strategies", []):
        if row.get("strategy") == strategy:
            return int(row.get("score_adjustment", 0))
    return 0
