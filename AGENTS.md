# ThousandEyes MCP Lab: agent instructions

This repo is a hands-on lab portal for AI builders (a Cisco ThousandEyes event) plus the API that runs its scoreboard. Read this file before touching anything. `DEPLOY.md` is the runbook; `CURSOR_PROMPT.md` is the task the owner expects you to carry out.

## What is here

| Path | What it is | Edit? |
|---|---|---|
| `site/index.html` | The whole website, one hash-routed page (vanilla HTML/CSS/JS, no framework, no build step at runtime). **Generated** by `src/build.py`. | No. Change `src/shell.html` and rebuild. |
| `site/config.js` | Runtime config: `apiBase` (the API URL) and the event name/date/city. Written by `scripts/deploy.sh`. | Yes, or via env vars to the deploy script. |
| `api/app.py` | One Lambda (Python 3.12, boto3 only): `/checkin`, `/answer`, `/hint`, `/player`, `/leaderboard`, `/discover`, `/health`, optional `/ask`; hands `/onboard` and `/proctor/*` to `onboarding.py`. | Yes, carefully (see rules). |
| `api/onboarding.py` | Attendee onboarding into ThousandEyes: creates an account group per attendee and invites the user (v7 Administrative API), proctor config and the proctor-key gate. | Yes, carefully (see rules). |
| `api/template.yaml` | AWS SAM: HTTP API + Lambda + DynamoDB tables (Players, Config, Onboard) + SSM policy. Parameters: `AllowedOrigin`, `AnthropicApiKey`, `AnthropicModel`, `AnswersB64`, `ProctorKey`, `TeApiBase`. | Yes. |
| `api/tests/` | `test_api.py` (every route offline), `fakes.py` (fake ThousandEyes, DynamoDB and SSM stubs), `devserver.py` (the whole lab on localhost with no AWS). | Yes. |
| `api/checkpoints.json` | The 10 checkpoint questions, hints, points and scoring rules. No answers. | Yes, then rebuild. |
| `api/answers.json` | **Not in git.** `{checkpoint id: [accepted answers]}`. The deploy script passes it to the Lambda as a NoEcho parameter; the build hashes it into the page. Keep a copy somewhere safe; without it `make build` and `make deploy` refuse to run. | Yes, then rebuild and deploy. |
| `infra/hosting.yaml` | CloudFormation: private S3 bucket + CloudFront with origin access control, optional custom domain and Route 53 records. | Yes. |
| `infra/certificate.yaml` | CloudFormation: ACM certificate with Route 53 DNS validation. Deploy in **us-east-1** only. | Yes. |
| `scripts/deploy.sh` | One-shot, idempotent deploy: hosting stack, API stack, config.js, S3 sync, CloudFront invalidation, health check. | Yes. |
| `scripts/smoke.sh` | Post-deploy checks (API health, leaderboard, site, config.js, CORS preflight). | Yes. |
| `scripts/wipe-board.sh` | Deletes every player from the DynamoDB table. | Yes. |
| `scripts/wipe-onboarding.sh` | Deletes the lab's onboarding records (ThousandEyes is untouched). | Yes. |
| `src/shell.html` | The page source: design tokens, CSS, markup with `<!--@PLACEHOLDER@-->` slots, and the app script. | Yes. |
| `src/build.py` | Ports the lab guide HTML into the shell, parses the tool catalogue, builds the search index, hashes answers, writes `site/index.html` and `src/out/index.html`. | Yes. |
| `src/assets/mountain.webp` | Scoreboard artwork, embedded into the page as a data URI by the build. | Yes, then rebuild. |
| `src/guide/*.html` | The verified lab guide content the site is built from. | Only for content corrections. |

## How the pieces fit

- The browser never sees an answer, and neither does the repo. In **local mode** (`apiBase: ""`) the page checks answers against SHA-256 hashes and keeps scores in `localStorage`. In **API mode** the page posts to the API, which checks answers it received at deploy time (`ANSWERS_B64` environment variable, base64 of `api/answers.json`) and keeps the shared leaderboard in DynamoDB. `/health` reports `"answers": true` when the Lambda has them.
- Answer matching uses the same normaliser in both places: lower-case, NFKC, strip quotes, trim, strip trailing `.!?`, remove spaces, underscores and hyphens. `canon()` in `src/shell.html` and `canon()` in `api/app.py` must stay identical. There is a parity test in `DEPLOY.md`.
- Scoring (both places): 100 points per checkpoint, three free tries then −10 per wrong answer, hints −25 (never twice, never after a solve), total never below 0. Change `api/checkpoints.json` `rules` and rebuild; never change one side only.
- Format of `api/answers.json`: `{"cp0": ["first accepted answer", "another accepted variant"], "cp1": ["42", "forty-two"], ...}` (placeholders, not the real answers). One key per checkpoint id in `checkpoints.json`; any listed variant is accepted after normalisation.
- Routes are hash fragments only (`#setup`, `#lab-1` … `#lab-6`, `#build-0` … `#build-3`, `#field`, `#standings`, `#ask`, `#keymaker`). No server-side routing is needed; the site is plain static files.
- CORS: the API's `AllowedOrigin` must equal the site origin (`https://host`, no path). `scripts/deploy.sh` sets it from the hosting stack's output. The proctor page sends an `X-Proctor-Key` header, so that header stays in the HTTP API's `AllowHeaders`.
- Onboarding (API mode only): the Setup page and the Overview show a sign-up form when `/health` says `"onboarding": "ready"`, otherwise a "see a proctor" fallback (always in local mode). `POST /onboard` creates a ThousandEyes account group per attendee and invites the user; `#proctor` (gated by the `ProctorKey` stack parameter) holds the ThousandEyes token (SSM SecureString, never returned by any route), the settings and the list of sign-ups. Details and the ThousandEyes endpoints used are in `api/README.md`.

## Commands

```bash
make build      # python3 src/build.py  -> site/index.html (and src/out/index.html for the Claude artifact)
make test       # python3 api/tests/test_api.py  -> every API route offline (needs api/answers.json)
make dev        # build, then the whole lab on http://127.0.0.1:8787 with no AWS and a fake ThousandEyes
make deploy     # scripts/deploy.sh      -> everything, idempotent (export PROCTOR_KEY first to keep onboarding on)
make smoke      # scripts/smoke.sh
make wipe       # scripts/wipe-board.sh  (clears the leaderboard)
make wipe-onboarding   # clears the onboarding list only
make destroy    # deletes both stacks (empties the bucket first) and the ThousandEyes token parameter
```

Python 3.11+ with `beautifulsoup4` and `lxml` is needed for `make build`; `boto3` for `make wipe`. AWS CLI v2 and AWS SAM CLI for deploys.

## Rules

1. Never put answers, API keys, the proctor key or ThousandEyes tokens into `site/`, `src/shell.html` or git. `api/answers.json` is git-ignored and stays that way. The Anthropic key, the proctor key and the answers are NoEcho stack parameters passed on the command line by `scripts/deploy.sh`; `samconfig.toml` is git-ignored because `sam deploy --guided` writes parameter values into it. Deploy with the script, not with `sam deploy --guided`. The ThousandEyes token is entered on the proctor page and lives only in SSM Parameter Store; no route may ever return it and no code may log it.
2. Keep `canon()` identical in `api/app.py` and `src/shell.html`.
3. Brand: Cisco dark template. Background `#07182D`, text white, headings may use Cisco Blue `#02C8FF`, outlines may use Medium Blue `#0A60FF`. Magenta `#FF007F` and Orange `#FF9000` are decorative only (stripes, dots, bars, outlines), never text. Containers are outlined, never filled. Keep it that way.
4. Copy style: no em dashes anywhere (code, docs, UI copy), plain sentences, Australian spelling (organisation, colour).
5. `site/index.html` is generated. Edit `src/shell.html` or `api/checkpoints.json`, then `make build`, and commit both the source and the generated file.
6. Don't add a framework, a bundler or a backend beyond the Lambda. The page must stay a single self-contained HTML file that works with `apiBase: ""`.
7. Ask the owner before: choosing or changing the custom domain, enabling the front desk (it bills their Anthropic key), changing scoring or questions, or deleting stacks.
8. If `api/answers.json` is missing, ask the owner for it. Do not invent answers and do not reconstruct them from git history.
9. Onboarding writes into the owner's ThousandEyes organisation. Keep every gate (`enabled`, event code, cap, one record per email, the proctor key on every `/proctor` route) and never add a route that creates or changes ThousandEyes objects without the key. Test against `api/tests/fakes.py`, never against the real organisation, unless the owner asks.

## Verifying your work

- After `make build`: open `site/index.html` in a browser with `config.js` present; the hero, chapters and a lab page should render; check in with a handle and answer Lab 1 with `5` (local mode) to see "+100 banked".
- After `make deploy`: `make smoke` must pass; then open the site, check in, answer Lab 1, and confirm the handle appears on `#standings` from a second browser.
- After editing anything in `api/`: `make test` must pass (it stubs DynamoDB and SSM, fakes ThousandEyes and exercises every route), then `make dev` and click through `#setup` and `#proctor` (key `proctor-secret-123`, token `good-token`).
