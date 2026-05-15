#!/usr/bin/env bash
#
# One-command deploy.
#
# What it does:
#   1. Commits any uncommitted changes in the working tree
#   2. Pulls/rebases against origin/main and pushes
#   3. SSHes into Lightsail, pulls, compile-checks, restarts services
#   4. Prints the final deployed commit hash so you know it's live
#
# Usage:
#   ./push-and-deploy.sh "short commit message"
#   ./push-and-deploy.sh                          # uses an auto-generated msg
#
# Bypasses GitHub Actions entirely (works even if CI is red).

set -euo pipefail

KEY=~/Downloads/LightsailDefaultKey-eu-west-2.pem
HOST=ubuntu@16.60.74.15
MSG="${1:-deploy: $(date +'%Y-%m-%d %H:%M:%S')}"

cd "$(dirname "$0")"

echo "=== [1/5] commit local changes ==="
git add -A
if git diff --cached --quiet; then
    echo "no changes to commit, will deploy whatever's on origin/main"
else
    git commit -m "$MSG"
    echo "committed: $MSG"
fi

echo ""
echo "=== [2/5] push to origin/main ==="
git checkout main 2>/dev/null || true
git pull --rebase origin main || true
git push origin main

echo ""
echo "=== [3/5] pull on Lightsail + compile-check ==="
ssh -i "$KEY" "$HOST" "
  set -e
  cd ~/angad-option-desk-v1
  git fetch origin
  git reset --hard origin/main
  find . -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
  python3 -m compileall -q app/ tests/
  echo 'compile OK'
"

echo ""
echo "=== [4/5] restart services ==="
ssh -i "$KEY" "$HOST" "
  sudo systemctl restart angad-option-desk.service
  sudo systemctl restart ig-execution-worker.service
  sudo systemctl restart angad-ig-briefing.service
  sudo systemctl restart angad-code-proposer.service 2>/dev/null || true
  sudo systemctl restart autonomous-cto.service 2>/dev/null || true
  echo 'services restarted'
"

echo ""
echo "=== [5/5] verify deployed commit ==="
DEPLOYED_SHA=$(ssh -i "$KEY" "$HOST" "cd ~/angad-option-desk-v1 && git rev-parse --short HEAD")
LOCAL_SHA=$(git rev-parse --short HEAD)

echo "local main:    $LOCAL_SHA"
echo "lightsail HEAD: $DEPLOYED_SHA"
if [[ "$LOCAL_SHA" == "$DEPLOYED_SHA" ]]; then
    echo "✅ deploy complete — Lightsail matches local"
else
    echo "⚠️ mismatch — local $LOCAL_SHA but Lightsail at $DEPLOYED_SHA"
    exit 1
fi
