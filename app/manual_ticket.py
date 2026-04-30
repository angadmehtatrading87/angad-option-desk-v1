from app.trade_store import get_trade, update_manual_ticket, mark_manual_executed, mark_manual_not_executed
from app.telegram_alerts import send_telegram_message


def build_manual_ticket_text(trade):
    estimated_debit = trade.get("estimated_debit")
    estimated_credit = trade.get("estimated_credit")

    if estimated_debit is not None:
        limit_instruction = f"Limit Debit: {estimated_debit}"
        price_effect = "DEBIT"
    elif estimated_credit is not None:
        limit_instruction = f"Limit Credit: {estimated_credit}"
        price_effect = "CREDIT"
    else:
        limit_instruction = "Limit Price: Review manually"
        price_effect = "UNKNOWN"

    ticket = f"""
TRADE #{trade.get("id")} — MANUAL EXECUTION TICKET

Symbol: {trade.get("symbol")}
Strategy: {trade.get("strategy")}
Expiry: {trade.get("expiry")}

Legs:
{trade.get("legs")}

Order Type: LIMIT
Quantity: 1 contract spread
Price Effect: {price_effect}
{limit_instruction}

Max Risk: ${trade.get("max_risk")}
Target Profit: ${trade.get("target_profit")}
Stop Loss: ${trade.get("stop_loss")}

Agent Grade: {trade.get("agent_grade")}
Agent View: {trade.get("agent_view")}
Confidence: {trade.get("confidence_score")}

Execution Mode:
MANUAL ENTRY IN TASTYTRADE APP

Checklist before placing:
1. Confirm both legs match exactly.
2. Confirm quantity is 1.
3. Use LIMIT order only.
4. Do not use market order.
5. Confirm debit/credit matches the ticket.
6. If live price moved materially, do not chase.
7. After execution, mark trade as manually executed in dashboard.

No API order has been placed.
"""
    return ticket.strip()


def generate_manual_ticket(trade_id):
    trade = get_trade(trade_id)

    if not trade:
        raise ValueError(f"Trade #{trade_id} not found.")

    ticket = build_manual_ticket_text(trade)

    update_manual_ticket(
        trade_id=trade_id,
        ticket_status="READY_FOR_MANUAL_EXECUTION",
        ticket_text=ticket
    )

    send_telegram_message(f"<b>Manual Execution Ticket Ready</b>\n\n<pre>{ticket}</pre>")

    return {
        "trade_id": trade_id,
        "status": "READY_FOR_MANUAL_EXECUTION",
        "ticket": ticket
    }


def mark_executed(trade_id):
    mark_manual_executed(trade_id, notes="Marked executed by user.")
    send_telegram_message(f"✅ Trade #{trade_id} marked as MANUALLY EXECUTED.")
    return {"trade_id": trade_id, "status": "MANUALLY_EXECUTED"}


def mark_not_executed(trade_id):
    mark_manual_not_executed(trade_id, notes="Marked not executed by user.")
    send_telegram_message(f"❌ Trade #{trade_id} marked as NOT EXECUTED.")
    return {"trade_id": trade_id, "status": "NOT_EXECUTED"}
