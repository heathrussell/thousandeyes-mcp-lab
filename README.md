# ThousandEyes MCP Lab

A hands-on lab portal for AI builders: connect an AI client to the hosted ThousandEyes MCP server, run six labs and three builds, bank points at ten checkpoints, watch the live scoreboard. Attendees get their own ThousandEyes login from the Setup page (an account group each under the lab organisation, configured by the proctors on `#proctor`). Cisco dark brand, one static page, one small API.

- **Deploying with Cursor**: open this folder in Cursor, then follow `CURSOR_PROMPT.md`.
- **Deploying by hand**: `DEPLOY.md`.
- **How it is put together and the rules for changing it**: `AGENTS.md`.

```
site/     the website (generated; edit src/ instead)      api/      scoreboard + onboarding API (AWS SAM), offline tests
infra/    hosting + certificate stacks (CloudFormation)   scripts/  deploy, smoke test, wipe board / onboarding list
src/      page source, build script, the lab guide        Makefile  build · test · dev · deploy · site · smoke · wipe · destroy
```

Quick start, no custom domain:

```bash
export PROCTOR_KEY='something-long-and-private'   # switches on proctor setup and attendee onboarding
AWS_REGION=ap-southeast-2 scripts/deploy.sh && scripts/smoke.sh
```

Try it with no AWS: `make dev`, then open http://127.0.0.1:8787 (proctor key `proctor-secret-123`, fake ThousandEyes token `good-token`).

Local-score mode (no AWS at all): serve `site/` from any static host with `apiBase: ""` in `site/config.js`.
