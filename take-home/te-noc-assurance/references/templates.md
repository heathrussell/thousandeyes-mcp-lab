# Output templates: te-noc-assurance

Use these exactly. Times in UTC. Every row carries the IDs it is based on.

## Health summary (Mode 1)

```text
HEALTH  <account group> (aid <aid>)  <window start> to <window end> UTC

Services
| Service | Criticality | Status | Users affected (sites or locations) | Signal vs normal (test ID, metric, value, normal) | Incident |
|---------|-------------|--------|-------------------------------------|---------------------------------------------------|----------|

Incidents, most impact first
| # | Services and users affected | Since (UTC) | Probable fault domain | Owner | Workaround | Status | Confidence |
|---|-----------------------------|-------------|-----------------------|-------|------------|--------|------------|

Sites
| Site | Criticality | Status | Agents online | Worst signal (test ID, metric, value) | Incident |
|------|-------------|--------|---------------|----------------------------------------|----------|

Circuits and providers
| Site | Circuit | Provider (ASN) | Status | Evidence (tests, agents) | Incident |
|------|---------|----------------|--------|--------------------------|----------|

Routing
| Prefix | Reachability (mean) | Path changes | Status | Evidence (BGP test ID) |
|--------|---------------------|--------------|--------|------------------------|

Evidence per incident: alert IDs, event IDs, outage IDs, anomaly timestamps.
Coincident signals (same time, nothing else shared, not merged): <ID: one line>
Provider outages touching us: <outage IDs and providers, or none>
Noisiest rules this shift: <rule (ID)>: <n> alerts
```

Status values: OK, DEGRADED, DOWN, or NOT OBSERVED (no agent or no data).
Incident status: ONGOING or RECOVERED. If there are no active alerts, ongoing
events or provider outages, say so in one line, then list the three most
recent cleared alerts (last 24 hours).

## Incident brief (Mode 2)

```text
INCIDENT BRIEF  <service, or network object if no service is affected>  (alert <id>, tests <ids>)
Impact:       <services> for <users: sites or locations>; <what users see: failing sign-in, slow page, dropped calls>
Severity:     <metric> at <value> against normal <range> on <test type> to <target>
Since:        <real onset, UTC> (<duration>); alert first seen <UTC>
Status:       ONGOING | RECOVERED (<rule met at UTC>)
Vantage:      affected <n> of <m> (<sites, ISPs, Enterprise, Cloud or Endpoint>); unaffected <n> (<who>)
Fault domain (probable): <a domain from the fault isolation table>
Where:        <hop and network (AS), failing step, page or domain, or timing split>
Evidence:     <2 to 4 lines: path, metrics, detailed results, BGP, outage IDs, event IDs, anomaly timestamps>
Device side:  <findings from Catalyst Center, Meraki or other controllers, or "not checked">
Ruled out:    <next most likely domain> because <evidence>
Workaround:   <option and the evidence it would work, or "none found">
Owner:        <team or provider>, given <the evidence they need; snapshot suggested>
Tell users:   <one plain line>
Confidence:   <high | medium | low> because <reason>
Checks:       <n> tool calls; skipped <checks> because <evidence>
```

## Noise report (Mode 3)

```text
NOISE REVIEW  <account group>  <window> UTC  (<n> alerts, <n> rules, <n> tests)

| Rule (ID) | Test (ID), interval | Service | Site or circuit | Severity | Alerts | Per day | Median duration | Longest | Cleared after one round | Flapping | Recommendation | Apply in |
|-----------|---------------------|---------|-----------------|----------|--------|---------|-----------------|---------|-------------------------|----------|----------------|----------|

ThousandEyes optimizations (read-only through MCP, apply in the UI):
- <rule (ID)>: <what it recommends> <optimization.uiUrl>
- Optimization data unavailable for: <rules, or none>

Estimated effect (from alert durations only): <statement>, labeled as an estimate.
Detection delay added: <minutes per rule changed>
Keep as is: <rules that look noisy but caught real problems, and why>
```

## Service levels (Mode 4)

```text
SERVICE LEVELS  <period> (elapsed <n>%)  as of <time> UTC

Services against SLO
| Service | SLO | Measured | Budget used | Burn rate | Status | Evidence | Action, owner |
|---------|-----|----------|-------------|-----------|--------|----------|---------------|

Circuits against provider SLA (end to end; the SLA covers the provider's segment)
| Site | Circuit | Provider | SLA (latency / loss / jitter / availability) | Measured | Breaches (UTC, value) | Status | Evidence (tests, agents) |
|------|---------|----------|----------------------------------------------|----------|-----------------------|--------|--------------------------|

Status: OK, AT RISK, BREACHED, or CANNOT VERIFY (the budget is under one round).
Method and sample sizes: <one line per row: interval, rounds counted, rounds counted unavailable, rounds left out>.
```

## Coverage matrix (Mode 5)

```text
ASSURANCE COVERAGE  <account group>  as of <time> UTC  (map: <file> | derived)

| Object | Kind | Requirement | Status | Evidence (agent, test or rule IDs) | Fix |
|--------|------|-------------|--------|------------------------------------|-----|

Kinds: service, dependency, site, circuit, hub, prefix, alerting.
Status: COVERED, PARTIAL, BLIND, or UNKNOWN (cannot tell whether it exists or is observed).

Blind and unknown, worst first:
1. <object>: <what is not observed> -> <suggested test: type, agents, target, interval> (activate with te-service-fulfillment)

Summary: <n> services, <n> dependencies, <n> sites, <n> circuits, <n> hubs, <n> prefixes: <covered> covered, <partial> partial, <blind> blind, <unknown> unknown
```
