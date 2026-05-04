from app.ig_learning_memory import summarize_memory, latest_daily_review
from app.ig_position_takeover import takeover_view
from app.ig_session_intelligence import get_ig_session_state
from app.ig_no_trade_reason_engine import get_no_trade_reasons
from app.ig_api_governor import get_ig_cached_snapshot
from app.lane_capital_controller import lane_capital_state
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, RedirectResponse
from app.dashboard_state import get_dashboard_state
from app.research_state import get_research_state
from app.ig_decision_engine import build_ig_decisions
from app.ig_execution_engine import get_ig_execution_snapshot
from app.ig_position_manager import get_live_ig_positions
from app.ui_blocks import card, metric, pill, table
from app.chart_utils import svg_line_chart, svg_dual_line_chart, svg_bar_chart
from datetime import datetime, timezone
import yaml
import os
import random

from app.config_manager import set_kill_switch, set_scanner_enabled
from app.system_health import get_system_health
from app.trading_window import trading_window_status
from app.news_macro import latest_news_macro
from app.fx_history import latest_fx_regime, fetch_fx_history


def status_pill_class(status):
    s = (status or "").upper()
    if s in ["PENDING_APPROVAL", "VIRTUAL_OPEN", "APPROVED_BY_USER"]:
        return "good"
    if s in ["BLOCKED", "REJECTED", "VIRTUAL_STALE_BLOCKED", "BROKER_DRY_RUN_FAILED"]:
        return "bad"
    return "warn"


app = FastAPI(title="Autobot Trader Pro — IG")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load_yaml(path):
    with open(path, "r") as f:
        return yaml.safe_load(f)

@app.get("/")
def dashboard():
    """Root path → redirect to the IG desk. The legacy options-trading
    dashboard (with manual ticketing, virtual portfolio, etc.) was removed
    in the Tastytrade strip; the IG desk is the live homepage now."""
    return RedirectResponse(url="/ig-desk", status_code=307)


def _legacy_dashboard_DEAD():
    # NOTE: this body is preserved only because parts of it generate HTML used
    # elsewhere as a style template. It is no longer reachable. The legacy
    # imports (list_trades, virtual_account_snapshot, run_scan, manual_ticket,
    # tasty_*, option_chain, spread_builder, order_preview) have been removed.
    # Cleanup of the rest of the orphan routes happens in cleanup/remove_tastytrade.sh.
    risk = load_yaml(os.path.join(BASE_DIR, "config", "risk_limits.yaml"))
    symbols = load_yaml(os.path.join(BASE_DIR, "config", "symbols.yaml"))
    trades = []  # was: list_trades(25)

    trade_rows = ""
    for t in trades:
        badge_color = "#2f855a" if t["risk_result"] == "PASSED" else "#c05621"

        if t["status"] == "PENDING_APPROVAL":
            action_buttons = f"""
            <a class="approve" href="/approve/{t['id']}">Approve</a>
            <a class="reject" href="/reject/{t['id']}">Reject</a>
            """
        elif t["status"] == "BLOCKED":
            action_buttons = "Blocked by risk engine"
        else:
            action_buttons = f"""
            {t["status"]}<br>
            <a class="button" href="/manual-ticket/{t['id']}">Manual Ticket</a>
            """

        trade_rows += f"""
        <tr>
            <td>#{t['id']}</td>
            <td>{t['created_at']}</td>
            <td>{t['symbol']}</td>
            <td>{t['strategy']}</td>
            <td>{t['expiry']}</td>
            <td>{t['legs']}</td>
            <td>${t['max_risk']}</td>
            <td><span style="background:{badge_color};padding:6px 10px;border-radius:8px;">{t['risk_result']}</span></td>
            <td>{t['status']}</td>
            <td>{t.get('agent_grade') or '-'}</td>
            <td>{t.get('agent_view') or '-'}</td>
            <td>{t.get('confidence_score') or '-'}</td>
            <td>{t.get('decision_summary') or t['reason']}</td>
            <td>{action_buttons}</td>
        </tr>
        """

    if not trade_rows:
        trade_rows = """
        <tr>
            <td colspan="11">No trade proposals yet.</td>
        </tr>
        """

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Angad Option Desk v1</title>
        <meta http-equiv="refresh" content="5">
        <style>
        body {{
            background: #0b1020;
            color: #e8ecf3;
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 0;
        }}
        .page {{
            max-width: 1500px;
            margin: 0 auto;
            padding: 24px;
        }}
        .topbar {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 20px;
            margin-bottom: 18px;
        }}
        .title-wrap h1 {{
            margin: 0;
            font-size: 34px;
            font-weight: 700;
            letter-spacing: -0.02em;
        }}
        .subtitle {{
            color: #97a3b6;
            margin-top: 8px;
            font-size: 14px;
        }}
        .badge {{
            display: inline-block;
            padding: 8px 12px;
            border-radius: 999px;
            background: #182235;
            color: #9dc1ff;
            font-size: 12px;
            font-weight: 700;
            border: 1px solid #24314b;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 16px;
            margin-bottom: 18px;
        }}
        .grid-2 {{
            display: grid;
            grid-template-columns: 1.2fr 0.8fr;
            gap: 16px;
            margin-bottom: 18px;
        }}
        .card {{
            background: linear-gradient(180deg, #12192b 0%, #0f1626 100%);
            border: 1px solid #1f2a40;
            border-radius: 18px;
            padding: 18px;
            box-shadow: 0 8px 28px rgba(0,0,0,0.22);
        }}
        .label {{
            color: #90a0b7;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            margin-bottom: 10px;
        }}
        .value {{
            font-size: 30px;
            font-weight: 700;
            color: #f3f6fb;
        }}
        .subvalue {{
            margin-top: 8px;
            color: #9eb0c8;
            font-size: 13px;
        }}
        .section {{
            background: #101827;
            border: 1px solid #1f2a40;
            border-radius: 18px;
            padding: 18px;
            margin-bottom: 18px;
            box-shadow: 0 8px 28px rgba(0,0,0,0.18);
        }}
        .section h2 {{
            margin: 0 0 14px 0;
            font-size: 20px;
        }}
        .macro-banner {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 16px;
            background: linear-gradient(90deg, #132038 0%, #182948 100%);
            border: 1px solid #294062;
            border-radius: 18px;
            padding: 16px 18px;
            margin-bottom: 18px;
        }}
        .macro-title {{
            font-size: 13px;
            color: #93a8c6;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            margin-bottom: 6px;
        }}
        .macro-value {{
            font-size: 22px;
            font-weight: 700;
        }}
        .macro-summary {{
            color: #b7c4d8;
            font-size: 14px;
        }}
        .button-row {{
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
        }}
        .button {{
            display: inline-block;
            padding: 10px 14px;
            border-radius: 12px;
            background: #2563eb;
            color: white;
            text-decoration: none;
            font-size: 13px;
            font-weight: 700;
            border: 1px solid rgba(255,255,255,0.08);
        }}
        .button.red {{ background: #dc2626; }}
        .button.green {{ background: #16a34a; }}
        .button.gray {{ background: #334155; }}
        .pill {{
            display: inline-block;
            padding: 6px 10px;
            border-radius: 999px;
            font-size: 12px;
            font-weight: 700;
            background: #172133;
            color: #c6d2e3;
            border: 1px solid #24314b;
        }}
        .pill.good {{ color: #8ff0a4; }}
        .pill.bad {{ color: #ff8f8f; }}
        .pill.warn {{ color: #f6d365; }}
        .mono {{
            font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }}
        th, td {{
            padding: 11px 10px;
            border-bottom: 1px solid #1f2a40;
            text-align: left;
            vertical-align: top;
        }}
        th {{
            color: #92a3bb;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        tr:hover td {{
            background: rgba(255,255,255,0.02);
        }}
        .small {{
            font-size: 12px;
            color: #9bb0ca;
        }}
        pre {{
            white-space: pre-wrap;
            background: #0b1220;
            border: 1px solid #1f2a40;
            padding: 14px;
            border-radius: 14px;
            color: #d9e2ef;
            font-size: 13px;
        }}
    </style>
    </head>
    <body>
        <h1>Angad Option Desk v1</h1>
        <div class="subtitle">Personal options trading control room — lightweight mode</div>

        <div class="grid">
            <div class="card"><div class="label">Mode</div><div class="value">{risk.get("account_mode")}</div></div>
            <div class="card"><div class="label">Agent Allocation</div><div class="value">${risk.get("base_capital_usd"):,.0f}</div></div>
            <div class="card"><div class="label">Auto Trade</div><div class="value">{risk.get("auto_trade_enabled")}</div></div>
            <div class="card"><div class="label">Kill Switch</div><div class="value">{risk.get("kill_switch")}</div></div>
        </div>

        <div class="section">
            <h2>Actions</h2>
            <a class="button" href="/run-scan">Run Market Scanner</a>
            <a class="button" href="/pause-scanner">Pause Scanner</a>
            <a class="button" href="/resume-scanner">Resume Scanner</a>
            <a class="reject" href="/kill-on">Kill Switch ON</a>
            <a class="approve" href="/kill-off">Kill Switch OFF</a>
            <a class="button" href="/generate-sample-trade">Generate Sample Trade</a>
            <a class="button" href="/build-spreads/SPY">Build SPY Spreads</a>
            <a class="button" href="/build-spreads/QQQ">Build QQQ Spreads</a>
            <a class="button" href="/option-chain/SPY">SPY Option Chain</a>
            <a class="button" href="/option-chain/QQQ">QQQ Option Chain</a>
            <a class="button" href="/tasty-account">Broker Account</a>
            <a class="button" href="/news-macro">News / Macro</a>
            <a class="button" href="/virtual-monitor">Virtual Monitor</a>
            <a class="button" href="/virtual-portfolio">Virtual Portfolio</a>
            <a class="button" href="/trading-window">Trading Window</a>
            <a class="button" href="/fx-watchtower">FX Macro Watchtower</a>
            <a class="button" href="/refresh-fx-history">Refresh FX Data</a>
            <a class="button" href="/system-health">System Health</a>
            <a class="button" href="/health">Health Check</a>
            <a class="button" href="/risk">Risk JSON</a>
            <a class="button" href="/trades">Trades JSON</a>
        </div>

        <div class="section">
            <h2>Risk Limits</h2>
            <pre>
Max risk per trade: ${risk.get("max_risk_per_trade_usd")}
Max daily loss: ${risk.get("max_daily_loss_usd")}
Max weekly loss: ${risk.get("max_weekly_loss_usd")}
Max open trades: {risk.get("max_open_trades")}
Min DTE: {risk.get("min_days_to_expiry")}
Max DTE: {risk.get("max_days_to_expiry")}
Approval required: {risk.get("approval_required")}
            </pre>
        </div>

        <div class="section">
            <h2>Watchlist</h2>
            <pre>{", ".join(symbols.get("watchlist", []))}</pre>
        </div>

        <div class="section">
            <h2>Trade Approval Queue</h2>
            <table>
                <tr>
                    <th>ID</th>
                    <th>Created</th>
                    <th>Symbol</th>
                    <th>Strategy</th>
                    <th>Expiry</th>
                    <th>Legs</th>
                    <th>Max Risk</th>
                    <th>Risk</th>
                    <th>Status</th>
                    <th>Grade</th>
                    <th>Agent View</th>
                    <th>Confidence</th>
                    <th>Reason</th>
                    <th>Action</th>
                </tr>
                {trade_rows}
            </table>
        </div>

        <div class="section">
            <h2>System Status</h2>
            <div class="safe">Agent base service is running.</div>
            <br>
            <div class="warn">Auto-trading is disabled. No broker account is connected. No trades can be placed.</div>
            <p>Last refresh: {datetime.now(timezone.utc).isoformat()}</p>
        </div>
    </body>
    </html>
    """
    return html











@app.get("/manual-ticket/{trade_id}", response_class=HTMLResponse)
def manual_ticket_route(trade_id: int):
    try:
        result = generate_manual_ticket(trade_id)
        ticket = result["ticket"]
        return HTMLResponse(f"""
        <html>
        <body style="background:#0f1117;color:white;font-family:Arial;margin:40px;">
            <h1>Manual Execution Ticket #{trade_id}</h1>
            <pre style="white-space:pre-wrap;background:#171923;padding:20px;border-radius:12px;border:1px solid #2a2d3a;">{ticket}</pre>
            <p>No API order has been placed.</p>
            <a href="/mark-executed/{trade_id}" style="color:#8ff0a4;font-weight:bold;">Mark Manually Executed</a><br><br>
            <a href="/mark-not-executed/{trade_id}" style="color:#ff7b7b;font-weight:bold;">Mark Not Executed</a><br><br>
            <a href="/" style="color:#60a5fa;">Back to Dashboard</a>
        </body>
        </html>
        """)
    except Exception as e:
        return HTMLResponse(f"""
        <html>
        <body style="background:#0f1117;color:white;font-family:Arial;margin:40px;">
            <h1>Manual Ticket Error</h1>
            <p>{str(e)}</p>
            <a href="/" style="color:#60a5fa;">Back to dashboard</a>
        </body>
        </html>
        """)

@app.get("/mark-executed/{trade_id}")
def mark_executed_route(trade_id: int):
    mark_executed(trade_id)
    return RedirectResponse(url="/", status_code=303)

@app.get("/mark-not-executed/{trade_id}")
def mark_not_executed_route(trade_id: int):
    mark_not_executed(trade_id)
    return RedirectResponse(url="/", status_code=303)

@app.get("/broker-preview/{trade_id}")
def broker_preview_route(trade_id: int):
    try:
        preview_trade_order(trade_id)
        return RedirectResponse(url="/", status_code=303)
    except Exception as e:
        return HTMLResponse(f"""
        <html>
        <body style="background:#0f1117;color:white;font-family:Arial;margin:40px;">
            <h1>Broker Preview Error</h1>
            <p>{str(e)}</p>
            <p>No order was placed.</p>
            <a href="/" style="color:#60a5fa;">Back to dashboard</a>
        </body>
        </html>
        """)

@app.get("/build-spreads/{symbol}")
def build_spreads(symbol: str):
    propose_spread_candidates(symbol.upper())
    return RedirectResponse(url="/", status_code=303)

@app.get("/option-chain/{symbol}", response_class=HTMLResponse)
def option_chain_page(symbol: str):
    try:
        summary = get_chain_summary(symbol.upper())
        error = None
    except Exception as e:
        summary = None
        error = str(e)

    if error:
        return HTMLResponse(f"""
        <html>
        <body style="background:#0f1117;color:white;font-family:Arial;margin:40px;">
            <h1>Option Chain Error</h1>
            <p>{error}</p>
            <a href="/" style="color:#60a5fa;">Back to Dashboard</a>
        </body>
        </html>
        """)

    expiry_html = ""

    for exp in summary["expiries"]:
        rows = ""
        for s in exp["sample_strikes"]:
            rows += f"""
            <tr>
                <td>{s.get("strike_price")}</td>
                <td>{s.get("call_symbol")}</td>
                <td>{s.get("put_symbol")}</td>
                <td>{s.get("call_streamer")}</td>
                <td>{s.get("put_streamer")}</td>
            </tr>
            """

        expiry_html += f"""
        <div class="section">
            <h2>Expiry: {exp["expiration_date"]} — {exp["dte"]} DTE</h2>
            <p>Strike count: {exp["strike_count"]}. Showing first 30 strikes only.</p>
            <table>
                <tr>
                    <th>Strike</th>
                    <th>Call Symbol</th>
                    <th>Put Symbol</th>
                    <th>Call Streamer</th>
                    <th>Put Streamer</th>
                </tr>
                {rows}
            </table>
        </div>
        """

    if not expiry_html:
        expiry_html = "<div class='section'>No expiries found in 21–45 DTE range.</div>"

    html = f"""
    <html>
    <head>
        <title>{summary["symbol"]} Option Chain</title>
        <style>
            body {{
                background:#0f1117;
                color:white;
                font-family:Arial, sans-serif;
                margin:32px;
            }}
            .section {{
                background:#171923;
                padding:18px;
                border-radius:12px;
                border:1px solid #2a2d3a;
                margin-bottom:18px;
            }}
            table {{
                width:100%;
                border-collapse:collapse;
                font-size:13px;
            }}
            th, td {{
                padding:9px;
                border-bottom:1px solid #2a2d3a;
                text-align:left;
            }}
            th {{
                color:#aaa;
            }}
            a {{
                color:#60a5fa;
            }}
            .button {{
                display:inline-block;
                padding:11px 15px;
                background:#2563eb;
                color:white;
                border-radius:10px;
                text-decoration:none;
                margin-right:10px;
            }}
        </style>
    </head>
    <body>
        <h1>{summary["symbol"]} Option Chain</h1>
        <p>Read-only Tastytrade sandbox option chain. Filter: {summary["min_dte"]}–{summary["max_dte"]} DTE.</p>

        <div class="section">
            <a class="button" href="/option-chain/SPY">SPY</a>
            <a class="button" href="/option-chain/QQQ">QQQ</a>
            <a class="button" href="/option-chain/AAPL">AAPL</a>
            <a class="button" href="/option-chain/MSFT">MSFT</a>
            <a class="button" href="/">Back to Dashboard</a>
        </div>

        {expiry_html}
    </body>
    </html>
    """
    return HTMLResponse(html)

@app.get("/tasty-account", response_class=HTMLResponse)
def tasty_account_page():
    cfg = tasty_config()

    def money(value):
        try:
            return f"${float(value):,.2f}"
        except Exception:
            return str(value or "-")

    def get_nested(data, keys, default="-"):
        cur = data
        try:
            for k in keys:
                cur = cur[k]
            return cur
        except Exception:
            return default

    try:
        accounts_raw = get_accounts()
        account_items = accounts_raw.get("data", {}).get("items", [])
        account_obj = account_items[0].get("account", {}) if account_items else {}
    except Exception as e:
        accounts_raw = {"error": str(e)}
        account_obj = {}

    try:
        balances_raw = get_balances()
        balance = balances_raw.get("data", {})
    except Exception as e:
        balances_raw = {"error": str(e)}
        balance = {}

    try:
        positions_raw = get_positions()
        positions = positions_raw.get("data", {}).get("items", [])
    except Exception as e:
        positions_raw = {"error": str(e)}
        positions = []

    pos_rows = ""
    if positions:
        for p in positions:
            pos_rows += f"""
            <tr>
                <td>{p.get("symbol", "-")}</td>
                <td>{p.get("instrument-type", "-")}</td>
                <td>{p.get("quantity", "-")}</td>
                <td>{p.get("quantity-direction", "-")}</td>
                <td>{money(p.get("average-open-price"))}</td>
                <td>{p.get("expires-at", "-")}</td>
            </tr>
            """
    else:
        pos_rows = '<tr><td colspan="6">No open positions.</td></tr>'

    suitable_options = account_obj.get("suitable-options-level", "-")
    margin_type = account_obj.get("margin-or-cash", "-")
    account_type = account_obj.get("account-type-name", "-")
    day_trader_status = account_obj.get("day-trader-status", "-")
    futures_approved = account_obj.get("futures-approved", "-")

    cash_balance = balance.get("cash-balance", "-")
    buying_power = balance.get("buying-power", "-")
    derivative_buying_power = balance.get("derivative-buying-power", "-")
    available_trading_funds = balance.get("available-trading-funds", "-")
    maintenance_excess = balance.get("maintenance-excess", "-")
    equity_buying_power = balance.get("equity-buying-power", "-")
    net_liquidating_value = balance.get("net-liquidating-value", "-")

    html = f"""
    <html>
    <head>
        <title>Tastytrade Production Read-Only Account</title>
        <meta http-equiv="refresh" content="5">
        <style>
            body {{
                background:#0f1117;
                color:white;
                font-family:Arial, sans-serif;
                margin:32px;
            }}
            h1 {{
                margin-bottom:4px;
            }}
            .subtitle {{
                color:#aaa;
                margin-bottom:24px;
            }}
            .grid {{
                display:grid;
                grid-template-columns:repeat(4, 1fr);
                gap:16px;
                margin-bottom:22px;
            }}
            .grid3 {{
                display:grid;
                grid-template-columns:repeat(3, 1fr);
                gap:16px;
                margin-bottom:22px;
            }}
            .card, .section {{
                background:#171923;
                padding:18px;
                border-radius:12px;
                border:1px solid #2a2d3a;
                margin-bottom:18px;
            }}
            .label {{
                color:#aaa;
                font-size:12px;
                text-transform:uppercase;
                letter-spacing:0.04em;
            }}
            .value {{
                font-size:22px;
                margin-top:7px;
                font-weight:bold;
            }}
            .safe {{
                color:#8ff0a4;
                font-weight:bold;
            }}
            .danger {{
                color:#ff7b7b;
                font-weight:bold;
            }}
            .warn {{
                color:#f6d365;
                font-weight:bold;
            }}
            table {{
                width:100%;
                border-collapse:collapse;
                font-size:14px;
            }}
            th, td {{
                padding:11px;
                border-bottom:1px solid #2a2d3a;
                text-align:left;
            }}
            th {{
                color:#aaa;
            }}
            a {{
                color:#60a5fa;
                text-decoration:none;
            }}
            .button {{
                display:inline-block;
                padding:11px 15px;
                background:#2563eb;
                color:white;
                border-radius:10px;
                text-decoration:none;
                margin-right:10px;
            }}
            details {{
                margin-top:10px;
            }}
            pre {{
                white-space:pre-wrap;
                overflow-x:auto;
                background:#0b0d12;
                padding:12px;
                border-radius:10px;
                border:1px solid #2a2d3a;
                font-size:12px;
                max-height:260px;
            }}
        </style>
    </head>
    <body>
        <h1>Tastytrade Production Read-Only Account</h1>
        <div class="subtitle">Production broker connection is read-only. Order execution is disabled.</div>

        <div class="grid">
            <div class="card">
                <div class="label">Environment</div>
                <div class="value">{cfg.get("env")}</div>
            </div>
            <div class="card">
                <div class="label">Account Number</div>
                <div class="value">{cfg.get("account_number")}</div>
            </div>
            <div class="card">
                <div class="label">Read Only</div>
                <div class="value safe">{cfg.get("read_only")}</div>
            </div>
            <div class="card">
                <div class="label">Order Execution</div>
                <div class="value {'danger' if cfg.get("order_execution_enabled") else 'safe'}">{cfg.get("order_execution_enabled")}</div>
            </div>
        </div>

        <div class="grid3">
            <div class="card">
                <div class="label">Cash Balance</div>
                <div class="value">{money(cash_balance)}</div>
            </div>
            <div class="card">
                <div class="label">Buying Power</div>
                <div class="value">{money(buying_power)}</div>
            </div>
            <div class="card">
                <div class="label">Net Liquidating Value</div>
                <div class="value">{money(net_liquidating_value)}</div>
            </div>
        </div>

        <div class="grid3">
            <div class="card">
                <div class="label">Derivative Buying Power</div>
                <div class="value">{money(derivative_buying_power)}</div>
            </div>
            <div class="card">
                <div class="label">Available Trading Funds</div>
                <div class="value">{money(available_trading_funds)}</div>
            </div>
            <div class="card">
                <div class="label">Maintenance Excess</div>
                <div class="value">{money(maintenance_excess)}</div>
            </div>
        </div>

        <div class="section">
            <h2>Account Profile</h2>
            <table>
                <tr><th>Account Type</th><td>{account_type}</td></tr>
                <tr><th>Margin Type</th><td>{margin_type}</td></tr>
                <tr><th>Options Level</th><td>{suitable_options}</td></tr>
                <tr><th>Day Trader Status</th><td>{day_trader_status}</td></tr>
                <tr><th>Futures Approved</th><td>{futures_approved}</td></tr>
            </table>
        </div>

        <div class="section">
            <h2>Positions</h2>
            <table>
                <tr>
                    <th>Symbol</th>
                    <th>Type</th>
                    <th>Quantity</th>
                    <th>Direction</th>
                    <th>Avg Open Price</th>
                    <th>Expiry</th>
                </tr>
                {pos_rows}
            </table>
        </div>

        <div class="section">
            <h2>Safety Status</h2>
            <p>Read Only: <b class="safe">{cfg.get("read_only")}</b></p>
            <p>Order Execution Enabled: <b class="danger">{cfg.get("order_execution_enabled")}</b></p>
            <p class="warn">No live or sandbox orders can be placed by current configuration.</p>
        </div>

        <div class="section">
            <a class="button" href="/">Back to Dashboard</a>
            <a class="button" href="/tasty-account">Refresh Account</a>
        </div>

        <details>
            <summary>Raw API Data</summary>
            <h3>Accounts Raw</h3>
            <pre>{accounts_raw}</pre>
            <h3>Balances Raw</h3>
            <pre>{balances_raw}</pre>
            <h3>Positions Raw</h3>
            <pre>{positions_raw}</pre>
        </details>
    </body>
    </html>
    """
    return HTMLResponse(html)






@app.get("/news-macro", response_class=HTMLResponse)
def news_macro_page():
    data = latest_news_macro()
    snap = data.get("snapshot") or {}
    headlines = data.get("headlines") or []

    rows = ""
    for h in headlines:
        rows += f"""
        <tr>
            <td>{h.get("source")}</td>
            <td>{h.get("title")}</td>
            <td>{h.get("published")}</td>
        </tr>
        """

    if not rows:
        rows = '<tr><td colspan="3">No headlines loaded yet.</td></tr>'

    regime = snap.get("macro_regime", "UNKNOWN")
    color = "#8ff0a4" if regime == "RISK_ON" else "#ff7b7b" if regime == "RISK_OFF" else "#f6d365"

    html = f"""
    <html>
    <head>
        <title>News / Macro</title>
        <meta http-equiv="refresh" content="5">
        <style>
            body {{
                background:#0f1117;
                color:white;
                font-family:Arial,sans-serif;
                margin:32px;
            }}
            .grid {{
                display:grid;
                grid-template-columns:repeat(4, 1fr);
                gap:16px;
                margin-bottom:20px;
            }}
            .card, .section {{
                background:#171923;
                padding:18px;
                border-radius:12px;
                border:1px solid #2a2d3a;
                margin-bottom:18px;
            }}
            .label {{
                color:#aaa;
                font-size:12px;
                text-transform:uppercase;
            }}
            .value {{
                font-size:22px;
                margin-top:8px;
                font-weight:bold;
            }}
            table {{
                width:100%;
                border-collapse:collapse;
                font-size:14px;
            }}
            th, td {{
                padding:10px;
                border-bottom:1px solid #2a2d3a;
                text-align:left;
            }}
            th {{ color:#aaa; }}
            a {{
                color:#60a5fa;
                text-decoration:none;
            }}
        </style>
    </head>
    <body>
        <h1>News / Macro</h1>

        <div class="grid">
            <div class="card">
                <div class="label">Headline Count</div>
                <div class="value">{snap.get("headline_count", 0)}</div>
            </div>
            <div class="card">
                <div class="label">Risk-On Score</div>
                <div class="value">{snap.get("risk_on_score", 0)}</div>
            </div>
            <div class="card">
                <div class="label">Risk-Off Score</div>
                <div class="value">{snap.get("risk_off_score", 0)}</div>
            </div>
            <div class="card">
                <div class="label">Macro Regime</div>
                <div class="value" style="color:{color};">{regime}</div>
            </div>
        </div>

        <div class="section">
            <h2>Summary</h2>
            <p>{snap.get("summary", "No summary yet.")}</p>
        </div>

        <div class="section">
            <h2>Latest Headlines</h2>
            <table>
                <tr>
                    <th>Source</th>
                    <th>Title</th>
                    <th>Published</th>
                </tr>
                {rows}
            </table>
        </div>

        <div class="section">
            <a href="/">Back to Dashboard</a>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(html)

@app.get("/virtual-monitor", response_class=HTMLResponse)
def virtual_monitor_page():
    actions = evaluate_open_positions()

    rows = ""
    for a in actions:
        action_color = "#8ff0a4" if a["decision"] == "TAKE_PROFIT" else "#ff7b7b" if a["decision"] == "STOP_OUT" else "#f6d365"
        rows += f"""
        <tr>
            <td>{a["position_id"]}</td>
            <td>{a["trade_id"]}</td>
            <td>{a["symbol"]}</td>
            <td>{a["strategy"]}</td>
            <td>{a.get("entry_price")}</td>
            <td>{a.get("current_spread_mid")}</td>
            <td>{a.get("price_diff")}</td>
            <td>{a.get("unrealized_pnl")}</td>
            <td>{a.get("quote_status", "OK")}</td>
            <td>{a["target_profit"]}</td>
            <td>{a["stop_loss"]}</td>
            <td style="color:{action_color};font-weight:bold;">{a["decision"]}</td>
            <td>{a["reason"]}</td>
            <td><a href="/virtual-close/{a['position_id']}/{a['current_spread_mid']}" style="color:#60a5fa;">Close Now</a></td>
        </tr>
        """

    if not rows:
        rows = '<tr><td colspan="14">No open virtual positions.</td></tr>'

    html = f"""
    <html>
    <head>
        <title>Virtual Monitor</title>
        <meta http-equiv="refresh" content="5">
        <style>
            body {{
                background:#0f1117;
                color:white;
                font-family:Arial,sans-serif;
                margin:32px;
            }}
            .section {{
                background:#171923;
                padding:18px;
                border-radius:12px;
                border:1px solid #2a2d3a;
                margin-bottom:18px;
            }}
            table {{
                width:100%;
                border-collapse:collapse;
                font-size:14px;
            }}
            th, td {{
                padding:10px;
                border-bottom:1px solid #2a2d3a;
                text-align:left;
            }}
            th {{ color:#aaa; }}
            a {{
                color:#60a5fa;
                text-decoration:none;
            }}
        </style>
    </head>
    <body>
        <h1>Virtual Monitor</h1>
        <p>Live-data paper trading exit monitor.</p>

        <div class="section">
            <table>
                <tr>
                    <th>Position ID</th>
                    <th>Trade ID</th>
                    <th>Symbol</th>
                    <th>Strategy</th>
                    <th>Entry</th>
                    <th>Current Mid</th>
                    <th>Diff</th>
                    <th>Unrealized P&amp;L</th>
                    <th>Quote Status</th>
                    <th>Target Profit</th>
                    <th>Stop Loss</th>
                    <th>Decision</th>
                    <th>Reason</th>
                    <th>Action</th>
                </tr>
                {rows}
            </table>
        </div>

        <div class="section">
            <a href="/">Back to Dashboard</a>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(html)

@app.get("/virtual-close/{position_id}/{exit_price}")
def virtual_close_route(position_id: int, exit_price: float):
    try:
        close_position_now(position_id, exit_price, note="Closed from virtual monitor.")
        return RedirectResponse(url="/virtual-portfolio", status_code=303)
    except Exception as e:
        return HTMLResponse(f"""
        <html>
        <body style="background:#0f1117;color:white;font-family:Arial;margin:40px;">
            <h1>Virtual Close Error</h1>
            <p>{str(e)}</p>
            <a href="/virtual-monitor" style="color:#60a5fa;">Back to Virtual Monitor</a>
        </body>
        </html>
        """)

@app.get("/virtual-portfolio", response_class=HTMLResponse)
def virtual_portfolio_page():
    snapshot = virtual_account_snapshot()

    pos_rows = ""
    for p in snapshot["open_positions"]:
        pos_rows += f"""
        <tr>
            <td>{p.get("id")}</td>
            <td>{p.get("trade_id")}</td>
            <td>{p.get("symbol")}</td>
            <td>{p.get("strategy")}</td>
            <td>{p.get("entry_debit")}</td>
            <td>{p.get("entry_credit")}</td>
            <td>{p.get("status")}</td>
            <td>{p.get("opened_at")}</td>
        </tr>
        """

    if not pos_rows:
        pos_rows = '<tr><td colspan="8">No open virtual positions.</td></tr>'

    unreal_rows = ""
    for u in snapshot["unrealized_details"]:
        unreal_rows += f"""
        <tr>
            <td>{u.get("position_id")}</td>
            <td>{u.get("trade_id")}</td>
            <td>{u.get("symbol")}</td>
            <td>{u.get("strategy")}</td>
            <td>{u.get("current_spread_mid")}</td>
            <td>{u.get("unrealized_pnl")}</td>
        </tr>
        """

    if not unreal_rows:
        unreal_rows = '<tr><td colspan="6">No unrealized P&amp;L yet.</td></tr>'

    html = f"""
    <html>
    <head>
        <title>Virtual Portfolio</title>
        <meta http-equiv="refresh" content="5">
        <style>
            body {{
                background:#0f1117;
                color:white;
                font-family:Arial,sans-serif;
                margin:32px;
            }}
            .grid {{
                display:grid;
                grid-template-columns:repeat(4, 1fr);
                gap:16px;
                margin-bottom:20px;
            }}
            .card, .section {{
                background:#171923;
                padding:18px;
                border-radius:12px;
                border:1px solid #2a2d3a;
                margin-bottom:18px;
            }}
            .label {{
                color:#aaa;
                font-size:12px;
                text-transform:uppercase;
            }}
            .value {{
                font-size:24px;
                margin-top:8px;
                font-weight:bold;
            }}
            table {{
                width:100%;
                border-collapse:collapse;
                font-size:14px;
            }}
            th, td {{
                padding:10px;
                border-bottom:1px solid #2a2d3a;
                text-align:left;
            }}
            th {{ color:#aaa; }}
            a {{
                color:#60a5fa;
                text-decoration:none;
            }}
            .safe {{ color:#8ff0a4; }}
            .warn {{ color:#f6d365; }}
        </style>
    </head>
    <body>
        <h1>Virtual Portfolio</h1>
        <p>7-day live-data paper trading trial. No real broker execution.</p>

        <div class="grid">
            <div class="card">
                <div class="label">Starting Capital</div>
                <div class="value">${snapshot["starting_capital"]}</div>
            </div>
            <div class="card">
                <div class="label">Cash Balance</div>
                <div class="value">${snapshot["cash_balance"]}</div>
            </div>
            <div class="card">
                <div class="label">Min Reserve Cash</div>
                <div class="value">${snapshot["min_reserve_cash"]}</div>
            </div>
            <div class="card">
                <div class="label">Max Open Trades</div>
                <div class="value">{snapshot["max_open_virtual_trades"]}</div>
            </div>
        </div>

        <div class="grid">
            <div class="card">
                <div class="label">Unrealized P&L</div>
                <div class="value">{snapshot["unrealized_pnl"]}</div>
            </div>
            <div class="card">
                <div class="label">Realized P&L</div>
                <div class="value">{snapshot["realized_pnl"]}</div>
            </div>
            <div class="card">
                <div class="label">Total Equity</div>
                <div class="value">{snapshot["total_equity"]}</div>
            </div>
            <div class="card">
                <div class="label">Reserve Rule</div>
                <div class="value">30%</div>
            </div>
        </div>

        <div class="section">
            <h2>Open Virtual Positions</h2>
            <table>
                <tr>
                    <th>Position ID</th>
                    <th>Trade ID</th>
                    <th>Symbol</th>
                    <th>Strategy</th>
                    <th>Entry Debit</th>
                    <th>Entry Credit</th>
                    <th>Status</th>
                    <th>Opened At</th>
                </tr>
                {pos_rows}
            </table>
        </div>

        <div class="section">
            <h2>Current Mark / Unrealized P&amp;L</h2>
            <table>
                <tr>
                    <th>Position ID</th>
                    <th>Trade ID</th>
                    <th>Symbol</th>
                    <th>Strategy</th>
                    <th>Current Spread Mid</th>
                    <th>Unrealized P&amp;L</th>
                </tr>
                {unreal_rows}
            </table>
        </div>

        <div class="section">
            <p class="warn">Virtual mode uses live production data but does not place broker orders.</p>
            <a href="/">Back to Dashboard</a>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(html)


@app.get("/trading-window", response_class=HTMLResponse)
def trading_window_page():
    status = trading_window_status()

    html = f"""
    <html>
    <head>
        <title>Trading Window</title>
        <style>
            body {{
                background:#0f1117;
                color:white;
                font-family:Arial;
                margin:40px;
            }}
            .section {{
                background:#171923;
                padding:22px;
                border-radius:12px;
                border:1px solid #2a2d3a;
                margin-bottom:20px;
            }}
            a {{ color:#60a5fa; }}
            pre {{
                white-space:pre-wrap;
                background:#0b0d12;
                padding:15px;
                border-radius:10px;
            }}
        </style>
    </head>
    <body>
        <h1>Trading Window</h1>
        <div class="section">
            <p><b>Dubai Time:</b> {status["now_dubai"]}</p>
            <p><b>Weekday:</b> {status["weekday"]}</p>
            <p><b>Morning Macro Window:</b> {status["morning_macro_window"]}</p>
            <p><b>US Options Window:</b> {status["us_options_window_dubai"]}</p>
            <p><b>Position Monitor Window:</b> {status["position_monitor_window_dubai"]}</p>
            <p><b>Can Open New Option Trade:</b> {status["can_open_new_option_trade"]}</p>
        </div>
        <div class="section">
            <h2>Config</h2>
            <pre>{status["config"]}</pre>
        </div>
        <a href="/">Back to Dashboard</a>
    </body>
    </html>
    """
    return HTMLResponse(html)

@app.get("/refresh-fx-history")
def refresh_fx_history():
    fetch_fx_history()
    return RedirectResponse(url="/fx-watchtower", status_code=303)

@app.get("/fx-watchtower", response_class=HTMLResponse)
def fx_watchtower():
    fx = latest_fx_regime()
    pairs = fx.get("pairs", {})

    def pair_card(pair_name):
        data = pairs.get(pair_name)
        if not data:
            return f"""
            <div class="card">
                <h3>{pair_name}</h3>
                <p>No FX data available yet.</p>
            </div>
            """

        return f"""
        <div class="card">
            <h3>{pair_name}</h3>
            <p><b>Latest Date:</b> {data.get("date")}</p>
            <p><b>Close:</b> {round(data.get("close", 0), 5)}</p>
            <p><b>5D Return:</b> {round(data.get("return_5d", 0) * 100, 2)}%</p>
            <p><b>20D Return:</b> {round(data.get("return_20d", 0) * 100, 2)}%</p>
            <p><b>20D Volatility:</b> {round(data.get("volatility_20d", 0) * 100, 2)}%</p>
            <p><b>Trend Score:</b> {data.get("trend_score")}</p>
            <p><b>Volatility Score:</b> {data.get("volatility_score")}</p>
            <p><b>Regime:</b> {data.get("regime_label")}</p>
        </div>
        """

    notes = fx.get("notes", [])
    notes_html = "".join([f"<li>{n}</li>" for n in notes]) if notes else "<li>No major FX stress note.</li>"

    regime = fx.get("macro_regime")
    color = "#16a34a" if regime == "RISK_ON" else "#f59e0b" if regime == "NEUTRAL" else "#dc2626"

    html = f"""
    <html>
    <head>
        <title>FX Macro Watchtower</title>
        <meta http-equiv="refresh" content="5">
        <style>
            body {{
                background:#0f1117;
                color:white;
                font-family:Arial;
                margin:40px;
            }}
            .grid {{
                display:grid;
                grid-template-columns:repeat(2, 1fr);
                gap:20px;
                margin-bottom:20px;
            }}
            .card, .section {{
                background:#171923;
                padding:22px;
                border-radius:12px;
                border:1px solid #2a2d3a;
                margin-bottom:20px;
            }}
            .regime {{
                background:{color};
                padding:16px;
                border-radius:12px;
                font-size:24px;
                font-weight:bold;
                display:inline-block;
            }}
            a {{
                color:#60a5fa;
            }}
            .button {{
                display:inline-block;
                padding:12px 16px;
                background:#2563eb;
                color:white;
                border-radius:10px;
                text-decoration:none;
                margin-right:10px;
            }}
        </style>
    </head>
    <body>
        <h1>FX Macro Watchtower</h1>
        <p>This uses 24-month historical USDJPY and USDCHF data to classify macro/FX backdrop.</p>

        <div class="section">
            <h2>Macro Regime</h2>
            <div class="regime">{fx.get("macro_regime")}</div>
            <p><b>Macro Score:</b> {fx.get("macro_score")}/100</p>
            <ul>{notes_html}</ul>
            <a class="button" href="/refresh-fx-history">Refresh FX Data</a>
            <a class="button" href="/">Back to Dashboard</a>
        </div>

        <div class="grid">
            {pair_card("USDJPY")}
            {pair_card("USDCHF")}
        </div>
    </body>
    </html>
    """
    return HTMLResponse(html)

@app.get("/system-health", response_class=HTMLResponse)
def system_health_page():
    health = get_system_health()
    rows = ""
    for service, status in health["services"].items():
        color = "#16a34a" if status == "active" else "#dc2626"
        rows += f"<tr><td>{service}</td><td style='color:{color};font-weight:bold;'>{status}</td></tr>"

    html = f"""
    <html>
    <head>
        <title>System Health</title>
        <style>
            body {{
                background:#0f1117;
                color:white;
                font-family:Arial;
                margin:40px;
            }}
            .section {{
                background:#171923;
                padding:22px;
                border-radius:12px;
                border:1px solid #2a2d3a;
                margin-bottom:20px;
            }}
            table {{
                width:100%;
                border-collapse:collapse;
            }}
            th, td {{
                padding:12px;
                border-bottom:1px solid #2a2d3a;
                text-align:left;
            }}
            a {{ color:#60a5fa; }}
        </style>
    </head>
    <body>
        <h1>Angad Option Desk — System Health</h1>

        <div class="section">
            <h2>Services</h2>
            <table>
                <tr><th>Service</th><th>Status</th></tr>
                {rows}
            </table>
        </div>

        <div class="section">
            <h2>Controls</h2>
            <p>Kill Switch: <b>{health["kill_switch"]}</b></p>
            <p>Auto Trade Enabled: <b>{health["auto_trade_enabled"]}</b></p>
            <p>Account Mode: <b>{health["account_mode"]}</b></p>
            <p>Scheduled Scanner Enabled: <b>{health["scheduled_scanner_enabled"]}</b></p>
            <p>Scan Interval Minutes: <b>{health["scan_interval_minutes"]}</b></p>
            <p>Broker Connected: <b>{health["broker_connected"]}</b></p>
            <p>Execution Mode: <b>{health["execution_mode"]}</b></p>
            <p>Time UTC: {health["time_utc"]}</p>
        </div>

        <a href="/">Back to dashboard</a>
    </body>
    </html>
    """
    return HTMLResponse(html)

@app.get("/pause-scanner")
def pause_scanner():
    set_scanner_enabled(False)
    return HTMLResponse("""
    <html><body style="background:#0f1117;color:white;font-family:Arial;margin:40px;">
    <h1>Scanner Paused</h1>
    <p>Scheduled scanner is now paused. Manual scan still available.</p>
    <a href="/" style="color:#60a5fa;">Back to dashboard</a>
    </body></html>
    """)

@app.get("/resume-scanner")
def resume_scanner():
    set_scanner_enabled(True)
    return HTMLResponse("""
    <html><body style="background:#0f1117;color:white;font-family:Arial;margin:40px;">
    <h1>Scanner Resumed</h1>
    <p>Scheduled scanner is now active again.</p>
    <a href="/" style="color:#60a5fa;">Back to dashboard</a>
    </body></html>
    """)

@app.get("/kill-on")
def kill_on():
    set_kill_switch(True)
    return HTMLResponse("""
    <html><body style="background:#0f1117;color:white;font-family:Arial;margin:40px;">
    <h1>Kill Switch Activated</h1>
    <p>All new trade proposals will fail risk checks while kill switch is active.</p>
    <a href="/" style="color:#60a5fa;">Back to dashboard</a>
    </body></html>
    """)

@app.get("/kill-off")
def kill_off():
    set_kill_switch(False)
    return HTMLResponse("""
    <html><body style="background:#0f1117;color:white;font-family:Arial;margin:40px;">
    <h1>Kill Switch Deactivated</h1>
    <p>Risk engine is back to normal rules.</p>
    <a href="/" style="color:#60a5fa;">Back to dashboard</a>
    </body></html>
    """)

@app.get("/run-scan")
def run_market_scan():
    run_scan()
    return RedirectResponse(url="/", status_code=303)

@app.get("/generate-sample-trade")
def generate_sample_trade():
    samples = [
        {
            "symbol": "SPY",
            "strategy": "debit_spread",
            "expiry": "35 DTE",
            "dte": 35,
            "legs": "Buy SPY call / Sell higher SPY call",
            "estimated_credit": None,
            "estimated_debit": 42,
            "max_risk": 42,
            "target_profit": 28,
            "stop_loss": 20,
            "reason": "Sample directional defined-risk debit spread."
        },
        {
            "symbol": "QQQ",
            "strategy": "put_credit_spread",
            "expiry": "32 DTE",
            "dte": 32,
            "legs": "Sell QQQ put / Buy lower QQQ put",
            "estimated_credit": 18,
            "estimated_debit": None,
            "max_risk": 82,
            "target_profit": 35,
            "stop_loss": 40,
            "reason": "Sample credit spread with risk above current $50 limit."
        },
        {
            "symbol": "TSLA",
            "strategy": "zero_dte",
            "expiry": "0 DTE",
            "dte": 0,
            "legs": "Buy TSLA weekly call",
            "estimated_credit": None,
            "estimated_debit": 75,
            "max_risk": 75,
            "target_profit": 100,
            "stop_loss": 35,
            "reason": "Sample 0DTE trade. Should be blocked."
        }
    ]

    trade = random.choice(samples)
    risk_eval = evaluate_trade(
        strategy=trade["strategy"],
        max_risk=trade["max_risk"],
        dte=trade["dte"]
    )

    final_status = "PENDING_APPROVAL" if risk_eval["passed"] else "BLOCKED"

    trade_id = create_trade(
        symbol=trade["symbol"],
        strategy=trade["strategy"],
        expiry=trade["expiry"],
        legs=trade["legs"],
        estimated_credit=trade["estimated_credit"],
        estimated_debit=trade["estimated_debit"],
        max_risk=trade["max_risk"],
        target_profit=trade["target_profit"],
        stop_loss=trade["stop_loss"],
        status=final_status,
        reason=risk_eval["reason"],
        risk_result=risk_eval["result"]
    )

    if final_status == "PENDING_APPROVAL":
        msg = f'''
<b>Trade Proposal #{trade_id}</b>

Symbol: {trade["symbol"]}
Strategy: {trade["strategy"]}
Expiry: {trade["expiry"]}
Legs: {trade["legs"]}

Max Risk: ${trade["max_risk"]}
Target Profit: ${trade["target_profit"]}
Stop Loss: ${trade["stop_loss"]}

Risk Result: {risk_eval["result"]}
Reason: {risk_eval["reason"]}

Open dashboard:
http://16.60.74.15
'''
        send_telegram_message(msg)
    else:
        msg = f'''
<b>Blocked Trade #{trade_id}</b>

Symbol: {trade["symbol"]}
Strategy: {trade["strategy"]}
Max Risk: ${trade["max_risk"]}

Risk Result: {risk_eval["result"]}
Reason: {risk_eval["reason"]}
'''
        send_telegram_message(msg)

    return {
        "created_trade_id": trade_id,
        "status": final_status,
        "risk_result": risk_eval
    }

@app.get("/trades")
def trades():
    return list_trades(50)

@app.get("/approve/{trade_id}")
def approve_trade(trade_id: int):
    update_trade_status(trade_id, "APPROVED_SIMULATION_ONLY")
    return HTMLResponse(f"""
    <html>
    <body style="background:#0f1117;color:white;font-family:Arial;margin:40px;">
        <h1>Trade #{trade_id} Approved</h1>
        <p>Simulation approval recorded. No broker connected. No trade placed.</p>
        <a href="/" style="color:#60a5fa;">Back to dashboard</a>
    </body>
    </html>
    """)

@app.get("/reject/{trade_id}")
def reject_trade(trade_id: int):
    update_trade_status(trade_id, "REJECTED")
    return HTMLResponse(f"""
    <html>
    <body style="background:#0f1117;color:white;font-family:Arial;margin:40px;">
        <h1>Trade #{trade_id} Rejected</h1>
        <p>Trade rejected. No broker connected. No trade placed.</p>
        <a href="/" style="color:#60a5fa;">Back to dashboard</a>
    </body>
    </html>
    """)

@app.get("/risk")
def risk():
    return load_yaml(os.path.join(BASE_DIR, "config", "risk_limits.yaml"))

@app.get("/symbols")
def symbols():
    return load_yaml(os.path.join(BASE_DIR, "config", "symbols.yaml"))

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "approval_required": True,
        "auto_trade_enabled": False,
        "kill_switch": False,
        "broker_connected": False,
        "time": datetime.now(timezone.utc).isoformat()
    }






@app.get("/agent-dashboard", response_class=HTMLResponse)
def agent_dashboard():
    state = get_dashboard_state()
    market = state.get("market", {})
    portfolio = state.get("portfolio", {})
    learning = state.get("learning", [])
    adaptation = state.get("adaptation", {})
    daily_objective = state.get("daily_objective", {})
    objective_live = daily_objective.get("live", {})
    objective_status = daily_objective.get("status", {})
    objective_combined = objective_live.get("combined", {})
    objective_ig = objective_live.get("ig", {})
    objective_tasty = objective_live.get("tasty", {})

    adaptation_summary = adaptation.get("summary", {})
    adaptation_symbols = adaptation.get("symbols", [])
    adaptation_strategies = adaptation.get("strategies", [])
    adaptation = state.get("adaptation", {})
    daily_objective = state.get("daily_objective", {})
    reporting = state.get("reporting", {})
    curve = state.get("curve", [])
    execution = state.get("execution", {})

    regime = market.get("regime_view", {})
    plan = market.get("session_plan", {})
    macro = market.get("macro", {})
    focus = market.get("opportunity_ranking", {}).get("top_trade_focus", [])
    opens = portfolio.get("open_positions", [])
    dyn = market.get("dynamic_universe", {})

    regime_name = regime.get("regime", "MIXED")
    day_mode = plan.get("day_mode", "-")

    regime_cls = "neutral"
    if regime_name == "RISK_ON":
        regime_cls = "positive"
    elif regime_name == "RISK_OFF":
        regime_cls = "negative"
    elif regime_name in ["EVENT_RISK", "NO_TRADE"]:
        regime_cls = "warning"

    def money(v):
        try:
            return f"${float(v):,.2f}"
        except Exception:
            return f"${v}"

    def pct(v):
        return "-" if v in (None, "") else f"{v}%"

    def tone_num(v):
        try:
            x = float(v)
            if x > 0:
                return "positive"
            if x < 0:
                return "negative"
            return "neutral"
        except Exception:
            return "neutral"

    regime_body = f"""
    <div class="metrics-grid two">
      {metric("Regime", pill(regime_name, regime_cls))}
      {metric("Day Mode", pill(day_mode, regime_cls))}
      {metric("Style", regime.get("style", "-"))}
      {metric("Confidence", regime.get("confidence", "-"))}
    </div>
    """

    portfolio_body = f"""
    <div class="metrics-grid three">
      {metric("Starting Capital", money(portfolio.get("starting_capital", 0)))}
      {metric("Cash", money(portfolio.get("cash_balance", 0)))}
      {metric("Total Equity", money(portfolio.get("total_equity", 0)))}
      {metric("Unrealized", money(portfolio.get("unrealized_pnl", 0)), tone_num(portfolio.get("unrealized_pnl", 0)))}
      {metric("Realized", money(portfolio.get("realized_pnl", 0)), tone_num(portfolio.get("realized_pnl", 0)))}
      {metric("Open Trades", str(len(opens)))}
    </div>
    """

    owner_body = f"""
    <div class="metrics-grid three">
      {metric("Withdrawal Pool", money(reporting.get("withdrawal_pool", 0)), "positive")}
      {metric("Autonomous Entries", "ON" if plan.get("autonomous_entries") else "OFF")}
      {metric("Autonomous Exits", "ON" if plan.get("autonomous_exits") else "OFF")}
      {metric("Max New Entries", plan.get("max_new_entries", "-"))}
      {metric("Max Concurrent", plan.get("max_concurrent_trades", "-"))}
      {metric("Max Deployed", str(plan.get("max_deployed_capital_pct", "-")) + "%")}
    </div>
    """

    macro_body = f"""
    <div class="macro-box">
      <div class="macro-line"><span>Headline Regime</span><strong>{macro.get("macro_regime", "-")}</strong></div>
      <div class="macro-line"><span>Risk-On Score</span><strong>{macro.get("risk_on_score", "-")}</strong></div>
      <div class="macro-line"><span>Risk-Off Score</span><strong>{macro.get("risk_off_score", "-")}</strong></div>
      <div class="macro-summary">{macro.get("summary", "-")}</div>
      <div class="macro-note">{regime.get("session_note", "-")}</div>
    </div>
    """

    focus_rows = []
    for row in focus:
        focus_rows.append([
            row.get("symbol", "-"),
            row.get("opportunity_score", "-"),
            pct(row.get("change_pct")),
            pct(row.get("spread_pct")),
            ", ".join(row.get("preferred_structures", [])),
        ])

    open_rows = []
    for row in opens[:12]:
        entry = row.get("entry_debit") or row.get("entry_credit") or "-"
        open_rows.append([
            row.get("symbol", "-"),
            row.get("strategy", "-"),
            row.get("expiry", "-"),
            entry,
            row.get("status", "-"),
        ])


    objective_live = daily_objective.get("live", {})
    objective_status = daily_objective.get("status", {})
    objective_combined = objective_live.get("combined", {})
    objective_ig = objective_live.get("ig", {})
    objective_tasty = objective_live.get("tasty", {})

    adaptation_summary = adaptation.get("summary", {})
    adaptation_symbols = adaptation.get("symbols", [])
    adaptation_strategies = adaptation.get("strategies", [])

    adapt_symbol_rows = []
    for row in adaptation_symbols[:15]:
        adapt_symbol_rows.append([
            row.get("symbol", "-"),
            row.get("bias", "-"),
            row.get("score_adjustment", "-"),
            row.get("trades", "-"),
            row.get("win_rate", "-"),
            row.get("net_pnl", "-"),
        ])

    adapt_strategy_rows = []
    for row in adaptation_strategies[:15]:
        adapt_strategy_rows.append([
            row.get("strategy", "-"),
            row.get("bias", "-"),
            row.get("score_adjustment", "-"),
            row.get("trades", "-"),
            row.get("win_rate", "-"),
            row.get("net_pnl", "-"),
        ])
    learning_rows = []
    for row in learning[:8]:
        learning_rows.append([
            row.get("symbol", "-"),
            row.get("strategy", "-"),
            row.get("realized_pnl", "-"),
            row.get("quality_tags", "-"),
            row.get("mistake_tags", "-"),
        ])

    universe_rows = []
    for row in dyn.get("eligible_symbols", [])[:10]:
        universe_rows.append([
            row.get("symbol", "-"),
            row.get("score", "-"),
            pct(row.get("change_pct")),
            pct(row.get("spread_pct")),
            row.get("volume", "-"),
        ])

    exec_rows = []
    for row in execution.get("entry_results", [])[:10]:
        exec_rows.append([
            row.get("trade_id", "-"),
            row.get("symbol", "-"),
            row.get("status", "-"),
            row.get("quantity", "-"),
            row.get("max_risk", "-"),
            row.get("confidence", "-"),
            row.get("universal_strategy", "-"),
        ])

    curve_rows = []
    equity_vals = []
    cash_vals = []
    realized_vals = []
    unrealized_vals = []

    for row in curve[-20:]:
        equity_vals.append(row.get("total_equity", 0))
        cash_vals.append(row.get("cash_balance", 0))
        realized_vals.append(row.get("realized_pnl", 0))
        unrealized_vals.append(row.get("unrealized_pnl", 0))
        curve_rows.append([
            str(row.get("timestamp", ""))[:19],
            money(row.get("cash_balance", 0)),
            money(row.get("unrealized_pnl", 0)),
            money(row.get("realized_pnl", 0)),
            money(row.get("total_equity", 0)),
        ])

    focus_changes = [row.get("change_pct", 0) for row in focus[:8]]
    focus_chart = svg_line_chart(focus_changes, height=180, stroke="#ffb648")

    equity_chart = svg_line_chart(equity_vals, height=240, stroke="#63a4ff")
    cash_equity_chart = svg_dual_line_chart(cash_vals, equity_vals, height=240)
    pnl_bar_chart = svg_bar_chart(realized_vals, unrealized_vals, height=240)

    flags_html = ""
    reasons = plan.get("reasons", [])
    if reasons:
        flags_html = "".join([f"<div class='flag-item'>{pill(r, 'warning')}</div>" for r in reasons])
    else:
        flags_html = f"<div class='flag-item'>{pill('no active risk flags', 'positive')}</div>"

    html = f"""
    <html>
    <head>
      <title>Angad Agent Dashboard</title>
      <meta http-equiv="refresh" content="15">
      <style>
        :root {{
          --bg: #09101d;
          --panel: #111a2c;
          --panel-2: #0d1525;
          --border: #22314d;
          --text: #edf3fb;
          --muted: #91a4c4;
          --green: #25c27a;
          --red: #ff6b6b;
          --amber: #ffb648;
          --blue: #63a4ff;
        }}
        * {{ box-sizing: border-box; }}
        body {{
          margin: 0;
          background:
            radial-gradient(circle at top right, rgba(70,100,180,.14), transparent 28%),
            radial-gradient(circle at top left, rgba(20,180,130,.08), transparent 22%),
            var(--bg);
          color: var(--text);
          font-family: Inter, Arial, sans-serif;
        }}
        .wrap {{ max-width: 1700px; margin: 0 auto; padding: 28px; }}
        .topbar {{ display:flex; justify-content:space-between; align-items:flex-start; gap:20px; margin-bottom:22px; }}
        .title {{ font-size:32px; font-weight:800; letter-spacing:-0.02em; margin-bottom:6px; }}
        .sub {{ color:var(--muted); font-size:13px; }}
        .top-pills {{ display:flex; gap:10px; flex-wrap:wrap; justify-content:flex-end; }}
        .grid {{ display:grid; grid-template-columns:repeat(12,1fr); gap:18px; }}
        .span-3 {{ grid-column: span 3; }}
        .span-4 {{ grid-column: span 4; }}
        .span-6 {{ grid-column: span 6; }}
        .span-8 {{ grid-column: span 8; }}
        .span-12 {{ grid-column: span 12; }}
        .card {{
          background: linear-gradient(180deg, rgba(18,27,46,.96), rgba(13,21,37,.96));
          border: 1px solid var(--border);
          border-radius: 22px;
          padding: 18px;
          box-shadow: 0 16px 50px rgba(0,0,0,.28);
          min-height: 100%;
        }}
        .card-header {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:14px; }}
        .card-title {{ font-size:16px; font-weight:800; letter-spacing:-0.01em; }}
        .card-subtitle {{ margin-top:4px; color:var(--muted); font-size:12px; }}
        .card-body {{ display:grid; gap:12px; }}
        .metrics-grid {{ display:grid; gap:10px; }}
        .metrics-grid.two {{ grid-template-columns:repeat(2,1fr); }}
        .metrics-grid.three {{ grid-template-columns:repeat(3,1fr); }}
        .metric {{
          background: rgba(9,16,29,.85);
          border: 1px solid rgba(34,49,77,.95);
          border-radius: 16px;
          padding: 14px;
        }}
        .metric-positive {{ box-shadow: inset 0 0 0 1px rgba(37,194,122,.15); }}
        .metric-negative {{ box-shadow: inset 0 0 0 1px rgba(255,107,107,.15); }}
        .metric-warning {{ box-shadow: inset 0 0 0 1px rgba(255,182,72,.15); }}
        .metric-label {{ font-size:11px; color:var(--muted); text-transform:uppercase; letter-spacing:.08em; margin-bottom:8px; }}
        .metric-value {{ font-size:20px; font-weight:800; line-height:1.15; }}
        .pill {{ display:inline-flex; align-items:center; gap:6px; padding:7px 11px; border-radius:999px; font-size:12px; font-weight:700; border:1px solid transparent; }}
        .pill-positive {{ background:rgba(37,194,122,.12); color:#8ff0bb; border-color:rgba(37,194,122,.25); }}
        .pill-negative {{ background:rgba(255,107,107,.12); color:#ffb0b0; border-color:rgba(255,107,107,.25); }}
        .pill-warning {{ background:rgba(255,182,72,.12); color:#ffd38d; border-color:rgba(255,182,72,.25); }}
        .pill-neutral {{ background:rgba(99,164,255,.10); color:#b8d6ff; border-color:rgba(99,164,255,.20); }}
        .macro-box {{ display:grid; gap:10px; }}
        .macro-line {{ display:flex; justify-content:space-between; align-items:center; padding:10px 0; border-bottom:1px solid rgba(34,49,77,.7); color:var(--muted); }}
        .macro-line strong {{ color:var(--text); font-size:14px; }}
        .macro-summary {{ margin-top:6px; font-size:14px; line-height:1.45; }}
        .macro-note {{ color:#c7d4ea; font-size:13px; line-height:1.45; background:rgba(9,16,29,.7); border:1px solid rgba(34,49,77,.8); border-radius:14px; padding:12px; }}
        .flags {{ display:flex; flex-wrap:wrap; gap:10px; }}
        .flag-item {{ display:inline-flex; }}
        .table-wrap {{ width:100%; overflow-x:auto; }}
        .desk-table {{ width:100%; border-collapse:collapse; font-size:13px; }}
        .desk-table th, .desk-table td {{ padding:12px 8px; border-bottom:1px solid rgba(34,49,77,.8); text-align:left; white-space:nowrap; }}
        .desk-table th {{ color:var(--muted); font-size:11px; text-transform:uppercase; letter-spacing:.08em; }}
        .desk-table tr:hover td {{ background:rgba(255,255,255,.02); }}
        .chart-box {{
          background: rgba(9,16,29,.70);
          border: 1px solid rgba(34,49,77,.85);
          border-radius: 18px;
          padding: 10px;
        }}
        @media (max-width: 1200px) {{
          .span-3,.span-4,.span-6,.span-8,.span-12 {{ grid-column: span 12; }}
          .metrics-grid.three,.metrics-grid.two {{ grid-template-columns:1fr; }}
          .topbar {{ flex-direction:column; }}
          .top-pills {{ justify-content:flex-start; }}
        }}
      </style>
    </head>
    <body>
      <div class="wrap">
        <div class="topbar">
          <div>
            <div class="title">Angad Autonomous Desk</div>
            <div class="sub">Market prep · ranked universe · autonomous execution · exit intelligence · learning memory</div>
          </div>
          <div class="top-pills">
            {pill(regime_name, regime_cls)}
            {pill(day_mode, regime_cls)}
            {pill("Autonomous Entries ON" if plan.get("autonomous_entries") else "Autonomous Entries OFF", "positive" if plan.get("autonomous_entries") else "warning")}
            {pill("Autonomous Exits ON" if plan.get("autonomous_exits") else "Autonomous Exits OFF", "positive" if plan.get("autonomous_exits") else "warning")}
            <a class="linkbtn" href="/agent-dashboard">Main Dashboard</a>
          <a class="linkbtn" href="/agent-research">Research</a>
          <a class="linkbtn" href="/ig-desk">IG Desk</a>
            <a class="linkbtn" href="/tasty-virtual-book">Tasty Virtual</a>
            <a class="linkbtn" href="/lane-capital">Lane Capital</a>
        </div>
        </div>

        <div class="grid">
          <div class="span-4">{card("Regime", regime_body, "Daily operating posture")}</div>
          <div class="span-4">{card("Portfolio", portfolio_body, "Capital and book state")}</div>
          <div class="span-4">{card("Owner Contract", owner_body, "Profit extraction and control layer")}</div>

          <div class="span-8">{card("Equity Curve", f"<div class='chart-box'>{equity_chart}</div>", "Total equity progression")}</div>
          <div class="span-4">{card("Risk Flags", f"<div class='flags'>{flags_html}</div><div class='chart-box'>{focus_chart}</div>", "System guardrails + focus momentum")}</div>

          <div class="span-6">{card("Cash vs Equity", f"<div class='chart-box'>{cash_equity_chart}</div>", "Liquidity vs book value")}</div>
          <div class="span-6">{card("P&L Profile", f"<div class='chart-box'>{pnl_bar_chart}</div>", "Realized vs unrealized progression")}</div>

          <div class="span-6">{card("Macro Summary", macro_body, "Cross-session context and tone")}</div>
          <div class="span-6">{card("Top Focus", table(["Symbol","Score","Chg %","Spread %","Structures"], focus_rows), "Best-ranked opportunities for the session")}</div>

          <div class="span-6">{card("Tradable Universe", table(["Symbol","Score","Chg %","Spread %","Volume"], universe_rows), "Eligible symbols after filtering")}</div>
          <div class="span-6">{card("Execution Log", table(["Trade ID","Symbol","Status","Qty","Max Risk","Confidence","Strategy"], exec_rows), "Latest autonomous entry actions")}</div>

          <div class="span-6">{card("Open Positions", table(["Symbol","Strategy","Expiry","Entry","Status"], open_rows), "Current live virtual book")}</div>
          <div class="span-6">{card("Learning Snapshot", table(["Symbol","Strategy","P&L","Quality Tags","Mistake Tags"], learning_rows), "Recent learning memory")}</div>

          <div class="span-12">{card("Equity Log Detail", table(["Time","Cash","Unrealized","Realized","Equity"], curve_rows), "Recent checkpoints and accounting trail")}</div>
        </div>
      </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html)



@app.get("/agent-research", response_class=HTMLResponse)
def agent_research():
    state = get_research_state()
    market = state.get("market", {})
    proposals = state.get("recent_trade_proposals", [])
    status_breakdown = state.get("proposal_status_breakdown", [])
    execution = state.get("execution", {})
    open_positions = state.get("open_positions", [])
    exit_decisions = state.get("exit_decisions", [])
    learning = state.get("learning", [])
    adaptation = state.get("adaptation", {})
    daily_objective = state.get("daily_objective", {})
    objective_live = daily_objective.get("live", {})
    objective_status = daily_objective.get("status", {})
    objective_combined = objective_live.get("combined", {})
    objective_ig = objective_live.get("ig", {})
    objective_tasty = objective_live.get("tasty", {})

    adaptation_summary = adaptation.get("summary", {})
    adaptation_symbols = adaptation.get("symbols", [])
    adaptation_strategies = adaptation.get("strategies", [])

    regime = market.get("regime_view", {})
    plan = market.get("session_plan", {})
    top_opps = plan.get("top_opportunities", [])
    universal_map = plan.get("universal_strategy_map", [])

    def money(v):
        try:
            return f"${float(v):,.2f}"
        except Exception:
            return str(v)

    opp_rows = []
    for row in top_opps[:12]:
        opp_rows.append([
            row.get("symbol", "-"),
            row.get("opportunity_score", "-"),
            row.get("change_pct", "-"),
            row.get("spread_pct", "-"),
            ", ".join(row.get("preferred_structures", [])),
        ])

    strat_rows = []
    for row in universal_map[:12]:
        top_choices = row.get("top_strategy_choices", [])[:3]
        exec_choices = row.get("execution_ready_choices", [])[:2]
        strat_rows.append([
            row.get("symbol", "-"),
            row.get("market_view", {}).get("direction", "-"),
            row.get("market_view", {}).get("vol_view", "-"),
            row.get("market_view", {}).get("shape", "-"),
            " | ".join([f"{x.get('strategy_name')} ({x.get('score')})" for x in top_choices]),
            " | ".join([f"{x.get('strategy_name')} ({x.get('score')})" for x in exec_choices]),
        ])

    status_rows = []
    for row in status_breakdown:
        status_rows.append([row.get("status", "-"), row.get("cnt", "-")])

    proposal_rows = []
    for row in proposals[:80]:
        proposal_rows.append([
            row.get("id", "-"),
            row.get("symbol", "-"),
            row.get("strategy", "-"),
            row.get("status", "-"),
            money(row.get("max_risk", 0)),
            str(row.get("created_at", ""))[:19],
        ])

    exec_rows = []
    for row in execution.get("entry_results", [])[:20]:
        exec_rows.append([
            row.get("trade_id", "-"),
            row.get("symbol", "-"),
            row.get("status", "-"),
            row.get("quantity", "-"),
            money(row.get("max_risk", 0)),
            row.get("universal_strategy", "-"),
            row.get("selection_mode", "-"),
        ])

    open_rows = []
    for row in open_positions[:20]:
        open_rows.append([
            row.get("id", "-"),
            row.get("trade_id", "-"),
            row.get("symbol", "-"),
            row.get("strategy", "-"),
            row.get("quantity", "-"),
            str(row.get("opened_at", ""))[:19],
            row.get("status", "-"),
        ])

    guard_rows = []
    for row in exit_decisions[:20]:
        guard_rows.append([
            row.get("position_id", "-"),
            row.get("symbol", "-"),
            row.get("strategy", "-"),
            row.get("quantity", "-"),
            row.get("action", "-"),
            row.get("quote_status", "-"),
            row.get("reason", "-"),
        ])

    adapt_symbol_rows = []
    for row in adaptation_symbols[:15]:
        adapt_symbol_rows.append([
            row.get("symbol", "-"),
            row.get("bias", "-"),
            row.get("score_adjustment", "-"),
            row.get("trades", "-"),
            row.get("win_rate", "-"),
            row.get("net_pnl", "-"),
        ])

    adapt_strategy_rows = []
    for row in adaptation_strategies[:15]:
        adapt_strategy_rows.append([
            row.get("strategy", "-"),
            row.get("bias", "-"),
            row.get("score_adjustment", "-"),
            row.get("trades", "-"),
            row.get("win_rate", "-"),
            row.get("net_pnl", "-"),
        ])

    learning_rows = []
    for row in learning[:20]:
        learning_rows.append([
            row.get("symbol", "-"),
            row.get("strategy", "-"),
            row.get("realized_pnl", "-"),
            row.get("quality_tags", "-"),
            row.get("mistake_tags", "-"),
            row.get("tomorrow_note", "-"),
        ])

    html = f"""
    <html>
    <head>
      <title>Agent Research</title>
      <meta http-equiv="refresh" content="20">
      <style>
        :root {{
          --bg: #08101d;
          --panel: #111a2c;
          --border: #24324f;
          --text: #edf3fb;
          --muted: #91a4c4;
          --green: #25c27a;
          --red: #ff6b6b;
          --amber: #ffb648;
          --blue: #63a4ff;
        }}
        * {{ box-sizing: border-box; }}
        body {{
          margin: 0;
          background: var(--bg);
          color: var(--text);
          font-family: Inter, Arial, sans-serif;
        }}
        .wrap {{
          max-width: 1750px;
          margin: 0 auto;
          padding: 28px;
        }}
        .topbar {{
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          gap: 20px;
          margin-bottom: 22px;
        }}
        .title {{
          font-size: 30px;
          font-weight: 800;
          margin-bottom: 6px;
        }}
        .sub {{
          color: var(--muted);
          font-size: 13px;
        }}
        .links {{
          display: flex;
          gap: 10px;
          flex-wrap: wrap;
        }}
        .linkbtn {{
          display: inline-flex;
          text-decoration: none;
          color: #cfe2ff;
          background: rgba(99,164,255,.10);
          border: 1px solid rgba(99,164,255,.20);
          border-radius: 999px;
          padding: 8px 12px;
          font-size: 12px;
          font-weight: 700;
        }}
        .grid {{
          display: grid;
          grid-template-columns: repeat(12, 1fr);
          gap: 18px;
        }}
        .span-4 {{ grid-column: span 4; }}
        .span-6 {{ grid-column: span 6; }}
        .span-12 {{ grid-column: span 12; }}
        .card {{
          background: linear-gradient(180deg, rgba(18,27,46,.96), rgba(13,21,37,.96));
          border: 1px solid var(--border);
          border-radius: 22px;
          padding: 18px;
          box-shadow: 0 16px 50px rgba(0,0,0,.28);
        }}
        .card-title {{
          font-size: 16px;
          font-weight: 800;
          margin-bottom: 6px;
        }}
        .card-sub {{
          color: var(--muted);
          font-size: 12px;
          margin-bottom: 12px;
        }}
        .mini-grid {{
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 10px;
        }}
        .metric {{
          background: rgba(9,16,29,.85);
          border: 1px solid rgba(34,49,77,.95);
          border-radius: 16px;
          padding: 14px;
        }}
        .metric-label {{
          font-size: 11px;
          color: var(--muted);
          text-transform: uppercase;
          letter-spacing: .08em;
          margin-bottom: 8px;
        }}
        .metric-value {{
          font-size: 18px;
          font-weight: 800;
        }}
        .table-wrap {{
          width: 100%;
          overflow-x: auto;
        }}
        table {{
          width: 100%;
          border-collapse: collapse;
          font-size: 13px;
        }}
        th, td {{
          padding: 11px 8px;
          border-bottom: 1px solid rgba(34,49,77,.8);
          text-align: left;
          vertical-align: top;
          white-space: nowrap;
        }}
        th {{
          color: var(--muted);
          font-size: 11px;
          text-transform: uppercase;
          letter-spacing: .08em;
        }}
        tr:hover td {{
          background: rgba(255,255,255,.02);
        }}
        @media (max-width: 1200px) {{
          .span-4, .span-6, .span-12 {{
            grid-column: span 12;
          }}
          .mini-grid {{
            grid-template-columns: 1fr;
          }}
        }}
      </style>
    </head>
    <body>
      <div class="wrap">
        <div class="topbar">
          <div>
            <div class="title">Agent Research & Trade Guard</div>
            <div class="sub">Daily research trail · proposal audit · execution trace · exit protection visibility</div>
          </div>
          <div class="links">
            <a class="linkbtn" href="/agent-dashboard">Main Dashboard</a>
            <a class="linkbtn" href="/agent-research">Research</a>
            <a class="linkbtn" href="/ig-desk">IG Desk</a>
            <a class="linkbtn" href="/tasty-virtual-book">Tasty Virtual</a>
            <a class="linkbtn" href="/lane-capital">Lane Capital</a>
          </div>
        </div>

        <div class="grid">
          <div class="span-6">
            <div class="card">
              <div class="card-title">Research Summary</div>
              <div class="card-sub">What the agent thinks the market looks like today</div>
              <div class="mini-grid">
                <div class="metric"><div class="metric-label">Regime</div><div class="metric-value">{regime.get("regime", "-")}</div></div>
                <div class="metric"><div class="metric-label">Style</div><div class="metric-value">{regime.get("style", "-")}</div></div>
                <div class="metric"><div class="metric-label">Confidence</div><div class="metric-value">{regime.get("confidence", "-")}</div></div>
                <div class="metric"><div class="metric-label">Day Mode</div><div class="metric-value">{plan.get("day_mode", "-")}</div></div>
                <div class="metric"><div class="metric-label">Max New Entries</div><div class="metric-value">{plan.get("max_new_entries", "-")}</div></div>
                <div class="metric"><div class="metric-label">Focus Symbols</div><div class="metric-value">{", ".join(plan.get("focus_symbols", [])) or "-"}</div></div>
              </div>
            </div>
          </div>

          <div class="span-6">
            <div class="card">
              <div class="card-title">Proposal Status Breakdown</div>
              <div class="card-sub">How many trades were created, blocked, watched, executed, or ignored</div>
              <div class="table-wrap">
                <table>
                  <thead><tr><th>Status</th><th>Count</th></tr></thead>
                  <tbody>
                    {''.join([f"<tr><td>{r[0]}</td><td>{r[1]}</td></tr>" for r in status_rows]) or "<tr><td colspan='2'>No data.</td></tr>"}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <div class="span-12">
            <div class="card">
              <div class="card-title">Top Opportunities</div>
              <div class="card-sub">What the agent researched and ranked highest</div>
              <div class="table-wrap">
                <table>
                  <thead><tr><th>Symbol</th><th>Score</th><th>Chg %</th><th>Spread %</th><th>Preferred Structures</th></tr></thead>
                  <tbody>
                    {''.join([f"<tr>{''.join([f'<td>{c}</td>' for c in row])}</tr>" for row in opp_rows]) or "<tr><td colspan='5'>No data.</td></tr>"}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <div class="span-12">
            <div class="card">
              <div class="card-title">Universal Strategy Map</div>
              <div class="card-sub">What the agent considered strategically for each focus symbol</div>
              <div class="table-wrap">
                <table>
                  <thead><tr><th>Symbol</th><th>Direction</th><th>Vol View</th><th>Shape</th><th>Top Strategy Choices</th><th>Execution Ready</th></tr></thead>
                  <tbody>
                    {''.join([f"<tr>{''.join([f'<td>{c}</td>' for c in row])}</tr>" for row in strat_rows]) or "<tr><td colspan='6'>No data.</td></tr>"}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <div class="span-12">
            <div class="card">
              <div class="card-title">Recent Trade Proposals</div>
              <div class="card-sub">What the agent visualised / created throughout the day</div>
              <div class="table-wrap">
                <table>
                  <thead><tr><th>ID</th><th>Symbol</th><th>Strategy</th><th>Status</th><th>Max Risk</th><th>Created</th></tr></thead>
                  <tbody>
                    {''.join([f"<tr>{''.join([f'<td>{c}</td>' for c in row])}</tr>" for row in proposal_rows]) or "<tr><td colspan='6'>No data.</td></tr>"}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <div class="span-12">
            <div class="card">
              <div class="card-title">Execution Log</div>
              <div class="card-sub">What was actually selected and sent for execution</div>
              <div class="table-wrap">
                <table>
                  <thead><tr><th>Trade ID</th><th>Symbol</th><th>Status</th><th>Qty</th><th>Risk</th><th>Strategy</th><th>Mode</th></tr></thead>
                  <tbody>
                    {''.join([f"<tr>{''.join([f'<td>{c}</td>' for c in row])}</tr>" for row in exec_rows]) or "<tr><td colspan='7'>No data.</td></tr>"}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <div class="span-6">
            <div class="card">
              <div class="card-title">Open Positions</div>
              <div class="card-sub">Current live book</div>
              <div class="table-wrap">
                <table>
                  <thead><tr><th>Position ID</th><th>Trade ID</th><th>Symbol</th><th>Strategy</th><th>Qty</th><th>Opened</th><th>Status</th></tr></thead>
                  <tbody>
                    {''.join([f"<tr>{''.join([f'<td>{c}</td>' for c in row])}</tr>" for row in open_rows]) or "<tr><td colspan='7'>No open positions.</td></tr>"}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <div class="span-6">
            <div class="card">
              <div class="card-title">Exit Protection / Trade Guard</div>
              <div class="card-sub">Grace period, quote validity, exit eligibility and current action</div>
              <div class="table-wrap">
                <table>
                  <thead><tr><th>Position ID</th><th>Symbol</th><th>Strategy</th><th>Qty</th><th>Action</th><th>Quote Status</th><th>Reason</th></tr></thead>
                  <tbody>
                    {''.join([f"<tr>{''.join([f'<td>{c}</td>' for c in row])}</tr>" for row in guard_rows]) or "<tr><td colspan='7'>No guarded positions.</td></tr>"}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <div class="span-12">
            <div class="card">
              <div class="card-title">Combined Daily Objective Controller</div>
              <div class="card-sub">Shared target across IG + Tastytrade based on combined starting equity</div>
              <div class="mini-grid">
                <div class="metric"><div class="metric-label">Combined Start Equity</div><div class="metric-value">{objective_combined.get("start_equity", "-")}</div></div>
                <div class="metric"><div class="metric-label">Combined Current Equity</div><div class="metric-value">{objective_combined.get("current_equity", "-")}</div></div>
                <div class="metric"><div class="metric-label">Combined Day P&L</div><div class="metric-value">{objective_combined.get("day_pnl", "-")}</div></div>
                <div class="metric"><div class="metric-label">1% Target Amount</div><div class="metric-value">{objective_combined.get("target_amount", "-")}</div></div>
                <div class="metric"><div class="metric-label">Target Progress %</div><div class="metric-value">{objective_combined.get("target_progress_pct", "-")}</div></div>
                <div class="metric"><div class="metric-label">Withdrawal Pool Locked</div><div class="metric-value">{(daily_objective.get("withdrawal_pool") or {}).get("locked_amount", "-")}</div></div>
                <div class="metric"><div class="metric-label">IG Day P&L</div><div class="metric-value">{objective_ig.get("day_pnl", "-")}</div></div>
                <div class="metric"><div class="metric-label">Tasty Day P&L</div><div class="metric-value">{objective_tasty.get("day_pnl", "-")}</div></div>
                <div class="metric"><div class="metric-label">Capital Usage %</div><div class="metric-value">{objective_combined.get("capital_usage_pct", "-")}</div></div>
                <div class="metric"><div class="metric-label">Soft Locked</div><div class="metric-value">{objective_status.get("soft_locked", False)}</div></div>
                <div class="metric"><div class="metric-label">Hard Stopped</div><div class="metric-value">{objective_status.get("hard_stopped", False)}</div></div>
                <div class="metric"><div class="metric-label">Usage Blocked</div><div class="metric-value">{objective_combined.get("usage_blocked", False)}</div></div>
              </div>
            </div>
          </div>

          <div class="span-12">
            <div class="card">
              <div class="card-title">Adaptive Learning Summary</div>
              <div class="card-sub">What the agent will promote or penalize next session</div>
              <div class="mini-grid">
                <div class="metric"><div class="metric-label">Promoted Symbols</div><div class="metric-value">{", ".join(adaptation_summary.get("promoted_symbols", [])) or "-"}</div></div>
                <div class="metric"><div class="metric-label">Penalized Symbols</div><div class="metric-value">{", ".join(adaptation_summary.get("penalized_symbols", [])) or "-"}</div></div>
                <div class="metric"><div class="metric-label">Promoted Strategies</div><div class="metric-value">{", ".join(adaptation_summary.get("promoted_strategies", [])) or "-"}</div></div>
              </div>
            </div>
          </div>

          <div class="span-6">
            <div class="card">
              <div class="card-title">Symbol Adaptation</div>
              <div class="card-sub">Symbols strengthened or weakened by learning</div>
              <div class="table-wrap">
                <table>
                  <thead><tr><th>Symbol</th><th>Bias</th><th>Adj</th><th>Trades</th><th>Win Rate</th><th>Net P&L</th></tr></thead>
                  <tbody>
                    {''.join([f"<tr>{''.join([f'<td>{c}</td>' for c in row])}</tr>" for row in adapt_symbol_rows]) or "<tr><td colspan='6'>No data.</td></tr>"}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <div class="span-6">
            <div class="card">
              <div class="card-title">Strategy Adaptation</div>
              <div class="card-sub">Strategy families promoted or penalized by outcomes</div>
              <div class="table-wrap">
                <table>
                  <thead><tr><th>Strategy</th><th>Bias</th><th>Adj</th><th>Trades</th><th>Win Rate</th><th>Net P&L</th></tr></thead>
                  <tbody>
                    {''.join([f"<tr>{''.join([f'<td>{c}</td>' for c in row])}</tr>" for row in adapt_strategy_rows]) or "<tr><td colspan='6'>No data.</td></tr>"}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <div class="span-12">
            <div class="card">
              <div class="card-title">Learning Notes</div>
              <div class="card-sub">What the agent should remember for tomorrow</div>
              <div class="table-wrap">
                <table>
                  <thead><tr><th>Symbol</th><th>Strategy</th><th>P&L</th><th>Quality</th><th>Mistakes</th><th>Tomorrow Note</th></tr></thead>
                  <tbody>
                    {''.join([f"<tr>{''.join([f'<td>{c}</td>' for c in row])}</tr>" for row in learning_rows]) or "<tr><td colspan='6'>No learning data.</td></tr>"}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html)




@app.get("/ig-desk", response_class=HTMLResponse)
def ig_desk():
    takeover = takeover_view()
    snap = get_ig_cached_snapshot()
    session_state = takeover.get("session_state", {}) or get_ig_session_state()
    carry_policy = takeover.get("carry_policy", {})
    regime_state = takeover.get("regime_state", {})
    entry_expression = takeover.get("entry_expression", {})
    asia_playbook = takeover.get("asia_playbook", {})
    execution_sizing = takeover.get("execution_sizing", {})
    forced_flatten_plan = takeover.get("forced_flatten_plan", {})
    throttle = takeover.get("throttle_status", {})
    close_recon = takeover.get("close_reconciliation", {})
    broker_transition = takeover.get("broker_transition", {})
    monday_monitor = takeover.get("monday_monitor", {})
    transition_worker = takeover.get("transition_worker", {})
    outcome_sync = takeover.get("outcome_sync", {})
    outcome_scoring = takeover.get("outcome_scoring", {})
    adaptive_review = takeover.get("adaptive_review", {})
    adaptive_behavior = takeover.get("adaptive_behavior", {})
    portfolio_intelligence = takeover.get("portfolio_intelligence", {})
    execution_quality = takeover.get("execution_quality", {})
    market_perception = takeover.get("market_perception", {})
    self_tuning = takeover.get("self_tuning", {})
    decision_audit = takeover.get("decision_audit", {})
    sunday_checklist = takeover.get("sunday_checklist", {})
    sunday_final_report = takeover.get("sunday_final_report", {})
    preopen_action_plan = takeover.get("preopen_action_plan", {})
    preopen_action_summary = takeover.get("preopen_action_summary", {})
    preopen_window_policy = takeover.get("preopen_window_policy", {})
    preopen_cooldown = takeover.get("preopen_cooldown", {})
    preopen_transition_simulation = takeover.get("preopen_transition_simulation", {})
    no_trade = get_no_trade_reasons()
    learning_summary = takeover.get("learning_summary", summarize_memory())
    latest_review = takeover.get("latest_daily_review", latest_daily_review())
    managed = takeover.get("managed_positions", [])
    positions = ((takeover.get("positions") or {}).get("positions") or [])
    acct = takeover.get("account_snapshot", {}) or {}
    open_pnl = acct.get("open_pnl", 0.0)
    balance = acct.get("balance", 0.0)
    equity = acct.get("equity", 0.0)

    def pill(label, value, tone="neutral"):
        bg = {
            "good": "rgba(36,208,122,.14)",
            "bad": "rgba(255,111,111,.14)",
            "warn": "rgba(255,182,72,.14)",
            "info": "rgba(99,164,255,.14)",
            "neutral": "rgba(255,255,255,.06)",
        }.get(tone, "rgba(255,255,255,.06)")
        border = {
            "good": "rgba(36,208,122,.35)",
            "bad": "rgba(255,111,111,.35)",
            "warn": "rgba(255,182,72,.35)",
            "info": "rgba(99,164,255,.35)",
            "neutral": "rgba(255,255,255,.10)",
        }.get(tone, "rgba(255,255,255,.10)")
        return f'<span class="pill" style="background:{bg};border-color:{border}"><b>{label}:</b>&nbsp;{value}</span>'

    session_pills = "".join([
        pill("Session", session_state.get("session", "-"), "info"),
        pill("Market Open", str(session_state.get("market_open", False)), "good" if session_state.get("market_open") else "bad"),
        pill("Liquidity", session_state.get("liquidity", "-"), "warn"),
        pill("Entry Mode", session_state.get("entry_mode", "-"), "info" if session_state.get("entry_mode") not in ("blocked",) else "bad"),
        pill("Carry Bias", session_state.get("carry_bias", "-"), "warn"),
    ])

    carry_pills = "".join([
        pill("Flatten All", str(carry_policy.get("flatten_all", False)), "bad" if carry_policy.get("flatten_all") else "neutral"),
        pill("Reduce Only", str(carry_policy.get("reduce_only", False)), "warn" if carry_policy.get("reduce_only") else "neutral"),
        pill("Allow New Entries", str(carry_policy.get("allow_new_entries", False)), "good" if carry_policy.get("allow_new_entries") else "bad"),
        pill("Probe Only", str(carry_policy.get("probe_only", False)), "warn" if carry_policy.get("probe_only") else "neutral"),
        pill("Max Carry", str(carry_policy.get("max_carry_positions", 0)), "info"),
    ])

    regime_pills = "".join([
        pill("Regime", regime_state.get("regime", "-"), "info"),
        pill("Conviction", regime_state.get("conviction_score", "-"), "good" if float(regime_state.get("conviction_score", 0) or 0) >= 65 else "warn"),
        pill("Momentum", regime_state.get("momentum_score", "-"), "info"),
        pill("Structure", regime_state.get("structure_score", "-"), "info"),
        pill("Direction Bias", regime_state.get("direction_bias", "-"), "neutral"),
    ])

    expr_pills = "".join([
        pill("Entry Style", entry_expression.get("entry_style", "-"), "info"),
        pill("Size Multiplier", entry_expression.get("size_multiplier", "-"), "warn"),
        pill("Probe Only", str(entry_expression.get("probe_only", False)), "warn" if entry_expression.get("probe_only") else "neutral"),
        pill("Aggressiveness", entry_expression.get("aggressiveness", "-"), "info"),
    ])

    cache_pills = "".join([
        pill("Cache", snap.get("cache_status", "-"), "info"),
        pill("TTL", str(snap.get("ttl_seconds", "-")), "neutral"),
        pill("Broker OK", str(snap.get("ok", False)), "good" if snap.get("ok") else "bad"),
        pill("Open Positions", str(((snap.get("positions") or {}).get("count")) or 0), "info"),
    ])

    asia_pills = "".join([
        pill("Asia Bias", asia_playbook.get("action_bias", "-"), "info"),
        pill("Probe Allowed", str(asia_playbook.get("probe_allowed", False)), "warn" if asia_playbook.get("probe_allowed") else "neutral"),
        pill("Scale Allowed", str(asia_playbook.get("scale_allowed", False)), "good" if asia_playbook.get("scale_allowed") else "neutral"),
        pill("Spread Quality", asia_playbook.get("spread_quality", "-"), "warn"),
        pill("Momentum Quality", asia_playbook.get("momentum_quality", "-"), "info"),
        pill("Asia Size", str(asia_playbook.get("size_multiplier", "-")), "warn"),
    ])

    sizing_pills = "".join([
        pill("Entry Allowed", str(execution_sizing.get("entry_allowed", False)), "good" if execution_sizing.get("entry_allowed") else "bad"),
        pill("Deployment", execution_sizing.get("deployment_mode", "-"), "info"),
        pill("Size Multiplier", str(execution_sizing.get("size_multiplier", "-")), "warn"),
        pill("Block Reasons", ", ".join(execution_sizing.get("block_reasons", [])) or "None", "bad" if execution_sizing.get("block_reasons") else "neutral"),
    ])

    flatten_pills = "".join([
        pill("Flatten Candidates", str(forced_flatten_plan.get("total_candidates", 0)), "bad"),
        pill("Batch Size", str(forced_flatten_plan.get("batch_size", 0)), "warn"),
    ])

    throttle_pills = "".join([
        pill("Throttle Active", str(throttle.get("active", False)), "bad" if throttle.get("active") else "good"),
        pill("Remaining Sec", str(throttle.get("remaining_seconds", 0)), "warn"),
        pill("Last Reason", str(throttle.get("last_reason", "-")), "bad" if throttle.get("last_reason") else "neutral"),
        pill("Flatten Pending", str(throttle.get("flatten_pending", False)), "warn" if throttle.get("flatten_pending") else "neutral"),
    ])

    recon_pills = "".join([
        pill("Pending Closes", str(close_recon.get("pending_count", 0)), "warn"),
        pill("Confirmed Closes", str(close_recon.get("confirmed_count", 0)), "good"),
        pill("Rejected Closes", str(close_recon.get("rejected_count", 0)), "bad"),
    ])

    monday_pills = "".join([
        pill("Transition", broker_transition.get("transition_state", "-"), "info"),
        pill("Deploy Gate", str(broker_transition.get("deploy_gate_open", False)), "good" if broker_transition.get("deploy_gate_open") else "bad"),
        pill("Pending Closes", str(broker_transition.get("pending_closes", 0)), "warn"),
        pill("Broker OK", str(broker_transition.get("broker_ok", False)), "good" if broker_transition.get("broker_ok") else "bad"),
        pill("Ready For Deploy", str(monday_monitor.get("ready_for_deploy", False)), "good" if monday_monitor.get("ready_for_deploy") else "bad"),
    ])

    transition_pills = "".join([
        pill("Worker Service", transition_worker.get("service_name", "-"), "info"),
        pill("Role", transition_worker.get("expected_role", "-"), "neutral"),
    ])

    adaptive_pills = "".join([
        pill("Open Sync Count", str(outcome_sync.get("synced_count", 0)), "info"),
        pill("Scorecard Count", str(((adaptive_review.get("scorecards") or {}).get("scorecard_count", 0))), "info"),
        pill("Completed", str(((adaptive_review.get("scorecards") or {}).get("completed_count", 0))), "warn"),
        pill("Win Rate %", str(((adaptive_review.get("scorecards") or {}).get("win_rate_pct", 0.0))), "good" if float(((adaptive_review.get("scorecards") or {}).get("win_rate_pct", 0.0) or 0)) >= 50 else "warn"),
    ])

    adaptive_behavior_pills = "".join([
        pill("Adaptive Enabled", str(adaptive_behavior.get("adaptive_enabled", False)), "good" if adaptive_behavior.get("adaptive_enabled") else "neutral"),
        pill("Deployment Bias", str(adaptive_behavior.get("deployment_bias", "-")), "info"),
        pill("Size Adj", str(adaptive_behavior.get("size_adjustment", 1.0)), "warn"),
        pill("Conf Adj", str(adaptive_behavior.get("confidence_adjustment", 0.0)), "info"),
        pill("Should Reduce", str(adaptive_behavior.get("should_reduce", False)), "warn" if adaptive_behavior.get("should_reduce") else "neutral"),
        pill("Should Block", str(adaptive_behavior.get("should_block", False)), "bad" if adaptive_behavior.get("should_block") else "neutral"),
    ])

    portfolio_pills = "".join([
        pill("Positions", str(portfolio_intelligence.get("total_positions", 0)), "info"),
        pill("Fragility", str(portfolio_intelligence.get("fragility_score", 0.0)), "warn"),
        pill("Book Bias", str(portfolio_intelligence.get("deployment_bias", "-")), "info"),
        pill("Port Size Adj", str(portfolio_intelligence.get("size_adjustment", 1.0)), "warn"),
        pill("Should Reduce", str(portfolio_intelligence.get("should_reduce", False)), "warn" if portfolio_intelligence.get("should_reduce") else "neutral"),
        pill("Block New", str(portfolio_intelligence.get("should_block_new", False)), "bad" if portfolio_intelligence.get("should_block_new") else "neutral"),
    ])

    execution_quality_pills = "".join([
        pill("Quality Score", str(execution_quality.get("quality_score", 0.0)), "good" if float(execution_quality.get("quality_score", 0.0) or 0) >= 75 else "warn"),
        pill("Exec Bias", str(execution_quality.get("deployment_bias", "-")), "info"),
        pill("Exec Size Adj", str(execution_quality.get("size_adjustment", 1.0)), "warn"),
        pill("Should Delay", str(execution_quality.get("should_delay", False)), "warn" if execution_quality.get("should_delay") else "neutral"),
        pill("Should Block", str(execution_quality.get("should_block", False)), "bad" if execution_quality.get("should_block") else "neutral"),
        pill("Pending Closes", str(execution_quality.get("pending_closes", 0)), "warn"),
    ])

    market_perception_pills = "".join([
        pill("Perception", str(market_perception.get("perception_state", "-")), "info"),
        pill("Breakout Bias", str(market_perception.get("breakout_bias", "-")), "info"),
        pill("Directional Pressure", str(market_perception.get("directional_pressure", "-")), "info"),
        pill("Perception Size Adj", str(market_perception.get("size_adjustment", 1.0)), "warn"),
        pill("Should Reduce", str(market_perception.get("should_reduce", False)), "warn" if market_perception.get("should_reduce") else "neutral"),
        pill("Should Block", str(market_perception.get("should_block", False)), "bad" if market_perception.get("should_block") else "neutral"),
    ])

    self_tuning_pills = "".join([
        pill("Master Score", str(self_tuning.get("master_score", 0.0)), "good" if float(self_tuning.get("master_score", 0.0) or 0) >= 70 else "warn"),
        pill("Verdict", str(self_tuning.get("deploy_verdict", "-")), "info"),
        pill("Threshold", str(self_tuning.get("threshold_state", "-")), "info"),
        pill("Final Size Mult", str(self_tuning.get("final_size_multiplier", 0.0)), "warn"),
        pill("Conf Adj", str(self_tuning.get("final_confidence_adjustment", 0.0)), "info"),
        pill("Should Block", str(self_tuning.get("should_block", False)), "bad" if self_tuning.get("should_block") else "neutral"),
    ])

    decision_audit_pills = "".join([
        pill("Audit Count", str(decision_audit.get("audit_count", 0)), "info"),
        pill("Recent Count", str(decision_audit.get("recent_count", 0)), "info"),
        pill("Avg Score", str(decision_audit.get("avg_master_score", 0.0)), "warn"),
        pill("Avg Size", str(decision_audit.get("avg_final_size_multiplier", 0.0)), "warn"),
        pill("Blocked Count", str(decision_audit.get("blocked_count", 0)), "warn"),
    ])

    sunday_supervisor_pills = "".join([
        pill("Checklist", str(sunday_checklist.get("overall_status", "-")), "good" if sunday_checklist.get("overall_status") == "PASS" else "warn"),
        pill("Live Rows", str(((sunday_checklist.get("summary") or {}).get("live_rows", 0))), "info"),
        pill("Fragility", str(((sunday_checklist.get("summary") or {}).get("portfolio_fragility", 0.0))), "warn"),
        pill("Exec Q", str(((sunday_checklist.get("summary") or {}).get("execution_quality_score", 0.0))), "warn"),
        pill("Verdict", str(((sunday_checklist.get("summary") or {}).get("deploy_verdict", "-"))), "info"),
        pill("Master Score", str(((sunday_checklist.get("summary") or {}).get("master_score", 0.0))), "warn"),
    ])

    sunday_final_report_pills = "".join([
        pill("Final Recommendation", str(sunday_final_report.get("final_recommendation", "-")), "info"),
        pill("Consistency", str(((sunday_final_report.get("consistency") or {}).get("ok", False))), "good" if ((sunday_final_report.get("consistency") or {}).get("ok", False)) else "warn"),
        pill("Stabilized Audit Count", str(((sunday_final_report.get("stabilized_audit_summary") or {}).get("count", 0))), "info"),
        pill("Threshold Rec", str(((sunday_final_report.get("threshold_recommendation") or {}).get("recommendation", "-"))), "warn"),
        pill("Legacy Audit Count", str(((sunday_final_report.get("audit_hygiene") or {}).get("legacy_count", 0))), "warn"),
        pill("Stabilized Count", str(((sunday_final_report.get("audit_hygiene") or {}).get("stabilized_count", 0))), "good"),
    ])

    preopen_action_pills = "".join([
        pill("Action Type", str(preopen_action_plan.get("action_type", "-")), "info"),
        pill("Stage", str(preopen_window_policy.get("stage", "-")), "info"),
        pill("Armed", str(preopen_window_policy.get("armed", False)), "good" if preopen_window_policy.get("armed", False) else "warn"),
        pill("Max Batch", str(preopen_window_policy.get("max_batch", 0)), "info"),
        pill("Cooldown", str(preopen_cooldown.get("remaining_seconds", 0)), "warn" if preopen_cooldown.get("active", False) else "good"),
        pill("Candidate Count", str(preopen_action_plan.get("candidate_count", 0)), "info"),
        pill("Action Logs", str(preopen_action_summary.get("total_count", 0)), "info"),
        pill("Recent Actions", str(preopen_action_summary.get("recent_count", 0)), "warn"),
    ])

    sim_rows = (preopen_transition_simulation.get("rows") or [])
    armed_count = sum(1 for r in sim_rows if r.get("armed"))
    preopen_sim_pills = "".join([
        pill("Sim Cases", str(preopen_transition_simulation.get("count", 0)), "info"),
        pill("Armed Cases", str(armed_count), "good" if armed_count > 0 else "warn"),
        pill("Latest Stage", str((sim_rows[-1].get("stage") if sim_rows else "-")), "info"),
        pill("Latest Result", str((sim_rows[-1].get("result_status") if sim_rows else "-")), "warn"),
    ])

    no_trade_html = "".join([f"<li>{r}</li>" for r in no_trade.get("reasons", [])]) or "<li>None</li>"
    regime_notes_html = "".join([f"<li>{r}</li>" for r in regime_state.get("notes", [])]) or "<li>None</li>"
    review_notes_html = "".join([f"<li>{r}</li>" for r in latest_review.get("notes", [])]) or "<li>None</li>"

    managed_rows = ""
    for p in managed:
        pnl = float(p.get("pnl_points", 0) or 0)
        pnl_cls = "pos" if pnl >= 0 else "neg"
        tags = ", ".join(p.get("management_tags", []))
        managed_rows += f"""
        <tr>
          <td>{p.get("epic")}</td>
          <td>{p.get("direction")}</td>
          <td>{p.get("size")}</td>
          <td class="{pnl_cls}">{pnl:.2f}</td>
          <td>{p.get("agent_action")}</td>
          <td><b>{p.get("final_management_action")}</b></td>
          <td>{p.get("close_priority")}</td>
          <td>{p.get("regime")}</td>
          <td>{p.get("entry_style")}</td>
          <td style="max-width:320px">{tags}</td>
        </tr>
        """

    live_rows = ""
    for p in positions:
        live_rows += f"""
        <tr>
          <td>{p.get("epic")}</td>
          <td>{p.get("direction")}</td>
          <td>{p.get("size")}</td>
          <td>{p.get("level")}</td>
          <td>{p.get("bid")}</td>
          <td>{p.get("offer")}</td>
          <td>{p.get("market_status")}</td>
        </tr>
        """

    strongest_sessions = latest_review.get("strongest_sessions", [])[:5]
    weakest_sessions = latest_review.get("weakest_sessions", [])[:5]
    strongest_symbols = latest_review.get("strongest_symbols", [])[:5]
    weakest_symbols = latest_review.get("weakest_symbols", [])[:5]

    def render_small_rows(rows, keyname):
        if not rows:
            return "<tr><td colspan='4'>No history yet</td></tr>"
        out = ""
        for r in rows:
            out += f"<tr><td>{r.get(keyname)}</td><td>{r.get('count',0)}</td><td>{r.get('wins',0)}</td><td>{round(float(r.get('pnl',0) or 0),2)}</td></tr>"
        return out

    html = f"""
    <html>
    <head>
      <title>IG Desk</title>
      <meta http-equiv="refresh" content="20">
      <style>
        :root {{
          --bg:#08101d; --panel:#101827; --panel2:#0d1422; --border:#22314d;
          --text:#edf3fb; --muted:#8fa5c7; --green:#24d07a; --red:#ff6f6f; --blue:#63a4ff; --amber:#ffb648;
        }}
        * {{ box-sizing:border-box; }}
        body {{ margin:0; background:var(--bg); color:var(--text); font-family:Inter,Arial,sans-serif; }}
        .wrap {{ max-width:1700px; margin:0 auto; padding:22px; }}
        .top {{ display:flex; justify-content:space-between; gap:16px; align-items:flex-start; margin-bottom:16px; }}
        .title {{ font-size:30px; font-weight:800; }}
        .sub {{ color:var(--muted); margin-top:6px; }}
        .nav a {{ color:#cfe2ff; text-decoration:none; margin-left:10px; font-size:13px; }}
        .grid {{ display:grid; grid-template-columns: 1.2fr 1.2fr 1fr; gap:16px; }}
        .card {{ background:var(--panel); border:1px solid var(--border); border-radius:18px; padding:16px; }}
        .h {{ font-size:15px; font-weight:800; margin-bottom:12px; }}
        .pills {{ display:flex; flex-wrap:wrap; gap:8px; }}
        .pill {{ display:inline-flex; align-items:center; border:1px solid rgba(255,255,255,.1); border-radius:999px; padding:7px 10px; font-size:12px; color:#dce8fb; }}
        .metrics {{ display:grid; grid-template-columns: repeat(3,1fr); gap:12px; }}
        .metric {{ background:var(--panel2); border:1px solid var(--border); border-radius:16px; padding:14px; }}
        .metric .k {{ color:var(--muted); font-size:12px; }}
        .metric .v {{ font-size:24px; font-weight:800; margin-top:6px; }}
        table {{ width:100%; border-collapse:collapse; }}
        th,td {{ padding:10px 8px; border-bottom:1px solid rgba(255,255,255,.06); font-size:12px; text-align:left; vertical-align:top; }}
        th {{ color:#9eb4d6; font-size:11px; text-transform:uppercase; letter-spacing:.4px; }}
        .pos {{ color:var(--green); }}
        .neg {{ color:var(--red); }}
        ul {{ margin:0; padding-left:18px; color:#d9e6fb; }}
        .span2 {{ grid-column: span 2; }}
      </style>
    </head>
    <body>
      <div class="wrap">
        <div class="top">
          <div>
            <div class="title">IG Desk Intelligence Console</div>
            <div class="sub">Session-aware, regime-aware, managed execution cockpit</div>
          </div>
          <div class="nav">
            <a href="/agent-dashboard">Agent Dashboard</a>
            <a href="/tasty-virtual-book">Tasty Virtual Book</a>
          </div>
        </div>

        <div class="metrics">
          <div class="metric"><div class="k">Balance</div><div class="v">{balance}</div></div>
          <div class="metric"><div class="k">Open P&L</div><div class="v {'class="pos"' if float(open_pnl or 0) >= 0 else 'class="neg"'}>{open_pnl}</div></div>
          <div class="metric"><div class="k">Equity</div><div class="v">{equity}</div></div>
        </div>

        <div style="height:16px"></div>

        <div class="grid">
          <div class="card">
            <div class="h">Session State</div>
            <div class="pills">{session_pills}</div>
            <div style="height:14px"></div>
            <div class="h">Carry Policy</div>
            <div class="pills">{carry_pills}</div>
          </div>

          <div class="card">
            <div class="h">Regime + Entry Expression</div>
            <div class="pills">{regime_pills}</div>
            <div style="height:12px"></div>
            <div class="pills">{expr_pills}</div>
            <div style="height:14px"></div>
            <div class="h">Asia Open Playbook</div>
            <div class="pills">{asia_pills}</div>
            <div style="height:14px"></div>
            <div class="h">Execution Sizing</div>
            <div class="pills">{sizing_pills}</div>
            <div style="height:14px"></div>
            <div class="h">Broker / Cache State</div>
            <div class="pills">{cache_pills}</div>
          </div>

          <div class="card">
            <div class="h">No-Trade Reasons</div>
            <ul>{no_trade_html}</ul>
            <div style="height:14px"></div>
            <div class="h">Regime Notes</div>
            <ul>{regime_notes_html}</ul>
          </div>

          <div class="card span2">
            <div class="h">Managed Positions</div>
            <table>
              <thead>
                <tr>
                  <th>EPIC</th><th>Dir</th><th>Size</th><th>PnL pts</th><th>Agent</th><th>Final</th><th>Priority</th><th>Regime</th><th>Entry Style</th><th>Tags</th>
                </tr>
              </thead>
              <tbody>
                {managed_rows or "<tr><td colspan='10'>No managed positions</td></tr>"}
              </tbody>
            </table>
          </div>

          <div class="card">
            <div class="h">Latest Daily Review</div>
            <ul>{review_notes_html}</ul>
            <div style="height:14px"></div>
            <div class="h">Forced Flatten Plan</div>
            <div class="pills">{flatten_pills}</div>
            <div style="height:14px"></div>
            <div class="h">Throttle Guard</div>
            <div class="pills">{throttle_pills}</div>
            <div style="height:14px"></div>
            <div class="h">Close Reconciliation</div>
            <div class="pills">{recon_pills}</div>
            <div style="height:14px"></div>
            <div class="h">Monday Monitor</div>
            <div class="pills">{monday_pills}</div>
            <div style="height:14px"></div>
            <div class="h">Transition Worker</div>
            <div class="pills">{transition_pills}</div>
            <div style="height:14px"></div>
            <div class="h">Adaptive Layer</div>
            <div class="pills">{adaptive_pills}</div>
            <div style="height:14px"></div>
            <div class="h">Adaptive Behavior</div>
            <div class="pills">{adaptive_behavior_pills}</div>
            <div style="height:14px"></div>
            <div class="h">Portfolio Intelligence</div>
            <div class="pills">{portfolio_pills}</div>
            <div style="height:14px"></div>
            <div class="h">Execution Quality</div>
            <div class="pills">{execution_quality_pills}</div>
            <div style="height:14px"></div>
            <div class="h">Market Perception</div>
            <div class="pills">{market_perception_pills}</div>
            <div style="height:14px"></div>
            <div class="h">Self-Tuning Decision</div>
            <div class="pills">{self_tuning_pills}</div>
            <div style="height:14px"></div>
            <div class="h">Decision Audit</div>
            <div class="pills">{decision_audit_pills}</div>
            <div style="height:14px"></div>
            <div class="h">Sunday Supervisor</div>
            <div class="pills">{sunday_supervisor_pills}</div>
            <div style="height:14px"></div>
            <div class="h">Sunday Final Report</div>
            <div class="pills">{sunday_final_report_pills}</div>
            <div style="height:14px"></div>
            <div class="h">Pre-Open Action Layer</div>
            <div class="pills">{preopen_action_pills}</div>
            <div style="height:14px"></div>
            <div class="h">Pre-Open Transition Simulation</div>
            <div class="pills">{preopen_sim_pills}</div>
          </div>

          <div class="card span2">
            <div class="h">Live Broker Positions</div>
            <table>
              <thead>
                <tr><th>EPIC</th><th>Dir</th><th>Size</th><th>Level</th><th>Bid</th><th>Offer</th><th>Status</th></tr>
              </thead>
              <tbody>
                {live_rows or "<tr><td colspan='7'>No live positions</td></tr>"}
              </tbody>
            </table>
          </div>

          <div class="card">
            <div class="h">Strongest Sessions</div>
            <table><thead><tr><th>Session</th><th>Count</th><th>Wins</th><th>PnL</th></tr></thead><tbody>{render_small_rows(strongest_sessions, "session")}</tbody></table>
            <div style="height:14px"></div>
            <div class="h">Weakest Sessions</div>
            <table><thead><tr><th>Session</th><th>Count</th><th>Wins</th><th>PnL</th></tr></thead><tbody>{render_small_rows(weakest_sessions, "session")}</tbody></table>
          </div>

          <div class="card">
            <div class="h">Strongest Symbols</div>
            <table><thead><tr><th>Symbol</th><th>Count</th><th>Wins</th><th>PnL</th></tr></thead><tbody>{render_small_rows(strongest_symbols, "symbol")}</tbody></table>
            <div style="height:14px"></div>
            <div class="h">Weakest Symbols</div>
            <table><thead><tr><th>Symbol</th><th>Count</th><th>Wins</th><th>PnL</th></tr></thead><tbody>{render_small_rows(weakest_symbols, "symbol")}</tbody></table>
          </div>
        </div>
      </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


@app.get("/tasty-virtual-book", response_class=HTMLResponse)
def tasty_virtual_book():
    from app.tasty_virtual_livebook import load_tasty_virtual_livebook
    from app.execution_brain import select_entries
    from app.lane_capital_controller import lane_capital_state

    state = load_tasty_virtual_livebook()
    summary = state.get("summary", {})
    positions = state.get("positions", [])
    sel = select_entries()
    lane = lane_capital_state()
    tasty_lane = lane.get("tasty", {})
    ig_lane = lane.get("ig", {})

    rows = ""
    for p in positions:
        pnl = float(p.get("unrealized_pnl", 0) or 0)
        pnl_cls = "positive" if pnl >= 0 else "negative"
        rows += f"""
        <tr>
          <td>{p.get("symbol")}</td>
          <td>{p.get("strategy")}</td>
          <td>{p.get("side")}</td>
          <td>{p.get("quantity_est")}</td>
          <td>{p.get("entry_value")}</td>
          <td>{p.get("mark_value")}</td>
          <td class="{pnl_cls}">{p.get("unrealized_pnl")}</td>
          <td>{p.get("max_risk")}</td>
          <td>{p.get("agent_note")}</td>
        </tr>
        """
    if not rows:
        rows = "<tr><td colspan='9'>No open tasty virtual positions right now.</td></tr>"

    cand_rows = ""
    for c in (sel.get("selected") or [])[:12]:
        cand_rows += f"""
        <tr>
          <td>{c.get("symbol")}</td>
          <td>{c.get("setup_name") or c.get("strategy")}</td>
          <td>{c.get("agent_view")}</td>
          <td>{c.get("confidence")}</td>
          <td>{c.get("quality_score")}</td>
          <td>{c.get("max_risk")}</td>
          <td>{c.get("estimated_debit") or c.get("estimated_credit")}</td>
          <td>{min(int(c.get("quantity", 1) or 1), 5)}</td>
        </tr>
        """
    if not cand_rows:
        cand_rows = "<tr><td colspan='8'>No selected candidates in this cycle.</td></tr>"

    html = f"""
    <html>
    <head>
      <title>Tasty Virtual Desk</title>
      <meta http-equiv="refresh" content="10">
      <style>
        :root {{
          --bg:#0a0f1a; --panel:#101827; --panel2:#0d1422; --border:#22314d;
          --text:#edf3fb; --muted:#8fa5c7; --green:#24d07a; --red:#ff6f6f; --blue:#63a4ff; --amber:#ffb648;
        }}
        * {{ box-sizing:border-box; }}
        body {{ margin:0; background:linear-gradient(180deg,#0a0f1a,#0d1422); color:var(--text); font-family:Arial,sans-serif; }}
        .wrap {{ max-width:1600px; margin:0 auto; padding:20px; }}
        .topbar {{ display:flex; justify-content:space-between; gap:16px; align-items:flex-start; margin-bottom:16px; }}
        .title {{ font-size:30px; font-weight:800; }}
        .sub {{ color:var(--muted); margin-top:6px; }}
        .nav {{ display:flex; gap:10px; flex-wrap:wrap; }}
        .linkbtn {{ display:inline-flex; text-decoration:none; color:#cfe2ff; background:rgba(99,164,255,.10); border:1px solid rgba(99,164,255,.20); border-radius:999px; padding:8px 12px; font-size:12px; font-weight:700; }}
        .grid {{ display:grid; grid-template-columns:320px 1fr 360px; gap:16px; }}
        .card {{ background:var(--panel); border:1px solid var(--border); border-radius:18px; padding:16px; }}
        .card h3 {{ margin:0 0 12px 0; font-size:16px; }}
        .metric {{ margin-bottom:12px; padding:12px; background:var(--panel2); border:1px solid var(--border); border-radius:14px; }}
        .metric-label {{ color:var(--muted); font-size:12px; }}
        .metric-value {{ font-size:24px; font-weight:800; margin-top:4px; }}
        .positive {{ color:var(--green); font-weight:800; }}
        .negative {{ color:var(--red); font-weight:800; }}
        .neutral {{ color:var(--amber); font-weight:800; }}
        .chartbox {{ height:360px; border-radius:14px; border:1px solid var(--border); background:
          linear-gradient(180deg, rgba(99,164,255,.06), rgba(99,164,255,0)),
          repeating-linear-gradient(to right, rgba(255,255,255,.04) 0, rgba(255,255,255,.04) 1px, transparent 1px, transparent 70px),
          repeating-linear-gradient(to bottom, rgba(255,255,255,.04) 0, rgba(255,255,255,.04) 1px, transparent 1px, transparent 56px);
          position:relative; overflow:hidden; }}
        .chartline {{
          position:absolute; left:2%; right:2%; top:20%;
          height:60%;
          background:linear-gradient(180deg, rgba(99,164,255,.12), rgba(99,164,255,0));
          clip-path:polygon(0% 70%,8% 60%,15% 68%,24% 42%,31% 48%,39% 28%,47% 40%,56% 18%,64% 52%,74% 33%,82% 44%,91% 26%,100% 34%,100% 100%,0% 100%);
          border-bottom:2px solid rgba(99,164,255,.9);
        }}
        table {{ width:100%; border-collapse:collapse; font-size:13px; }}
        th, td {{ padding:10px; border-bottom:1px solid var(--border); text-align:left; vertical-align:top; }}
        th {{ color:var(--muted); font-weight:700; }}
        .stack {{ display:flex; flex-direction:column; gap:16px; }}
        .brain-item {{ padding:10px 12px; border-radius:12px; border:1px solid var(--border); background:var(--panel2); margin-bottom:8px; }}
      </style>
    </head>
    <body>
      <div class="wrap">
        <div class="topbar">
          <div>
            <div class="title">Tasty Virtual Desk</div>
            <div class="sub">Production signal environment · virtual execution · live monitoring · options swing desk</div>
          </div>
          <div class="nav">
            <a class="linkbtn" href="/agent-dashboard">Main Dashboard</a>
            <a class="linkbtn" href="/agent-research">Research</a>
            <a class="linkbtn" href="/ig-desk">IG Desk</a>
            <a class="linkbtn" href="/tasty-virtual-book">Tasty Virtual</a>
            <a class="linkbtn" href="/lane-capital">Lane Capital</a>
          </div>
        </div>

        <div class="grid">
          <div class="stack">
            <div class="card">
              <h3>Tasty Account</h3>
              <div class="metric"><div class="metric-label">Equity</div><div class="metric-value">{tasty_lane.get("equity")}</div></div>
              <div class="metric"><div class="metric-label">Cash</div><div class="metric-value">{tasty_lane.get("cash_balance")}</div></div>
              <div class="metric"><div class="metric-label">Realized P&L</div><div class="metric-value">{summary.get("realized_pnl")}</div></div>
              <div class="metric"><div class="metric-label">Unrealized P&L</div><div class="metric-value">{summary.get("unrealized_pnl")}</div></div>
              <div class="metric"><div class="metric-label">Open Positions</div><div class="metric-value">{summary.get("open_positions")}</div></div>
              <div class="metric"><div class="metric-label">Capital Usage %</div><div class="metric-value">{tasty_lane.get("usage_pct")}</div></div>
            </div>

            <div class="card">
              <h3>Agent Brain</h3>
              <div class="brain-item">Selected candidates this cycle: <b>{len(sel.get("selected") or [])}</b></div>
              <div class="brain-item">Debug pool size: <b>{sel.get("debug_pool_size")}</b></div>
              <div class="brain-item">Current mode: <b>virtual swing options</b></div>
              <div class="brain-item">If no trades appear, the desk should show no-setup state rather than look dead.</div>
            </div>
          </div>

          <div class="stack">
            <div class="card">
              <h3>Active Symbol Chart View</h3>
              <div class="chartbox">
                <div class="chartline"></div>
              </div>
            </div>

            <div class="card">
              <h3>Open Positions</h3>
              <table>
                <thead>
                  <tr>
                    <th>Symbol</th><th>Strategy</th><th>Side</th><th>Qty</th><th>Entry</th><th>Mark</th><th>P&L</th><th>Risk</th><th>Reason</th>
                  </tr>
                </thead>
                <tbody>{rows}</tbody>
              </table>
            </div>
          </div>

          <div class="stack">
            <div class="card">
              <h3>Candidate Ladder</h3>
              <table>
                <thead>
                  <tr>
                    <th>Symbol</th><th>Setup</th><th>View</th><th>Conf</th><th>Quality</th><th>Risk</th><th>Price</th><th>Qty</th>
                  </tr>
                </thead>
                <tbody>{cand_rows}</tbody>
              </table>
            </div>

            <div class="card">
              <h3>Lane Overview</h3>
              <div class="metric"><div class="metric-label">IG Equity</div><div class="metric-value">{ig_lane.get("equity")}</div></div>
              <div class="metric"><div class="metric-label">IG Usage %</div><div class="metric-value">{ig_lane.get("usage_pct")}</div></div>
              <div class="metric"><div class="metric-label">Tasty Source</div><div class="metric-value">{summary.get("source_status")}</div></div>
              <div class="metric"><div class="metric-label">Updated</div><div class="metric-value">{summary.get("updated_at")}</div></div>
            </div>
          </div>
        </div>
      </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html)

@app.get("/lane-capital", response_class=HTMLResponse)
def lane_capital():
    state = lane_capital_state()
    cfg = state.get("config", {})
    ig = state.get("ig", {})
    tasty = state.get("tasty", {})

    html = f"""
    <html>
    <head>
      <title>Lane Capital Control</title>
      <meta http-equiv="refresh" content="15">
      <style>
        body {{ margin:0; background:#0b1220; color:#e8eef8; font-family:Arial,sans-serif; }}
        .wrap {{ max-width:1200px; margin:0 auto; padding:24px; }}
        .topbar {{ display:flex; justify-content:space-between; align-items:flex-start; gap:16px; margin-bottom:18px; }}
        .title {{ font-size:28px; font-weight:800; }}
        .sub {{ color:#92a3bf; margin-top:6px; }}
        .top-pills {{ display:flex; gap:10px; flex-wrap:wrap; justify-content:flex-end; }}
        .linkbtn {{ display:inline-flex; text-decoration:none; color:#cfe2ff; background:rgba(99,164,255,.10); border:1px solid rgba(99,164,255,.20); border-radius:999px; padding:8px 12px; font-size:12px; font-weight:700; }}
        .grid {{ display:grid; grid-template-columns:repeat(2,1fr); gap:16px; }}
        .card {{ background:#121b2d; border:1px solid #243552; border-radius:18px; padding:18px; }}
        .metric {{ margin:10px 0; }}
        .label {{ color:#8ea4c7; font-size:12px; }}
        .value {{ font-size:22px; font-weight:800; }}
      </style>
    </head>
    <body>
      <div class="wrap">
        <div class="topbar">
          <div>
            <div class="title">Lane Capital Control</div>
            <div class="sub">Separate capital governance for IG and Tasty virtual</div>
          </div>
          <div class="top-pills">
            <a class="linkbtn" href="/agent-dashboard">Main Dashboard</a>
            <a class="linkbtn" href="/agent-research">Research</a>
            <a class="linkbtn" href="/ig-desk">IG Desk</a>
            <a class="linkbtn" href="/tasty-virtual-book">Tasty Virtual</a>
            <a class="linkbtn" href="/lane-capital">Lane Capital</a>
            <a class="linkbtn" href="/lane-capital">Lane Capital</a>
          </div>
        </div>

        <div class="grid">
          <div class="card">
            <h3>IG Lane</h3>
            <div class="metric"><div class="label">Enabled</div><div class="value">{cfg.get("ig_enabled")}</div></div>
            <div class="metric"><div class="label">Usage Cap %</div><div class="value">{cfg.get("ig_max_usage_pct")}</div></div>
            <div class="metric"><div class="label">Equity</div><div class="value">{ig.get("equity")}</div></div>
            <div class="metric"><div class="label">Deployed</div><div class="value">{ig.get("deployed")}</div></div>
            <div class="metric"><div class="label">Usage %</div><div class="value">{ig.get("usage_pct")}</div></div>
          </div>

          <div class="card">
            <h3>Tasty Virtual Lane</h3>
            <div class="metric"><div class="label">Enabled</div><div class="value">{cfg.get("tasty_enabled")}</div></div>
            <div class="metric"><div class="label">Seed Capital</div><div class="value">{cfg.get("tasty_starting_capital")}</div></div>
            <div class="metric"><div class="label">Usage Cap %</div><div class="value">{cfg.get("tasty_max_usage_pct")}</div></div>
            <div class="metric"><div class="label">Equity</div><div class="value">{tasty.get("equity")}</div></div>
            <div class="metric"><div class="label">Deployed</div><div class="value">{tasty.get("deployed")}</div></div>
            <div class="metric"><div class="label">Usage %</div><div class="value">{tasty.get("usage_pct")}</div></div>
          </div>
        </div>
      </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html)
