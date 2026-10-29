# Prompt for Cursor's agent

Open this folder in Cursor, start an Agent chat, and paste the block below. The agent will read `AGENTS.md` and `DEPLOY.md`, ask for the few decisions that are yours, run the deploy script, and hand back the URLs.

```
Deploy this project into my AWS account. Steps:

1. Read AGENTS.md and DEPLOY.md first. Do not edit site/index.html by hand; it is generated.
2. Confirm the tooling: `aws sts get-caller-identity`, `sam --version`, `python3 --version`. If anything is missing, tell me how to install it and stop.
3. Ask me, in one message, for:
   - the AWS region (default ap-southeast-2)
   - whether I want a custom domain; if yes, the domain and the Route 53 hosted zone ID
   - whether to enable the front desk (needs an Anthropic API key; it bills that key)
   - the event name, date and city to show on the site
4. If I gave you a domain: deploy infra/certificate.yaml in us-east-1 as described in DEPLOY.md section 2 and capture the certificate ARN.
5. Run scripts/deploy.sh with my answers as environment variables (AWS_REGION, DOMAIN, CERT_ARN, HOSTED_ZONE_ID, EVENT_NAME, EVENT_DATE, EVENT_CITY, ANTHROPIC_API_KEY). Pass the API key only as an environment variable for that command; never write it into a file or commit it.
6. If anything fails, fix the cause and re-run the script (it is idempotent). Ask me before deleting any stack.
7. Run scripts/smoke.sh until it passes (CloudFront can take a few minutes after the first deploy).
8. Run scripts/wipe-board.sh so the leaderboard starts empty.
9. Report back: the site URL, the API URL, the scoreboard URL (#standings) and the proctor page (#keymaker), plus anything I should know. Keep the report short.
```

If you want Cursor to do a dry run first, add: "Do steps 1 to 3 only, then show me the exact commands you would run and wait."
