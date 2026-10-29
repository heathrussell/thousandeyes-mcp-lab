# Lab API: scoreboard and ThousandEyes onboarding

One Lambda (Python 3.12, boto3 only; `app.py` plus `onboarding.py`), three DynamoDB tables, one HTTP API, defined in `template.yaml` (AWS SAM).

## Scoreboard routes (`app.py`)

| Route | Body | Returns |
|---|---|---|
| `POST /checkin` | `{name}` | `{player}` (creates or resumes; names are first come, first served) |
| `POST /answer` | `{name, checkpoint, answer}` | `{correct, player}` |
| `POST /hint` | `{name, checkpoint}` | `{hint, player}` |
| `GET /player?name=` | | `{player}` |
| `GET /leaderboard` | | `{players: [{name, points, solvedCount, updatedAt, lastSolveAt}], total}` |
| `GET /health` | | `{status, checkpoints, answers, ask, onboarding, onboardingNeedsCode, proctor}` |
| `POST /ask` | `{question, snippets}` | `{answer}`; 404 unless `AnthropicApiKey` is set on the stack |

Scoring, identical to the page: 100 points per checkpoint; three free tries, then −10 per wrong answer; hints −25, never twice and never after a solve; totals never go below 0. Ties on the leaderboard break on more checkpoints solved, then the earlier last solve.

`checkpoints.json` holds the questions, hints, points and scoring rules. The accepted answers live in `answers.json` next to it, which is git-ignored on purpose: `scripts/deploy.sh` base64-encodes it into the `AnswersB64` stack parameter (NoEcho) and the Lambda reads it from `ANSWERS_B64`; `src/build.py` hashes it into the page. `/health` reports `"answers": true` when the Lambda has them. Edit either file, then `make build` and `make deploy`.

## Onboarding routes (`onboarding.py`)

Attendees type their name and work email on the Setup page. The API then uses the proctor's ThousandEyes credential to create, in the lab's ThousandEyes organisation:

1. an **account group** named from the proctor's template (default `{name} ({email})`), with the chosen Enterprise Agents shared into it (`POST /v7/account-groups`, docs: https://developer.cisco.com/docs/thousandeyes/create-account-group);
2. a **user** with the chosen role in that group, that group as their login account group, and optionally a role in the shared demo account group (`POST /v7/users`, docs: https://developer.cisco.com/docs/thousandeyes/create-user). If the email is already a user of the organisation, the lab's roles are merged into the existing user instead (`GET /v7/users`, then `PUT /v7/users/{id}` with the full merged `accountGroupRoles`, because PUT replaces them wholesale).

ThousandEyes then emails the attendee an activation link (valid for 72 hours).

| Route | Gate | Body or query | Returns |
|---|---|---|---|
| `POST /onboard` | sign-up open, event code, cap | `{name, email, company?, eventCode?}` | `{status: ready \| already, record, sharedAccountGroupName, welcomeNote}`; 403 closed or wrong code, 409 in progress, 429 full, 502 ThousandEyes refused (`detail` says why), 503 not configured |
| `GET /onboard?email=` | | | `{status, record, ...}` or 404 |
| `GET /proctor/config` | key | | `{config, tokenSet, onboarded}` (never the token) |
| `PUT /proctor/config` | key | any of the config fields, plus `teToken` to save a token or `clearToken: true` | `{config, tokenSet}` |
| `GET /proctor/te` | key | | overview using the saved token: `{orgName, accountGroups, roles, agents}` or 502 with a `hint` |
| `POST /proctor/te` | key | `{teToken}` | the same overview for a candidate token, without saving it |
| `GET /proctor/onboarded` | key | | `{records}` |
| `POST /proctor/onboard` | key | `{name, email, company?}` | onboards by hand (ignores the open flag, the code and the cap) |
| `POST /proctor/retry` | key | `{email}` | re-runs a failed onboarding |
| `DELETE /proctor/onboarded?email=` | key | | removes the lab's record only; ThousandEyes is untouched |

"Key" means the `X-Proctor-Key` header must equal the `ProctorKey` stack parameter (constant-time compare). A blank `ProctorKey` disables every proctor route and, with it, onboarding.

Config fields: `enabled`, `eventCode`, `groupNameTemplate` (`{name}`, `{email}`, `{company}`), `ownRoleId` and `ownRoleName`, `sharedAid` and `sharedAccountGroupName`, `sharedRoleId` and `sharedRoleName`, `agentIds`, `maxOnboardings` (0 = no cap), `welcomeNote`, `orgName`. The proctor page fills the ids from the overview, so nobody types them.

Where things live:

- **Config table** (`id = "onboarding"`): everything above except the credential.
- **Onboard table** (one item per email, lower-cased): `name, company, status (pending | ready | failed), aid, accountGroupName, uid, userStatus (invited | added-to-existing), error, attempts, createdAt, readyAt, updatedAt`.
- **SSM Parameter Store**, SecureString `/te-lab/<api stack>/te-token`: the ThousandEyes token. Written by `PUT /proctor/config`, read at onboarding time, never returned by any route, never in DynamoDB, never in git, deleted by `make destroy`.

The ThousandEyes credential must be able to create account groups and users across the organisation: an OAuth bearer token (Manage > Account Settings > Users and Roles > Profile > User API Tokens) from an **Organization Admin** of the lab organisation does, since "Edit all account groups" is an Organization Admin permission. Built-in roles and permissions: https://docs.thousandeyes.com/product-documentation/user-management/authorization/rb-access-control/built-in-roles-and-permissions. ThousandEyes rate-limits the organisation to 240 requests a minute; the client retries once on 429.

## Testing without AWS

- `make test` (`python3 api/tests/test_api.py`): every route against stubbed DynamoDB and SSM and a fake ThousandEyes server (`api/tests/fakes.py`) that speaks the v7 shapes, including the problem+json errors.
- `make dev` (`python3 api/tests/devserver.py`): the built site on http://127.0.0.1:8787 in API mode with the same stubs. Proctor key `proctor-secret-123`; the fake ThousandEyes accepts the token `good-token`. Nothing persists between runs.

Deploying: `scripts/deploy.sh` from the repo root (see `DEPLOY.md`). Avoid `sam deploy --guided` here: it would write the answers, the keys and the proctor key into `samconfig.toml`.
