# Network baseline format: te-change-assurance

The baseline records how the network behaves as ThousandEyes measures it, so a
later check can tell an intended change from drift. Save one for the whole
network (`te-network-baseline.yaml`) and one per change record (the pre-change
file). Keep it in Git: sorted, one field per line, no secrets. The IDs below
are illustrative.

## Example

```yaml
# te-network-baseline.yaml
baseline_version: "1"
account_group: "Production"
captured_at: "2026-11-02T00:00:00Z"
reason: "monthly baseline"            # or "CHG0012345 pre-change"
windows: {long: "24h", short: "1h"}

paths:                                # per test, agent and direction
  - test_id: "100002"
    test: "BNE01 | Internet | agent-to-server"   # underlay: the site's breakout
    agent: "bne01-ea"
    direction: "to-target"
    networks: ["Provider A (AS 64500)", "Example Transit (AS 64510)", "Example Corp (AS 64496)"]   # in path order
    egress_network: "Provider A (AS 64500)"   # first network past the site edge
    last_hops: ["198.51.100.1", "198.51.100.9", "203.0.113.10"]
    server_ip: "203.0.113.10"
    hops: 11                          # numberOfHops
    path_mtu: 1500                    # only where the result reports it
    mpls: true                        # MPLS labels seen on the path
    dscp_configured: 46               # from get_test dscpId, for tests marked with a DSCP

performance:                          # per test, agent and metric
  - test_id: "100002"
    agent: "bne01-ea"
    metric: "NET_LATENCY"
    aggregation: "MEDIAN"             # MEAN for loss and availability
    long_value: 12.4
    long_worst: 18.0                  # MAXIMUM; MINIMUM for availability
    short_value: 12.1
    rounds: 288

routing:                              # per prefix
  - prefix: "203.0.113.0/24"
    bgp_test_id: "200001"
    reachability_mean_pct: 98.0
    monitors_reaching: 150            # of monitors_total
    monitors_total: 153
    path_changes_long: 0
    updates_long: 2
    origin_asn: 64496                 # last AS in every path
    upstreams: {64500: 0.7, 64501: 0.3}   # AS before the origin, share of monitors
    prepending: false                 # a repeated AS in the paths

dns:                                  # per DNS test
  - test_id: "300001"
    answers: ["203.0.113.10"]
    time_median_ms: 18
```

Overlay tests (agent-to-agent between SD-WAN sites) usually show only the
tunnel endpoints, so record their networks and hops as they appear and keep
the underlay detail on agent-to-server tests like the one above.

## Where each field comes from

| Field | Tool |
|---|---|
| `networks`, `egress_network`, `last_hops`, `server_ip`, `mpls` | `get_full_path_visualization` (hop nodes carry `network` as "Organization (AS n)") |
| `hops`, `path_mtu` | `get_path_visualization_results` (`numberOfHops`; `pathMtu` where the result includes it) |
| `dscp_configured` | `get_test`: `dscpId` is the number, `dscp` the label (for example "Best Effort (DSCP 0)") |
| `performance` | `get_network_app_synthetics_metrics`, grouped by AGENT |
| `routing` reachability, changes, updates | `get_network_app_synthetics_metrics` with `BGP_REACHABILITY`, `BGP_PATH_CHANGES` and `BGP_UPDATES`. Grouped by TEST, the `n` column is the number of monitors behind each row; use this for long windows. Grouped by MONITOR, each row is one monitor (the `SOURCE` column, names in `names.aggregatesMap`) per BGP round, so keep that to a few minutes: an hour for one prefix runs to thousands of rows |
| `routing` origin, upstreams, prepending | `get_bgp_route_test_results` for one round: each monitor's `hops` (`asn`, `asName`) is its AS path, origin last; a row without `hops` has no route |
| `dns` | `get_instant_test_metrics` with result type `dns-server` on the DNS test (it reads scheduled tests too); check that it returns the answers before you rely on them |

## Comparison rules

| Section | Drift when | Severity |
|---|---|---|
| `paths` | A network is added or removed, or `egress_network` changes | HIGH on a critical path, otherwise MEDIUM |
| `paths` | `server_ip` changes | MEDIUM (a move, failover or anycast shift) |
| `paths` | `hops` changes by 3 or more inside the same networks | LOW |
| `paths` | `path_mtu` falls | MEDIUM (new encapsulation, fragmentation risk) |
| `paths` | `dscp_configured` changes | MEDIUM (the test no longer measures the class it did) |
| `performance` | The short-window value is worse than `long_worst` (higher for latency, loss and times, lower for availability), or the regression thresholds in Local context are crossed | MEDIUM |
| `routing` | `monitors_reaching` falls by more than 10% of `monitors_total` against the baseline (a few public monitors routinely lack a route, so compare with the baseline count, not with 100%) | HIGH |
| `routing` | `origin_asn` changes, or a second origin appears | HIGH (possible hijack or misconfiguration) |
| `routing` | A new upstream appears, or the upstream shares move sharply | MEDIUM (possible route leak or policy change); HIGH if traffic now crosses an unexpected network |
| `routing` | Path changes or updates well above the baseline outside any change window | MEDIUM (unstable or changed routing upstream) |
| `dns` | `answers` change | HIGH for critical names |

A deviation is **explained** when an approved change in the change log covers
the object and the time; otherwise it is **unexplained** and goes first.
