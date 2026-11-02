# Output templates: te-performance-optimization

Times in UTC. Every figure names its metric, aggregation, window and the rounds
or data points behind it.

## Network scorecard (Mode 1)

```text
NETWORK PERFORMANCE  <scope>  <this period> vs <previous period>

| Site or circuit | Path or test (ID) | Metric | Target | This period | Previous | Change | Where latency accrues | Status |
|-----------------|-------------------|--------|--------|-------------|----------|--------|-----------------------|--------|

Status: MEETS, AT RISK, or MISSES.

Top opportunities
1. <object>: <finding>. Evidence: <tests, agents, rows, path segment>. Lever: <action>. Expected effect: <range> (estimate). Prove it with: <experiment or check>
2. ...
3. ...

Last mile and Wi-Fi (Endpoint Agents): <summary by location or network, or "no Endpoint data">
Method: <metrics, aggregations, rows per test; computed with code: yes | no>
```

## Experiment report (Mode 2)

```text
EXPERIMENT  <question>
Hypothesis: <option A beats option B on <metric> by at least <amount>>
Design:     <options, agents, targets, test type, runs or window, metric, aggregation>
Units:      <instant tests or temporary tests>, approved by <name>

| Option | Runs or rows | Median | p25 to p75 | Max | Loss | Jitter | Notes |
|--------|--------------|--------|------------|-----|------|--------|-------|

Difference:     <median A - median B> (<percent>); spread overlap: none | partial | full
Verdict:        A better | B better | no meaningful difference | inconclusive, because <reason>
Recommendation: <action>. Make the change through te-change-assurance and verify it afterwards.
```

## QoS and path report (Mode 3)

```text
QOS AND PATH HYGIENE  <scope>  <window>

| Test (ID) | Agent (site) | Check | Expected | Observed | Where (hop, network) | Verdict | Fix |
|-----------|--------------|-------|----------|----------|----------------------|---------|-----|

Checks: DSCP preserved, class treatment at peak, path MTU, symmetry (to
target versus from target), detours (latency against distance), egress as
designed.
```

## Capacity outlook (Mode 4)

```text
CAPACITY OUTLOOK  <scope>  history <start> to <end> (<n> weeks)

| Site or circuit | Metric | Weekly median now | Slope per week | Fit | Threshold | Projected crossing | Peak vs off-peak |
|-----------------|--------|-------------------|----------------|-----|-----------|--------------------|------------------|

Congestion signatures: <tests where latency, jitter and loss rise in business hours>
Early drift (anomalies, last 7 days): <test, metric, timestamp>
Recommendations: <action, by when, evidence>
These are projections from <n> weeks of history, not forecasts.
```

## Decision memo (Mode 5)

```text
DECISION MEMO  <decision>
Options: <A>, <B>, ...   Window: <start> to <end>   Weights: <criterion: weight> (<source>)

| Criterion (weight) | <A> | <B> | Evidence |
|--------------------|-----|-----|----------|
| Latency (w)        |     |     | <metric, agents, rows> |
| Loss (w)           |     |     | |
| Jitter (w)         |     |     | |
| Availability (w)   |     |     | |
| Outage history (w) |     |     | <outage IDs> |
| Cost (w)           |     |     | <from the user> |
| Weighted score     |     |     | normalized 0 to 1 |

Recommendation: <option>, confidence <high | medium | low> because <reason>
Sensitivity: <does the winner change if any weight moves by 0.1?>
Risks: <list>
Measure success with: <tests and alert rules; te-service-fulfillment can commission them, te-change-assurance verifies the change>
```
