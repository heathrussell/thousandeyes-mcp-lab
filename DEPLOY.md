# Deploying the ThousandEyes MCP Lab

Three AWS pieces, all created by CloudFormation: a hosting stack (S3 + CloudFront), an API stack (HTTP API + Lambda + DynamoDB), and, only if you want your own domain, a certificate stack in us-east-1. `scripts/deploy.sh` does everything except the certificate and is safe to re-run.

## 0. Prerequisites

- AWS CLI v2, signed in to the target account with permission to create CloudFormation stacks, S3, CloudFront, Lambda, API Gateway, DynamoDB, IAM roles (and Route 53 / ACM if using a domain). Check: `aws sts get-caller-identity`.
- AWS SAM CLI: `brew install aws-sam-cli` or https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html. Check: `sam --version`.
- Python 3.11+ (`python3 --version`). For rebuilding the site: `pip install beautifulsoup4 lxml`. For wiping the board: `pip install boto3`.
- Region: the discovery API used by Lab 1 lives in us-east-1, but the lab stacks can go anywhere. Default is `ap-southeast-2` (Sydney).

## 0b. The answers file

The accepted answers are kept out of git. Before any build or deploy, put `api/answers.json` in place (git-ignored). Format:

```json
{"cp0": ["first accepted answer", "another accepted variant"], "cp1": ["42", "forty-two"], "cp2": ["someFieldName", "some field name"]}
```

One key per checkpoint id in `api/checkpoints.json`; every listed variant is accepted after normalisation (case, spaces, underscores, hyphens, quotes and trailing punctuation are ignored). The deploy script refuses to run without the file, and `/health` on a deployed API says `"answers": true` when the Lambda has them. Keep a copy somewhere safe (password manager, private drive).

## 1. Quick path (CloudFront domain, no custom DNS)

```bash
AWS_REGION=ap-southeast-2 EVENT_NAME="AI Builders" EVENT_DATE="" EVENT_CITY="" scripts/deploy.sh
scripts/smoke.sh
```

The script prints the site URL (`https://dxxxx.cloudfront.net`), the API URL, and the scoreboard and proctor pages. First-time CloudFront creation takes 5 to 10 minutes; the script waits.

## 2. Custom domain (optional)

1. The domain must resolve through a Route 53 hosted zone in this account (or you manage the DNS records yourself; then skip `HOSTED_ZONE_ID` and create a CNAME to the CloudFront domain by hand).
2. Request the certificate in **us-east-1** (CloudFront only accepts certificates from there):
   ```bash
   aws cloudformation deploy --region us-east-1 --stack-name te-lab-cert \
     --template-file infra/certificate.yaml \
     --parameter-overrides DomainName=lab.example.com HostedZoneId=Z0123456789ABC
   CERT_ARN=$(aws cloudformation describe-stacks --region us-east-1 --stack-name te-lab-cert \
     --query "Stacks[0].Outputs[?OutputKey=='CertificateArn'].OutputValue" --output text)
   ```
   Validation is automatic via DNS records written into the zone; the stack completes once the certificate is issued (usually a few minutes).
3. Deploy with the domain:
   ```bash
   AWS_REGION=ap-southeast-2 DOMAIN=lab.example.com CERT_ARN=$CERT_ARN HOSTED_ZONE_ID=Z0123456789ABC scripts/deploy.sh
   ```
   The hosting stack adds the alias and the A/AAAA records; the API's CORS origin becomes `https://lab.example.com`.

## 3. Front desk (optional)

`/ask` answers questions from the guide excerpts the page sends, using the owner's Anthropic key. It bills that key per question. Enable it by passing the key to the deploy (never commit it):

```bash
ANTHROPIC_API_KEY=sk-ant-... scripts/deploy.sh
```

`curl $API_URL/health` shows `"ask": true` when it is on. The model defaults to `claude-haiku-5-5` (`AnthropicModel` parameter in `api/template.yaml`).

## 3b. Proctor key and ThousandEyes onboarding (optional, recommended)

With a proctor key, attendees get their own ThousandEyes login from the Setup page: the API creates an account group per attendee under the lab's ThousandEyes organisation and invites them by email (details in `api/README.md`). Pick a key of 12+ characters and pass it on **every** deploy (export it in the shell you deploy from; a deploy without it switches onboarding off):

```bash
export PROCTOR_KEY='something-long-and-private'
scripts/deploy.sh
```

Then, before the doors open, on the deployed site:

1. Open `$SITE_URL/#proctor` and sign in with the key (it stays in that browser tab only).
2. **Credential**: in ThousandEyes, as an **Organization Admin** of the lab organisation (the one the attendees should land in), go to Manage > Account Settings > Users and Roles > Profile > User API Tokens and copy the OAuth bearer token (https://developer.cisco.com/docs/thousandeyes/authentication). Paste it into "Test and save". The page lists the organisation's account groups, roles and Enterprise Agents if the token works, or tells you why not (a 403 means the user is not an Organization Admin: creating account groups needs "Edit all account groups"). The token is stored as an AWS SSM SecureString, never shown again, and deleted by `make destroy`.
3. **Settings**: tick "Open self-service sign-up", set an event code if you want one (attendees type it; it is shown on the screen in the room), the cap, the account group name template, the attendee's role in their own group (Account Admin is right for Labs 1 and 6), the shared demo account group with live tests (Labs 2 to 5) and the role in it (Regular User), the Enterprise Agents to share into each new group, and an optional welcome note. Save.
4. Watch "Who has signed up" during the event. Failed rows show ThousandEyes' own error and have a Retry; "Onboard by hand" adds a walk-up without the code or the cap. Remove deletes only the lab's record.

`curl $API_URL/health` shows `"proctor": true` and `"onboarding": "ready"` once this is done; `scripts/smoke.sh` checks both. Clean-up after the event is done in ThousandEyes (delete the per-attendee account groups and users); `make wipe-onboarding` clears only the lab's list.

## 4. What the deploy script does, in order

1. `aws cloudformation deploy infra/hosting.yaml` → bucket, CloudFront distribution, optional DNS.
2. `sam build && sam deploy api/` with `AllowedOrigin` set to the site URL (or `ALLOWED_ORIGIN` if you override it), plus the answers, the Anthropic key and the proctor key as NoEcho parameters.
3. Writes `site/config.js` with the API URL and event details.
4. `aws s3 sync site/` to the bucket, uploads `config.js` with `Cache-Control: no-cache`, invalidates CloudFront.
5. `curl $API_URL/health`.

Outputs you may need later:

```bash
aws cloudformation describe-stacks --region ap-southeast-2 --stack-name te-lab-site --query "Stacks[0].Outputs"
aws cloudformation describe-stacks --region ap-southeast-2 --stack-name te-lab-api  --query "Stacks[0].Outputs"
```

## 5. Day-to-day

- **Change the event text or API URL**: edit `site/config.js`, then `make site` (sync + invalidate) or re-run the deploy script with the env vars.
- **Change a question or hint**: edit `api/checkpoints.json`; **change an accepted answer**: edit `api/answers.json`. Either way run `make build` (refreshes the hashes in the page), then `make deploy`.
- **Change the page**: edit `src/shell.html`, `make build`, `make deploy`.
- **Clear the leaderboard** before the event or after testing: `make wipe`. **Clear the onboarding list**: `make wipe-onboarding` (ThousandEyes itself is untouched).
- **Close or reopen sign-up** during the event: the "Open self-service sign-up" tick box on `#proctor`, no deploy needed. **Rotate the proctor key**: re-run the deploy script with a new `PROCTOR_KEY`.
- **Run it all locally** while editing: `make dev` serves the site in API mode on http://127.0.0.1:8787 with a fake ThousandEyes and no AWS (proctor key `proctor-secret-123`, token `good-token`).
- **Tighten CORS** if you ever deployed with `ALLOWED_ORIGIN=*`: re-run the deploy script without it.
- **Tear down**: `make destroy` (empties the bucket, deletes both stacks; the certificate stack is separate).

## 6. Checks

Site: open it, check in with a handle, open Lab 1, type a domain in the Service Finder form, confirm Step B fills, answer `5`, see "+100 banked", open `#standings` in another browser and confirm the handle is on the board.

API, offline (stubs DynamoDB and SSM, fakes ThousandEyes, exercises every route including onboarding; run from the repo root with `api/answers.json` in place):

```bash
make test
```

Onboarding, on the deployed stack: sign in at `#proctor`, use "Onboard by hand" with your own work email, watch the row turn ready, then check the ThousandEyes UI shows the new account group and the invitation email arrives. Remove the row afterwards and delete the account group in ThousandEyes.

Normaliser parity (the page and the API must agree on every accepted answer):

```bash
node -e '
const canon=s=>String(s||"").toLowerCase().normalize("NFKC").replace(/[`"\x27“”‘’]/g,"").trim().replace(/[.!?]+$/,"").replace(/[\s_-]+/g,"");
const bank=require("./api/checkpoints.json"); const ans=require("./api/answers.json"); const v=bank.checkpoints.flatMap(c=>ans[c.id]);
require("fs").writeFileSync("/tmp/js-canon.json", JSON.stringify(v.map(canon)));'
python3 -c '
import json, sys; sys.path.insert(0, "api"); import os; os.environ.setdefault("TABLE_NAME","stub"); os.environ.setdefault("AWS_DEFAULT_REGION","ap-southeast-2")
import app; ans=json.load(open("api/answers.json")); v=[a for c in app.BANK["checkpoints"] for a in ans[c["id"]]]
print("canon parity:", json.load(open("/tmp/js-canon.json")) == [app.canon(a) for a in v])'
```

## 7. Costs and limits

- DynamoDB on demand, one small Lambda, an HTTP API and CloudFront for a room of people: cents for the event. The bucket and distribution cost nothing meaningful at rest.
- API Gateway throttling is set to 25 requests/second, burst 50 (`api/template.yaml`). Raise it for a bigger room.
- There is no authentication on the scoreboard by design: handles are first come, first served and writes are last-writer-wins. Fine for a lab, not for prizes with money on them.
- Onboarding is the one place with write access to something that matters (your ThousandEyes organisation). It is gated by the sign-up switch, the event code, the cap and one record per email, and the proctor routes by the key; the ThousandEyes token never leaves SSM and the Lambda. Keep the event code off the public internet, switch sign-up off after the event, and revoke the token in ThousandEyes when you are done.
