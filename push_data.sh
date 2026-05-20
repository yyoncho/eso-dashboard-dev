#!/usr/bin/env bash
# Fetch ESO snapshot and push to data branch.
# Run every 5 min via cron.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DATA_WORKTREE="$(cd "$SCRIPT_DIR/../eso-data" && pwd)"

# fetch.py writes into DATA_WORKTREE/data/
DATA_DIR="$DATA_WORKTREE/data" \
  python3 "$SCRIPT_DIR/fetch.py"

# recompute renewable/battery/export records
DATA_DIR="$DATA_WORKTREE/data" python3 "$SCRIPT_DIR/compute_records.py"

cd "$DATA_WORKTREE"
git add data/
git diff --cached --quiet && exit 0   # nothing changed

git commit -m "data: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
git push origin data
