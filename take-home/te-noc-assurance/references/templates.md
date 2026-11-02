# Output templates: te-noc-assurance

Use these exactly. Times in UTC. Every row carries the IDs it is based on.

## Network health summary (Mode 1)

```text
NETWORK HEALTH  <account group> (aid <aid>)  <window start> to <window end> UTC

Sites
| Site | Criticality | Status | Agents online | Worst signal (test ID, metric, value) | Incident |
|------|-------------|--------|---------------|----------------------------------------|----------|

Circuits and providers
| Site | Circuit | Provider (ASN) | Status | Evidence (tests, agents) | Incident |
|------|---------|----------------|--------|--------------------------|----------|

Routing
| Prefix | Reachability (mean) | Path changes | Origin and upstreams (if checked) | Status | Evidence (BGP test ID) |
|--------|---------------------|--------------|-----------------------------------|--------|------------------------|

Incidents, most important first
| # | Network object | Affected (agents, tests) | Since (UTC) | Probable fault domain | Confidence | Next action, owner |
|---|----------------|--------------------------|-------------|-----------------------|------------|--------------------|

Evidence per incident: alert IDs, event IDs, outage IDs, anomaly timestamps.
Coincident signals (same time, nothing else shared, not merged): <ID: one line>
Provider outages touching us: <outage IDs and providers, or none>
Noisiest rules this shift: <rule (ID)>: <n> alerts
```

Status values: OK, DEGRADED, DOWN, or NOT OBSERVED (no agent or no data). If
there are no active alerts, ongoing events or provider outages, say so in one
line, then list the three most recent cleared alerts (last 24 hours).

## Incident brief (Mode 2)

```text
INCIDENT BRIEF  <network object>  (alert <id>, tests <ids>)
What:         <metric> breached <threshold> on <test type> to <target>
Since:        <first seen, UTC> (<duration>)
Vantage:      affected <n> of <m> agents (<sites, ISPs, Enterprise or Cloud>); unaffected <n> (<who>)
Fault domain (probable): <site LAN or agent host | WAN edge or circuit | SD-WAN overlay | ISP, transit or peering | routing | security edge | DNS | data center or cloud edge | destination application | provider outage>
Where:        <hop and network (AS) where latency jumps and persists, or where the traces stop>
Evidence:     <2 to 4 lines: path, metrics, BGP, outage IDs, event IDs, anomaly timestamps>
Device side:  <findings from Catalyst Center, Meraki or other controllers, or "not checked">
Ruled out:    <next most likely domain> because <evidence>
Next action:  <one concrete step and owner; for a provider, the evidence to send>
Confidence:   <high | medium | low> because <reason>
```

## Noise report (Mode 3)

```text
NOISE REVIEW  <account group>  <window> UTC  (<n> alerts, <n> rules, <n> tests)

| Rule (ID) | Test (ID) | Site or circuit | Severity | Alerts | Per day | Median duration | Longest | Cleared < 5 min | Flapping | Recommendation | Apply in |
|-----------|-----------|-----------------|----------|--------|---------|-----------------|---------|-----------------|----------|----------------|----------|

ThousandEyes optimizations (read-only through MCP, apply in the UI):
- <rule (ID)>: <what it recommends> <optimization.uiUrl>
- Optimization data unavailable for: <rules, or none>

Estimated effect (from alert durations only): <statement>, labeled as an estimate.
Keep as is: <rules that look noisy but caught real problems, and why>
```

## Service levels (Mode 4)

```text
SERVICE LEVELS  <period> (elapsed <n>%)  as of <time> UTC

Circuits against provider SLA
| Site | Circuit | Provider | SLA (latency / loss / jitter / availability) | Measured | Breaches (UTC, value) | Status | Evidence (tests, agents) |
|------|---------|----------|----------------------------------------------|----------|-----------------------|--------|--------------------------|

Services against SLO
| Service | SLO | Measured | Budget used | Burn rate | Status | Evidence | Action, owner |
|---------|-----|----------|-------------|-----------|--------|----------|---------------|

Status: OK, AT RISK, or BREACHED. Method and sample sizes: <one line per row>.
```

## Coverage matrix (Mode 5)

```text
ASSURANCE COVERAGE  <account group>  as of <time> UTC  (map: <file> | derived)

| Object | Kind | Requirement | Status | Evidence (agent, test or rule IDs) | Fix |
|--------|------|-------------|--------|------------------------------------|-----|

Status: COVERED, PARTIAL, or BLIND.

Blind spots, worst first:
1. <object>: <what is not observed> -> <suggested test: type, agents, target, interval> (activate with te-service-fulfillment)

Summary: <n> sites, <n> circuits, <n> hubs, <n> prefixes, <n> services: <covered> covered, <partial> partial, <blind> blind
```
