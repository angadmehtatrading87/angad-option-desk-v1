from app.market_prep_brain import load_market_prep_state

def build_pre_session_briefing():
    state = load_market_prep_state()
    macro = state.get("macro", {})
    regime_view = state.get("regime_view", {})
    plan = state.get("session_plan", {})
    top_focus = plan.get("top_opportunities", [])

    lines = []
    lines.append("<b>Pre-Session Briefing</b>")
    lines.append("")
    lines.append(f"Regime: {plan.get('regime')}")
    lines.append(f"Style: {plan.get('style')}")
    lines.append(f"Confidence: {plan.get('confidence')}")
    lines.append(f"Day Mode: {plan.get('day_mode')}")
    lines.append("")
    lines.append("<b>Macro</b>")
    lines.append(f"Headline Regime: {macro.get('macro_regime')}")
    lines.append(f"Summary: {macro.get('summary')}")
    lines.append(f"Risk-On Score: {macro.get('risk_on_score')} | Risk-Off Score: {macro.get('risk_off_score')}")
    lines.append("")
    lines.append("<b>Plan</b>")
    lines.append(f"Max New Entries: {plan.get('max_new_entries')}")
    lines.append(f"Max Concurrent Trades: {plan.get('max_concurrent_trades')}")
    lines.append(f"Max Deployed Capital: {plan.get('max_deployed_capital_pct')}%")
    lines.append(f"Min Idle Liquidity: {plan.get('min_idle_liquidity_pct')}%")
    lines.append("")
    lines.append("<b>Preferred Structures</b>")
    for x in plan.get("preferred_structures", []):
        lines.append(f"- {x}")
    lines.append("")
    lines.append("<b>Avoid</b>")
    for x in plan.get("forbidden_structures", []):
        lines.append(f"- {x}")
    lines.append("")
    lines.append("<b>Top Focus</b>")
    if not top_focus:
        lines.append("- No valid opportunities today.")
    else:
        for row in top_focus:
            lines.append(
                f"- {row.get('symbol')} | score {row.get('opportunity_score')} | "
                f"chg {row.get('change_pct')}% | spread {row.get('spread_pct')}% | "
                f"structures {', '.join(row.get('preferred_structures', []))}"
            )
    if plan.get("reasons"):
        lines.append("")
        lines.append("<b>Flags</b>")
        for r in plan.get("reasons", []):
            lines.append(f"- {r}")
    lines.append("")
    lines.append(f"Session Note: {plan.get('session_note', regime_view.get('session_note', ''))}")
    return "\n".join(lines)
