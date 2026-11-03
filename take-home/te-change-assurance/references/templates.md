# Output templates: te-change-assurance

Times in UTC. Every row cites the IDs, values and rounds it is based on.

## Change assurance plan (Mode 1)

```text
CHANGE ASSURANCE PLAN  <change record>  window <start> to <end> UTC
Change:   <type>: <one line>
Touches:  <devices, circuits, prefixes, hosts, names, certificates, pools, releases>
Services in scope: <service: why (the dependency the change touches); users>
Smoke tests: <service: test (ID) or instant test, agents>
Must change (expected outcome): <each item measurable>
Must not change: <each item measurable>

| # | Check | Service or object | Evidence (test or instant test, agents, interval) | Pass when | Owner |
|---|-------|-------------------|---------------------------------------------------|-----------|-------|

Coverage gaps: <services or paths no test observes> -> <instant test or temporary test proposed>
Abort criteria during the window: <list, in minutes and checkpoints>
Units: <instant tests planned, temporary tests>  approval needed: yes | no
```

## Baseline record (Mode 2)

Saved as `te-change-<change record>-pre.md`.

```text
PRE-CHANGE BASELINE  <change record>  captured <time> UTC
Windows: <window clock hours> on <n> previous days (matched), and the last 1 h
Open issues before the change: <alert, event and outage IDs, or none>

Journeys
| Service | Test (ID), interval | Agent (site) | Completion (matched) | Time (matched, median) | Steps and domains (saved round ID) | Rounds |
|---------|---------------------|--------------|----------------------|------------------------|------------------------------------|--------|

Performance
| Test (ID), interval | Agent (site) | Metric (aggregation) | Value (matched) | Worst (matched) | Value 1 h | Rounds |
|---------------------|--------------|----------------------|-----------------|-----------------|-----------|--------|

Paths
| Test (ID) | Agent (site) | Networks crossed | Egress (first provider network) | Last 3 hops | Server IP | Hops | Path MTU (if reported) | DSCP configured (get_test) |
|-----------|--------------|------------------|---------------------------------|-------------|-----------|------|------------------------|----------------------------|

Routing
| Prefix | Reachability (monitors reaching / total) | Path changes | Updates | Origin | Upstreams (share of monitors) | Prepending |
|--------|------------------------------------------|--------------|---------|--------|-------------------------------|------------|

Instant-test baselines: <check: instant test ID, result values>
```

## Watch log (Mode 3)

```text
CHANGE WATCH  <change record>
| UTC | Step | Check (smoke first) | Result (test or instant test ID, values) | Status | Action |
|-----|------|---------------------|------------------------------------------|--------|--------|

Abort criteria hit: <none, or which and when>
```

## Verification report (Mode 4)

```text
CHANGE VERIFICATION  <change record>  window <start> to <end> UTC
Baseline: <file> (matched hours)   Post window: <start> to <end> (<minutes>, <n> rounds per test)
Open issues before the change: <IDs, or none>

Smoke tests
| Service | Test or instant test (ID) | Agents | Result | Verdict |
|---------|---------------------------|--------|--------|---------|

Expected outcome
| Check | Expected | Observed | Verdict | Evidence |
|-------|----------|----------|---------|----------|

No regression
| Test (ID) | Agent | Metric (aggregation) | Before (matched value / worst) | After (value / worst) | Delta | Sample (rounds, packets) | Verdict |
|-----------|-------|----------------------|--------------------------------|-----------------------|-------|--------------------------|---------|

Service sign-off
| Service | Sites or regions | Journey completes | Step times vs baseline | Verdict |
|---------|------------------|-------------------|------------------------|---------|

Path and routing changes: <test, agent: before -> after; prefix: before -> after>
Partial failures: <agents or flows failing while others pass, or none>
New alerts or events since the change: <IDs, or none>
Unrelated events in the window: <outage or event IDs, or none>
Not testable now: <for example QoS class treatment until the next peak>

OVERALL: GO | ROLL BACK | WATCH
Because: <2 to 4 lines of evidence>
Thresholds used: <defaults, or the ones you changed>
Follow-ups: <monitoring to add, move or retire; map updates; rechecks at peak>
```

## Drift report (Mode 5)

```text
DRIFT  <account group>  as of <time> UTC  (baseline <file>, captured <time>, hours <matched clock hours>)

| Object (service, path, prefix, name) | Expected | Observed | Since (UTC) | Explained by (change record) | Severity | Action |
|--------------------------------------|----------|----------|-------------|------------------------------|----------|--------|

Unexplained deviations first. Severity follows the comparison rules in
baseline-format.md:
HIGH: a journey no longer completes from a site or region, monitors reaching a
prefix fall by more than 10%, the origin changes, a critical path's networks
or egress change, critical DNS answers change, or traffic crosses an
unexpected network.
MEDIUM: a journey slows past its envelope or depends on a new domain, a new
upstream or a sharp shift in upstream shares, a non-critical path change, a
server IP change, a lower path MTU, a changed DSCP setting, a performance
breach, unusual routing churn.
LOW: hop changes inside the same networks.
```

## Change log entry

Append one line per event, newest last:

```text
<UTC time> | <change record> | <plan | baseline | watch | verify | drift | write> | <object> | <result, or field: old -> new> | evidence <IDs> | approved by <name>
```
