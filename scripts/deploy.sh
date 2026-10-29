#!/usr/bin/env bash
# Deploys the ThousandEyes MCP Lab into the current AWS account: hosting stack, API stack, site files.
# Idempotent: run it again after any change. Every setting is an environment variable with a sane default.
#
#   AWS_REGION          region for the API and hosting stacks (default ap-southeast-2)
#   API_STACK           CloudFormation stack name for the API (default te-lab-api)
#   SITE_STACK          CloudFormation stack name for the hosting (default te-lab-site)
#   DOMAIN              optional custom domain, e.g. lab.example.com (needs CERT_ARN)
#   CERT_ARN            ACM certificate ARN in us-east-1 for DOMAIN (see infra/certificate.yaml)
#   HOSTED_ZONE_ID      optional Route 53 zone for DOMAIN; the alias records are created for you
#   ANSWERS_FILE        path to the accepted answers (default api/answers.json; git-ignored, keep it beside the repo)
#   ANTHROPIC_API_KEY   optional; switches on the front desk (/ask). Never commit it.
#   EVENT_NAME, EVENT_DATE, EVENT_CITY   shown on the site hero (defaults: "AI Builders", blank, blank)
#   ALLOWED_ORIGIN      CORS origin for the API; defaults to the site URL once hosting exists
set -euo pipefail
cd "$(dirname "$0")/.."

: "${AWS_REGION:=ap-southeast-2}"
: "${API_STACK:=te-lab-api}"
: "${SITE_STACK:=te-lab-site}"
DOMAIN="${DOMAIN:-}"; CERT_ARN="${CERT_ARN:-}"; HOSTED_ZONE_ID="${HOSTED_ZONE_ID:-}"
ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}"
EVENT_NAME="${EVENT_NAME:-AI Builders}"; EVENT_DATE="${EVENT_DATE:-}"; EVENT_CITY="${EVENT_CITY:-}"

for tool in aws sam python3; do command -v "$tool" >/dev/null || { echo "missing: $tool (see DEPLOY.md, prerequisites)"; exit 1; }; done
if [ -n "$DOMAIN" ] && [ -z "$CERT_ARN" ]; then echo "DOMAIN is set but CERT_ARN is empty. Deploy infra/certificate.yaml in us-east-1 first (DEPLOY.md, step 2)."; exit 1; fi
ANSWERS_FILE="${ANSWERS_FILE:-api/answers.json}"
if [ ! -s "$ANSWERS_FILE" ]; then echo "missing $ANSWERS_FILE: the accepted answers are kept out of git on purpose. Put the file in place (format in DEPLOY.md) and re-run."; exit 1; fi
python3 -c "import json,sys; d=json.load(open(sys.argv[1])); assert isinstance(d, dict) and all(isinstance(v, list) and v for v in d.values()), 'answers.json must map checkpoint ids to non-empty lists'; print(f'== answers: {len(d)} checkpoints from {sys.argv[1]}')" "$ANSWERS_FILE"
ANSWERS_B64=$(base64 < "$ANSWERS_FILE" | tr -d '\n')

echo "== account: $(aws sts get-caller-identity --query Account --output text) · region: $AWS_REGION"

echo "== 1/5 hosting stack ($SITE_STACK)"
aws cloudformation deploy --region "$AWS_REGION" --stack-name "$SITE_STACK" \
  --template-file infra/hosting.yaml --no-fail-on-empty-changeset \
  --parameter-overrides "DomainName=$DOMAIN" "CertificateArn=$CERT_ARN" "HostedZoneId=$HOSTED_ZONE_ID"
out() { aws cloudformation describe-stacks --region "$AWS_REGION" --stack-name "$1" --query "Stacks[0].Outputs[?OutputKey=='$2'].OutputValue" --output text; }
BUCKET=$(out "$SITE_STACK" BucketName)
DIST_ID=$(out "$SITE_STACK" DistributionId)
SITE_URL=$(out "$SITE_STACK" SiteUrl)
ORIGIN="${ALLOWED_ORIGIN:-$SITE_URL}"

echo "== 2/5 API stack ($API_STACK), CORS origin $ORIGIN"
( cd api && sam build >/dev/null && sam deploy --region "$AWS_REGION" --stack-name "$API_STACK" \
    --resolve-s3 --capabilities CAPABILITY_IAM --no-confirm-changeset --no-fail-on-empty-changeset \
    --parameter-overrides "AllowedOrigin=$ORIGIN" "AnthropicApiKey=$ANTHROPIC_API_KEY" "AnswersB64=$ANSWERS_B64" )
API_URL=$(out "$API_STACK" ApiUrl)

echo "== 3/5 site/config.js -> $API_URL"
python3 - "$API_URL" "$EVENT_NAME" "$EVENT_DATE" "$EVENT_CITY" <<'PY'
import json, sys
api, name, date, city = sys.argv[1:5]
cfg = {"apiBase": api.rstrip("/"), "event": {"name": name, "date": date, "city": city}}
open("site/config.js", "w", encoding="utf-8").write(
    "// ThousandEyes MCP Lab: site configuration (written by scripts/deploy.sh; edit and re-run `make site` to change)\n"
    "window.TE_LAB_CONFIG = " + json.dumps(cfg, indent=2, ensure_ascii=False) + ";\n")
PY

echo "== 4/5 upload site to s3://$BUCKET and invalidate CloudFront"
aws s3 sync site/ "s3://$BUCKET/" --delete --region "$AWS_REGION" --only-show-errors
aws s3 cp site/config.js "s3://$BUCKET/config.js" --region "$AWS_REGION" --cache-control "no-cache" --content-type "application/javascript" --only-show-errors
aws cloudfront create-invalidation --distribution-id "$DIST_ID" --paths "/*" --query 'Invalidation.Id' --output text >/dev/null

echo "== 5/5 smoke test"
curl -fsS "$API_URL/health" && echo
echo
echo "Site:       $SITE_URL"
echo "API:        $API_URL"
echo "Scoreboard: $SITE_URL/#standings    Proctors: $SITE_URL/#keymaker"
echo "CloudFront can take a few minutes to serve the first deploy; re-run scripts/smoke.sh until it passes."
