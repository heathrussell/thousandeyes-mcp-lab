# ThousandEyes MCP and measurement notes: te-* skills

Shared by all four te-* skills. Read this before your first ThousandEyes call
in a session. Tool names are as the ThousandEyes MCP server names them
(`list_alerts`, `get_full_path_visualization`, ...); your client may add a
prefix. Where a tool's own description disagrees with this file, the tool's
description wins: it ships with the server and is newer.

## Calling the tools

- **Scope.** If the user names an account group, resolve its `aid` with
  `get_account_groups` and pass it to every call. Otherwise use the default
  account group and say so.
- **Time.** Work in UTC and state every window.
  `get_network_app_synthetics_metrics` accepts relative times (`now`,
  `now-24h`, `now-8w`). `list_events` and `search_outages` take a `window`
  (`24h`, `7d`) or a `start_date` and `end_date` pair. Every other tool needs
  ISO 8601 UTC timestamps (`YYYY-MM-DDTHH:MM:SSZ`), so compute them. Alert
  `start` and `end` are epoch milliseconds; round IDs are epoch seconds.
  Convert before you report.
- **Metrics.** `get_network_app_synthetics_metrics` takes one `metric_id` per
  call and needs `start_date`, `end_date` and `aggregation_type` (MEAN,
  MEDIAN, MINIMUM, MAXIMUM, STDEV; none is a percentile). Use MEAN for
  availability and loss, MEDIAN for latency and times. With
  `filter_dimension: TEST`, put the test IDs in `filter_values`. It returns
  CSV rows where `r` is a time in epoch seconds and `v` the value; a row with
  an empty `v` has no data. `get_endpoint_agent_metrics` needs ISO timestamps
  and spells the deviation STDDEV.
- **Counts.** Use the `total` a list tool returns (for `list_tests`, only when
  it returns no `warnings` and you did not search by `name`). Page until
  `hasMore` is false whenever you need every record. `list_tests` searches by
  `name` fuzzily: keep exact matches only.
- **Budget.** API keys and bearer tokens share one organization-wide rate
  limit (typically 240 requests a minute); each OAuth 2.0 client has its own.
  In a lab, everyone on the shared token draws from it. Prefer one grouped query
  (`group_by` TEST or AGENT) to one call per agent, and cap deep dives at the
  five most important items. List the rest by ID.
- **Large outputs.** Full path visualizations, BGP route results and detailed
  browser results are large. Ask for 15 to 30 minutes of path data, one
  prefix and one round of BGP data, and one agent and one round of detailed
  results at a time. Summarize them in code.

## Running well, attended or not

- **Inventory once per run.** Call `list_cloud_enterprise_agents` and
  `list_tests` once and reuse the result; do not repeat them per question.
- **Instant tests.** They consume units. Outside an approved plan (an
  experiment, a change window, an acceptance run), at most one per run,
  announced before it runs.
- **Least privilege.** For scheduled or headless runs, sign the connector in
  as a dedicated ThousandEyes user whose role can view and use the API but
  not create or delete. A prompt saying "read-only" is a request; a role is a
  control.
- **Other te-* skills.** The four skills hand work to each other (commission
  monitoring, verify a change, investigate a failure). Each is a separate
  download: if the skill named isn't installed, give the user that part as a
  plan in text instead.
- **Keep the record.** Every output cites its IDs and UTC windows, so a later
  reader of the transcript can check it.

## Intervals and rounds

Never assume a test runs every minute. Read each test's `interval` with
`get_test` (or `list_tests` with an `interval` projection) before applying any
threshold. Many production and demo tests run every 300 seconds.

- **Think in minutes, count in rounds.** Every threshold in these skills is
  in minutes. Convert it per test: rounds = minutes / interval, rounded up,
  and never fewer than 1. Say both ("15 minutes, 3 rounds at 300 s").
- **Rows and rounds.** When `r` steps by the test interval, each row with a
  value is one round and `r` is its round ID. Long windows come back in
  buckets instead: a 7-day query returns hourly rows, while a one-day window,
  even a week back, returns one row per round. The `n` column counts the
  measurements behind each row (agents or monitors times rounds): use it for
  the rounds behind a figure, and weight by it when you average rows. Query
  one day at a time when you need single rounds.
- **Off-grid rows.** A response can open with empty rows that are not rounds
  (seen 60 seconds apart before a 300-second test's first round). Keep only
  the rows on the test's round grid before you count anything.
- **Alert lag.** A rule that needs X violating rounds of Y fires X rounds
  after the problem began at the earliest. At 300 s with 2 of 3, the alert's
  first-seen time lags the real onset by 5 to 10 minutes. Start any "before"
  window at least 60 minutes, or 6 rounds, before first seen, whichever is
  longer, and find the real onset in the metrics.
- **Resolution.** A test can miss an outage shorter than its interval, and
  one failed round counts as one whole interval of failure.

## Is there enough data?

State the sample behind every figure, and call a verdict INCONCLUSIVE rather
than stretch thin data.

- **Packets per round.** A network test round sends a short stream of probe
  packets, typically 50 according to ThousandEyes. With 50 packets, one lost
  packet reads as 2% loss.
- **Proving low loss.** To claim loss is below L% when no loss is seen, you
  need about 3 / L packets (the rule of three, 95% confidence): 300 packets
  for 1%, 3,000 for 0.1%. Packets in one burst are not independent, so count
  rounds as well: prefer evidence spread over many rounds. With less, report
  "no loss seen in n packets over r rounds" and leave the target
  INCONCLUSIVE.
- **Proving availability.** An availability target allows (1 - target) x
  period minutes of failure. Divide by the interval to get the allowance in
  rounds. If the allowance is under one round, the test cannot verify the
  target: one failed round breaches it. Report observed failed rounds and
  their minutes instead of a pass.
- **Missing rounds.** A round the test should have run but has no value for
  (an empty row on its grid, or a bucket whose `n` falls short) is not a good
  round. If the affected agents went offline with their site, or you cannot
  tell, or an incident was open on that path or service, count it as
  unavailable. If only the agent or its host failed, or nothing suggests
  trouble, leave it out of the figure and report how many you left out and
  why.
- **Rounds are not independent.** Consecutive rounds repeat the same
  conditions: one 15-minute congestion event is several bad rounds but one
  event. Before any comparison or statistical test, reduce rounds to blocks
  (for example hourly medians), and spread sampling across days and times of
  day rather than packing it into one hour.
- **Like with like.** Compare the same hours of the day (business hours with
  business hours, a 02:00 change window with 02:00 on previous days), the same
  agents, and runs that reached the same server IP. A name served from many
  places (SaaS, CDN, anycast) can resolve to a different server each round.

## Arithmetic

Compute percentages, durations, budgets, deltas, percentiles and scores with
code when you can run it; otherwise show the calculation. Never estimate a
number you can compute.
