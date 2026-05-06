#!/usr/bin/env bash
#
# Remove the remaining legacy options-era reporting layer.
#
# Files deleted:
#   - app/daily_summary.py            (legacy "Day Start / End of Day Summary")
#   - app/daily_summary_worker.py     (its scheduler — was zombie running stale bytecode)
#   - app/owner_briefing.py           (legacy "Pre-Session Briefing" — replaced by ig_briefing)
#   - app/owner_reporting_worker.py   (its scheduler)
#   - app/reporting_engine.py         (legacy "Post-Session Report" with Withdrawal Pool)
#
# These were causing Tastytrade Telegram messages because the long-running
# zombies kept calling tasty_connector via in-memory imports from before
# Phase 1, even after the source files were deleted.
#
# Replacement: app/ig_briefing.py (already deployed) does all of this for FX.
#
# Run from repo root:
#     bash cleanup/remove_legacy_reporting.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

echo "=== Deleting 5 legacy options-reporting files ==="
DELETE_FILES=(
    app/daily_summary.py
    app/daily_summary_worker.py
    app/owner_briefing.py
    app/owner_reporting_worker.py
    app/reporting_engine.py
)

for f in "${DELETE_FILES[@]}"; do
    if [[ -f "$f" ]]; then
        git rm "$f"
        echo "  deleted: $f"
    else
        echo "  skipped (not present): $f"
    fi
done

echo ""
echo "=== Compile-checking remaining files ==="
python3 -m compileall -q app/ tests/ || {
    echo "py_compile FAILED — there are leftover imports to fix"
    exit 1
}
echo "all remaining files compile cleanly"

echo ""
echo "Next:"
echo "  1. git commit -m 'Remove legacy options reporting layer'"
echo "  2. git push origin main"
echo "  3. (after auto-deploy) on Lightsail:"
echo "     sudo systemctl stop angad-daily-summary angad-owner-reporting"
echo "     sudo systemctl disable angad-daily-summary angad-owner-reporting"
echo "     sudo rm -f /etc/systemd/system/angad-daily-summary.service"
echo "     sudo rm -f /etc/systemd/system/angad-owner-reporting.service"
echo "     sudo systemctl daemon-reload"
echo "     sudo pkill -9 -f daily_summary_worker || true"
echo "     sudo pkill -9 -f owner_reporting_worker || true"
echo "     sudo systemctl restart angad-option-desk.service"
