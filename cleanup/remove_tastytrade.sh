#!/usr/bin/env bash
#
# Tastytrade removal script. Generated as part of the IG-only migration.
# Safe to run from a clean working tree. Run from repo root.
#
# Usage:
#   bash cleanup/remove_tastytrade.sh
#
# What this script does:
#   1. Creates branch `remove-tastytrade` if not already on it
#   2. Deletes all files that exist solely to integrate Tastytrade or to power
#      the legacy options-trading stack that depended on Tastytrade
#   3. Stages the deletions (does not commit — review with `git status` first)
#   4. Runs syntax check on remaining Python files
#
# Files deleted (all under app/):
#   Pure Tastytrade broker layer (5):
#     tasty_connector.py, tasty_oauth.py,
#     tasty_virtual_livebook.py, tasty_virtual_livebook_worker.py,
#     tasty_virtual_booker.py
#
#   Options stack that only existed to consume Tastytrade (10):
#     option_chain.py, quote_engine.py, order_preview.py, spread_builder.py,
#     universe_selector.py, manual_ticket.py, market_scanner.py,
#     prep_cycle.py, prep_worker.py, scheduled_scanner.py
#
#   Legacy options execution path superseded by ig_execution_*:
#     execution_engine.py, execution_brain.py, virtual_execution.py,
#     virtual_exit.py, auto_trade_worker.py, autonomous_execution_worker.py,
#     virtual_portfolio.py
#
#   Plus a leftover editor-temp file:
#     ig_execution_sizing.py.save

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

# 1. branch
CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [[ "$CURRENT_BRANCH" != "remove-tastytrade" ]]; then
    if git rev-parse --verify remove-tastytrade >/dev/null 2>&1; then
        git checkout remove-tastytrade
    else
        git checkout -b remove-tastytrade
    fi
fi

# 2. files to delete
DELETE_FILES=(
    # Pure Tasty broker layer
    app/tasty_connector.py
    app/tasty_oauth.py
    app/tasty_virtual_livebook.py
    app/tasty_virtual_livebook_worker.py
    app/tasty_virtual_booker.py

    # Options stack — only existed to consume Tastytrade
    app/option_chain.py
    app/quote_engine.py
    app/order_preview.py
    app/spread_builder.py
    app/universe_selector.py
    app/manual_ticket.py
    app/market_scanner.py
    app/prep_cycle.py
    app/prep_worker.py
    app/scheduled_scanner.py

    # Legacy options execution path (superseded by ig_execution_*)
    app/execution_engine.py
    app/execution_brain.py
    app/virtual_execution.py
    app/virtual_exit.py
    app/auto_trade_worker.py
    app/autonomous_execution_worker.py
    app/virtual_monitor_worker.py
    app/telegram_worker.py

    # Legacy data layer — replaced by ig_trade_store on the IG side
    app/trade_store.py
    app/risk_engine.py

    # Editor backup
    app/ig_execution_sizing.py.save
)

# Files KEPT (and why):
#   app/virtual_portfolio.py        — still queried by IG dashboards
#                                     (dashboard_state, daily_summary,
#                                     research_state, exit_brain,
#                                     reporting_engine). Live-options pricing
#                                     calls were stubbed during the cleanup.
#   app/exit_brain.py               — used by research_state.py to display
#                                     virtual exit decisions on the IG dash.
#   app/reporting_engine.py         — used by owner_reporting_worker.

echo "Deleting ${#DELETE_FILES[@]} files..."
for f in "${DELETE_FILES[@]}"; do
    if [[ -f "$f" ]]; then
        git rm "$f"
        echo "  deleted: $f"
    else
        echo "  skipped (not present): $f"
    fi
done

# 3. compile-check the remaining python files
echo ""
echo "Running py_compile on remaining files..."
python3 -m compileall -q app/ tests/ || {
    echo ""
    echo "py_compile FAILED. There are remaining import errors to fix."
    echo "Inspect with: python3 -m py_compile app/main.py"
    exit 1
}

echo ""
echo "All remaining files compile cleanly."
echo ""
echo "Next: review with 'git status' and 'git diff --cached --stat'"
echo "When happy: git commit -m 'remove Tastytrade integration and legacy options stack'"
