# ThousandEyes MCP Lab

A hands-on lab portal for AI builders: connect an AI client to the hosted ThousandEyes MCP server, run six labs and three builds, bank points at ten checkpoints, watch the live scoreboard. Cisco dark brand, one static page, one small API.

- **Deploying with Cursor**: open this folder in Cursor, then follow `CURSOR_PROMPT.md`.
- **Deploying by hand**: `DEPLOY.md`.
- **How it is put together and the rules for changing it**: `AGENTS.md`.

```
site/     the website (generated; edit src/ instead)      api/      scoreboard API (AWS SAM)
infra/    hosting + certificate stacks (CloudFormation)   scripts/  deploy, smoke test, wipe board
src/      page source, build script, the lab guide        Makefile  build · deploy · site · smoke · wipe · destroy
```

Quick start, no custom domain:

```bash
AWS_REGION=ap-southeast-2 scripts/deploy.sh && scripts/smoke.sh
```

Local-score mode (no AWS at all): serve `site/` from any static host with `apiBase: ""` in `site/config.js`.
