# Service level math: te-noc-assurance

ThousandEyes measures from its agents' vantage points. Call the result
synthetic availability or latency, not user-measured experience, unless it
comes from Endpoint Agents.

## Which metric for which test type

All of these come from `get_network_app_synthetics_metrics`. For a service
with a journey test (web-transactions or api), measure the SLO on the journey:
it is closest to what users do.

| Test type | Availability | Speed | Quality |
|---|---|---|---|
| web-transactions | `WEB_TRANSACTION_COMPLETION` | `WEB_TRANSACTION_TIME` | `WEB_TRANSACTION_ERROR` |
| api | `API_REQUEST_COMPLETION` | `API_TRANSACTION_TIME` | `API_REQUEST_ASSERT_ERROR_COUNT` |
| page-load | `WEB_PAGE_LOAD_COMPLETION_RATE` | `WEB_PAGE_LOAD` | `WEB_PAGE_ERROR_COUNT` |
| http-server | `WEB_AVAILABILITY` | `WEB_TTFB` (application), `NET_LATENCY` (network) | `NET_LOSS`, `WEB_TOTAL_ERROR_COUNT` |
| agent-to-server | none (use loss) | `NET_LATENCY` | `NET_LOSS`, `NET_JITTER` |
| agent-to-agent | none (use loss) | `ONE_WAY_NET_LATENCY_BIDIRECTIONAL` (or the `_TO_TARGET` and `_FROM_TARGET` variants) | `ONE_WAY_NET_LOSS_BIDIRECTIONAL`, `ONE_WAY_NET_JITTER_BIDIRECTIONAL` |
| dns-server | `DNS_SERVER_AVAILABILITY` | `DNS_SERVER_TIME` | |
| voice | | `VOIP_LATENCY` | `VOIP_MOS`, `VOIP_LOSS`, `VOIP_PDV` |
| sip-server | `SIP_AVAILABILITY` | `SIP_RESPONSE_TIME`, `SIP_TOTAL_TIME` | `SIP_TOTAL_ERROR_COUNT` |
| bgp | `BGP_REACHABILITY` | | `BGP_PATH_CHANGES` |

None of the aggregation types is a percentile. For a "95th percentile" style
target, compute the percentile yourself from per-agent rows (`group_by:
AGENT`), or say which aggregation you used instead (for example MAXIMUM as a
conservative stand-in).

## Formulas

Let the SLO period be P minutes, the elapsed part E minutes, the target T (as
a fraction, so 99.9% is 0.999) and the test interval I minutes.

- **Error budget (minutes)** = (1 - T) x P. Example: 99.9% over 30 days =
  0.001 x 43,200 = 43.2 minutes.
- **Budget in rounds** = error budget / I. At I = 5 minutes, 43.2 minutes is
  about 8 failed rounds. If the budget is under one round, the test cannot
  verify the target: report failed rounds and their minutes, not a pass.
- **Attainment** = the mean of the availability values (`v`) over the rows
  that count (see Missing rounds), weighted by each row's `n`, divided by
  100, from a query with `aggregation_type: MEAN` and `group_by: TEST`, so
  each row is already averaged across agents. For a per-site or per-circuit
  SLA, or to see which users were hit, group by AGENT instead, so one
  unreachable agent is not averaged away.
- **Budget used (minutes)** = (1 - attainment) x E.
- **Burn rate** = budget used / ((1 - T) x E). Above 1 means the service is
  spending budget faster than the period allows; at that rate it runs out
  before the period ends.
- **Latency or loss targets:** count the rounds within target over all rounds
  that count, from round-level rows (query a day at a time). Treat the
  shortfall against the target share the same way as availability.

## Missing rounds

A round with no value is not a good round. Find them first:

- Keep only rows on the test's round grid. Empty rows before or between
  rounds (seen 60 seconds apart before a 300-second test's first round) are
  not rounds: drop them.
- Over long windows the rows are buckets. A bucket should hold agents x
  bucket length / interval measurements; the shortfall in its `n` is missing
  rounds, and an empty bucket is all missing.

Then decide what each missing round means:

- If the affected agents went offline with their site, or you cannot tell, or
  an incident was open on the service or its path, count the round as
  unavailable (a round with value 0). A site that loses its WAN often takes
  its agent's data with it: dropping those rounds would hide the outage.
- If only the agent or its host failed, or nothing suggests trouble, leave the
  round out and report how many you left out and why.

## Report the method

For every service, state: the metric and aggregation, the window, the test
interval, the rounds that count and the row spacing, the rounds counted as
unavailable, the rounds left out, and whether you computed with code.
