# Scoreboard API

One Lambda (Python 3.12, boto3 only), one DynamoDB table, one HTTP API, defined in `template.yaml` (AWS SAM).

| Route | Body | Returns |
|---|---|---|
| `POST /checkin` | `{name}` | `{player}` (creates or resumes; names are first come, first served) |
| `POST /answer` | `{name, checkpoint, answer}` | `{correct, player}` |
| `POST /hint` | `{name, checkpoint}` | `{hint, player}` |
| `GET /player?name=` | | `{player}` |
| `GET /leaderboard` | | `{players: [{name, points, solvedCount, updatedAt, lastSolveAt}], total}` |
| `GET /health` | | `{status, checkpoints, answers, ask}` |
| `POST /ask` | `{question, snippets}` | `{answer}`; 404 unless `AnthropicApiKey` is set on the stack |

Scoring, identical to the page: 100 points per checkpoint; three free tries, then −10 per wrong answer; hints −25, never twice and never after a solve; totals never go below 0. Ties on the leaderboard break on more checkpoints solved, then the earlier last solve.

`checkpoints.json` holds the questions, hints, points and scoring rules. The accepted answers live in `answers.json` next to it, which is git-ignored on purpose: `scripts/deploy.sh` base64-encodes it into the `AnswersB64` stack parameter (NoEcho) and the Lambda reads it from `ANSWERS_B64`; `src/build.py` hashes it into the page. `/health` reports `"answers": true` when the Lambda has them. Edit either file, then `make build` and `make deploy`.

Deploying: `scripts/deploy.sh` from the repo root (see `DEPLOY.md`). Avoid `sam deploy --guided` here: it would write the answers and the key into `samconfig.toml`.
