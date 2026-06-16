#!/usr/bin/env bash
# Fetch ESO snapshot and push to data branch.
# Run every 5 min via cron.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DATA_WORKTREE="$(cd "$SCRIPT_DIR/../eso-data" && pwd)"

# ── Fetch (strict: exit if ESO is unreachable — nothing to commit) ────────────
set -euo pipefail
DATA_DIR="$DATA_WORKTREE/data" python3 "$SCRIPT_DIR/fetch.py"
DATA_DIR="$DATA_WORKTREE/data" python3 "$SCRIPT_DIR/compute_records.py"
DATA_DIR="$DATA_WORKTREE/data" python3 "$SCRIPT_DIR/update_records_history_jsonl.py"

# ── Git: best-effort — data is always committed locally; push when GH reachable
set +e
cd "$DATA_WORKTREE"
git rebase --abort 2>/dev/null   # recover from any stuck rebase
git add data/
git diff --cached --quiet && exit 0   # nothing new

git commit -m "data: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
git pull --rebase origin data 2>/dev/null || true
git push origin data 2>/dev/null || true
