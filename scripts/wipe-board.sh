#!/usr/bin/env bash
# Deletes every player from the scoreboard table (run before the event, or to clear test handles).
set -euo pipefail
: "${AWS_REGION:=ap-southeast-2}"; : "${API_STACK:=te-lab-api}"
TABLE=$(aws cloudformation describe-stacks --region "$AWS_REGION" --stack-name "$API_STACK" --query "Stacks[0].Outputs[?OutputKey=='TableName'].OutputValue" --output text)
echo "Wiping table $TABLE in $AWS_REGION"
python3 - "$TABLE" "$AWS_REGION" <<'PY'
import sys, boto3
table = boto3.resource("dynamodb", region_name=sys.argv[2]).Table(sys.argv[1])
n = 0
with table.batch_writer() as batch:
    start = None
    while True:
        kw = {"ProjectionExpression": "#k", "ExpressionAttributeNames": {"#k": "key"}}
        if start: kw["ExclusiveStartKey"] = start
        page = table.scan(**kw)
        for item in page.get("Items", []):
            batch.delete_item(Key={"key": item["key"]}); n += 1
        start = page.get("LastEvaluatedKey")
        if not start: break
print(f"deleted {n} players")
PY
