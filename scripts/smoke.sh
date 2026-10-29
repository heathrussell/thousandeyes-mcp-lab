#!/usr/bin/env bash
# Checks a deployed lab end to end: API health, leaderboard, the site serving index.html and config.js, CORS, and the
# onboarding/proctor routes. Usage: scripts/smoke.sh (reads stack outputs) or SITE_URL=... API_URL=... scripts/smoke.sh
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
check curl -fsS -o /dev/null -X OPTIONS -H "Origin: $SITE_URL" -H "Access-Control-Request-Method: PUT" -H "Access-Control-Request-Headers: content-type,x-proctor-key" "$API_URL/proctor/config"
DISC=$(curl -sS -o /tmp/te-lab-discover.json -w '%{http_code}' "$API_URL/discover")
[ "$DISC" = "400" ] && echo "ok   GET /discover without a domain is 400" || { echo "FAIL GET /discover returned $DISC, expected 400"; fail=1; }
H=$(curl -fsS "$API_URL/health"); echo; echo "API health: $H"
echo "$H" | grep -q '"answers": true' && echo "ok   the Lambda has the accepted answers" || { echo "FAIL the Lambda has no answers (deploy ran without api/answers.json)"; fail=1; }
code=$(curl -s -o /dev/null -w "%{http_code}" "$API_URL/proctor/config"); [ "$code" = "401" ] && echo "ok   proctor routes refuse requests without the key" || { echo "FAIL /proctor/config without a key answered $code (expected 401)"; fail=1; }
if echo "$H" | grep -q '"proctor": true'; then
  echo "$H" | grep -q '"onboarding": "ready"' && echo "ok   attendee onboarding is open" || echo "note onboarding is not open yet: sign in at $SITE_URL/#proctor, save the ThousandEyes token and tick 'Open self-service sign-up'"
else
  echo "note deployed without PROCTOR_KEY: proctor setup and attendee onboarding are off"
fi
[ "$fail" -eq 0 ] && echo "All good. Open $SITE_URL and check in with a test handle." || { echo "Something failed; see above."; exit 1; }
