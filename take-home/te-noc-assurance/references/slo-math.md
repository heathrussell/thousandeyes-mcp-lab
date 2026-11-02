# Service level math: te-noc-assurance

ThousandEyes measures from its agents' vantage points. Call the result
synthetic availability or latency, not user-measured experience.

## Which metric for which test type

All of these come from `get_network_app_synthetics_metrics`.

| Test type | Availability | Speed | Quality |
|---|---|---|---|
| http-server | `WEB_AVAILABILITY` | `WEB_TTFB` (application), `NET_LATENCY` (network) | `NET_LOSS`, `WEB_TOTAL_ERROR_COUNT` |
| page-load | `WEB_PAGE_LOAD_COMPLETION_RATE` | `WEB_PAGE_LOAD` | `WEB_PAGE_ERROR_COUNT` |
| web-transactions | `WEB_TRANSACTION_COMPLETION` | `WEB_TRANSACTION_TIME` | `WEB_TRANSACTION_ERROR` |
| api | `API_REQUEST_COMPLETION` | `API_TRANSACTION_TIME` | `API_REQUEST_ASSERT_ERROR_COUNT` |
| agent-to-server | none (use loss) | `NET_LATENCY` | `NET_LOSS`, `NET_JITTER` |
| agent-to-agent | none (use loss) | `ONE_WAY_NET_LATENCY_BIDIRECTIONAL` (or the `_TO_TARGET` and `_FROM_TARGET` variants) | `ONE_WAY_NET_LOSS_BIDIRECTIONAL`, `ONE_WAY_NET_JITTER_BIDIRECTIONAL` |
| dns-server | `DNS_SERVER_AVAILABILITY` | `DNS_SERVER_TIME` | |
| voice | | `VOIP_LATENCY` | `VOIP_MOS`, `VOIP_LOSS`, `VOIP_PDV` |
| sip-server | `SIP_AVAILABILITY` | `SIP_RESPONSE_TIME`, `SIP_TOTAL_TIME` | `SIP_TOTAL_ERROR_COUNT` |
| bgp | `BGP_REACHABILITY` | | `BGP_PATH_CHANGES` |

The aggregation types the tool documents are MEAN, MEDIAN, MINIMUM, MAXIMUM and
STDEV, and none of them is a percentile. For a "95th percentile" style target,
compute the percentile yourself from per-agent rows (`group_by: AGENT`), or say
which aggregation you used instead (for example MAXIMUM as a conservative
stand-in).

## Formulas

Let the SLO period be P minutes, the elapsed part E minutes, and the target T
(as a fraction, so 99.9% is 0.999).

- **Error budget (minutes)** = (1 - T) x P.
  Example: 99.9% over 30 days = 0.001 x 43,200 = 43.2 minutes.
- **Attainment** = the mean of the availability values (`v`) over the rows that
  have one, divided by 100 (the metric is a percentage), from a query with
  `aggregation_type: MEAN` and `group_by: TEST`, so each row is already
  averaged across agents. For a per-site or per-circuit SLA, group by AGENT
  instead, so one unreachable agent is not averaged away.
- **Budget used (minutes)** = (1 - attainment) x E.
- **Burn rate** = budget used / ((1 - T) x E). Above 1 means the service is
  spending budget faster than the period allows; at that rate it runs out
  before the period ends.
- **Latency or loss targets:** count the rows within target over all rows with
  a value (each row is a round when `r` steps by the test interval). Treat the
  shortfall against the target share the same way as availability.

## Report the method

For every service, state: the metric and aggregation, the window, the number of
rows with a value and their spacing (one row per round when the spacing matches
the test interval), the rows with no value, and whether you computed with code.
Rows with no value shrink the sample: never count them as good.
