#!/usr/bin/env bash
# Push dev branch to eso-dashboard-dev (GitHub Pages staging).
#
# Usage:
#   ./push_staging.sh          — push current dev HEAD to staging
#   ./push_staging.sh --help   — show this message
#
# The staging site reads live data from the main repo's `data` branch
# (BASE URL in index.html), so no data sync is needed.
#
# Requires: git remote `staging` pointing to yyoncho/eso-dashboard-dev
#   git remote add staging https://<token>@github.com/yyoncho/eso-dashboard-dev.git

set -euo pipefail

if [[ "${1:-}" == "--help" ]]; then
  sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'
  exit 0
fi

CURRENT=$(git branch --show-current)
if [[ "$CURRENT" != "dev" ]]; then
  echo "ERROR: must be on dev branch (currently on '$CURRENT')" >&2
  exit 1
fi

if ! git remote get-url staging &>/dev/null; then
  echo "ERROR: remote 'staging' not configured." >&2
  echo "Run: git remote add staging https://<token>@github.com/yyoncho/eso-dashboard-dev.git" >&2
  exit 1
fi

echo "Pushing dev → staging/master …"
git push staging dev:master
echo "Done. Staging will be live at https://yyoncho.github.io/eso-dashboard-dev/ in ~1 min."
