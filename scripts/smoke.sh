#!/usr/bin/env bash
# Checks a deployed lab end to end: API health, leaderboard, and the site serving index.html and config.js.
# Usage: scripts/smoke.sh            (reads stack outputs)   or   SITE_URL=... API_URL=... scripts/smoke.sh
set -euo pipefail
cd "$(dirname "$0")/.."
: "${AWS_REGION:=ap-southeast-2}"; : "${API_STACK:=te-lab-api}"; : "${SITE_STACK:=te-lab-site}"
out() { aws cloudformation describe-stacks --region "$AWS_REGION" --stack-name "$1" --query "Stacks[0].Outputs[?OutputKey=='$2'].OutputValue" --output text; }
SITE_URL="${SITE_URL:-$(out "$SITE_STACK" SiteUrl)}"
API_URL="${API_URL:-$(out "$API_STACK" ApiUrl)}"
fail=0
check() { if "$@"; then echo "ok   $*"; else echo "FAIL $*"; fail=1; fi; }
check curl -fsS -o /dev/null "$API_URL/health"
check curl -fsS -o /dev/null "$API_URL/leaderboard"
check curl -fsS -o /dev/null "$SITE_URL/"
check curl -fsS "$SITE_URL/config.js" -o /tmp/te-lab-config.js
grep -q "$API_URL" /tmp/te-lab-config.js && echo "ok   config.js points at the API" || { echo "FAIL config.js does not point at $API_URL"; fail=1; }
check curl -fsS -o /dev/null -X OPTIONS -H "Origin: $SITE_URL" -H "Access-Control-Request-Method: POST" "$API_URL/checkin"
echo; echo "API health: $(curl -fsS "$API_URL/health")"
[ "$fail" -eq 0 ] && echo "All good. Open $SITE_URL and check in with a test handle." || { echo "Something failed; see above."; exit 1; }
