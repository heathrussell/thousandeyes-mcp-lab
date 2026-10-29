#!/usr/bin/env bash
# Deletes every onboarding record (the lab's own list of who asked for a ThousandEyes login).
# It does NOT touch ThousandEyes: account groups and users created there stay until you remove them in the TE UI.
set -euo pipefail
: "${AWS_REGION:=ap-southeast-2}"; : "${API_STACK:=te-lab-api}"
TABLE=$(aws cloudformation describe-stacks --region "$AWS_REGION" --stack-name "$API_STACK" --query "Stacks[0].Outputs[?OutputKey=='OnboardTableName'].OutputValue" --output text)
echo "Wiping onboarding table $TABLE in $AWS_REGION"
python3 - "$TABLE" "$AWS_REGION" <<'PY'
import sys, boto3
table = boto3.resource("dynamodb", region_name=sys.argv[2]).Table(sys.argv[1])
n = 0
with table.batch_writer() as batch:
    start = None
    while True:
        kw = {"ProjectionExpression": "email"}
        if start: kw["ExclusiveStartKey"] = start
        page = table.scan(**kw)
        for item in page.get("Items", []):
            batch.delete_item(Key={"email": item["email"]}); n += 1
        start = page.get("LastEvaluatedKey")
        if not start: break
print(f"deleted {n} onboarding records (ThousandEyes itself is unchanged)")
PY
