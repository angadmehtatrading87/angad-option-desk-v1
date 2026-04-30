import streamlit as st
import yaml
import os
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

st.set_page_config(
    page_title="Angad Option Desk v1",
    page_icon="📈",
    layout="wide"
)

def load_yaml(path):
    with open(path, "r") as f:
        return yaml.safe_load(f)

risk = load_yaml(os.path.join(BASE_DIR, "config", "risk_limits.yaml"))
symbols = load_yaml(os.path.join(BASE_DIR, "config", "symbols.yaml"))

st.title("Angad Option Desk v1")
st.caption("Personal options trading control room — simulation mode")

col1, col2, col3, col4 = st.columns(4)

col1.metric("Mode", risk.get("account_mode", "simulation"))
col2.metric("Base Capital", f"${risk.get('base_capital_usd', 0):,.0f}")
col3.metric("Auto Trade", str(risk.get("auto_trade_enabled", False)))
col4.metric("Kill Switch", str(risk.get("kill_switch", False)))

st.divider()

left, right = st.columns(2)

with left:
    st.subheader("Risk Limits")
    st.write({
        "Max risk per trade": f"${risk.get('max_risk_per_trade_usd')}",
        "Max daily loss": f"${risk.get('max_daily_loss_usd')}",
        "Max weekly loss": f"${risk.get('max_weekly_loss_usd')}",
        "Max open trades": risk.get("max_open_trades"),
        "Min DTE": risk.get("min_days_to_expiry"),
        "Max DTE": risk.get("max_days_to_expiry"),
    })

with right:
    st.subheader("Watchlist")
    st.write(symbols.get("watchlist", []))

st.divider()

st.subheader("Trade Approval Queue")
st.info("No trade proposals yet. Broker/data connector not connected.")

st.subheader("System Status")
st.success("Agent base service is running.")
st.write(f"Last dashboard refresh: {datetime.now(timezone.utc).isoformat()} UTC")

st.warning("Auto-trading is disabled. No broker account is connected. No trades can be placed.")
