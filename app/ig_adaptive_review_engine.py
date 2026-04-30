from app.ig_trade_scorecard import summarize_scorecards
from app.ig_context_performance_memory import build_context_performance, rank_context_bucket

def build_adaptive_review():
    score = summarize_scorecards()
    ctx = build_context_performance()

    session_rank = rank_context_bucket(ctx.get("by_session", {}), "session")
    regime_rank = rank_context_bucket(ctx.get("by_regime", {}), "regime")
    symbol_rank = rank_context_bucket(ctx.get("by_symbol", {}), "symbol")
    style_rank = rank_context_bucket(ctx.get("by_entry_style", {}), "entry_style")

    notes = []
    if score.get("completed_count", 0) < 5:
        notes.append("Adaptive history still thin; do not overfit yet.")
    if score.get("win_rate_pct", 0.0) < 40 and score.get("completed_count", 0) >= 5:
        notes.append("Win rate weak; tighten deployment and reduce size in weaker contexts.")
    if score.get("win_rate_pct", 0.0) >= 55 and score.get("completed_count", 0) >= 5:
        notes.append("Some edge emerging; lean into best contexts only.")
    if not session_rank.get("best"):
        notes.append("No strong session edge identified yet.")

    return {
        "scorecards": score,
        "context_performance": ctx,
        "best_sessions": session_rank.get("best", []),
        "worst_sessions": session_rank.get("worst", []),
        "best_regimes": regime_rank.get("best", []),
        "worst_regimes": regime_rank.get("worst", []),
        "best_symbols": symbol_rank.get("best", []),
        "worst_symbols": symbol_rank.get("worst", []),
        "best_entry_styles": style_rank.get("best", []),
        "worst_entry_styles": style_rank.get("worst", []),
        "notes": notes
    }
