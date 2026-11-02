# Output templates: te-change-assurance

Times in UTC. Every row cites the IDs and values it is based on.

## Change assurance plan (Mode 1)

```text
CHANGE ASSURANCE PLAN  <change record>  window <start> to <end> UTC
Change:   <type>: <one line>
Touches:  <sites, devices, circuits, prefixes, services>
Must change (expected outcome): <each item measurable>
Must not change: <each item measurable>

| # | Check | Network object | Evidence (test or instant test, agents) | Pass when | Owner |
|---|-------|----------------|-----------------------------------------|-----------|-------|

Coverage gaps: <affected paths no test observes> -> <instant test or temporary test proposed>
Abort criteria during the window: <list>
Units: <instant tests planned, temporary tests>  approval needed: yes | no
```

## Baseline record (Mode 2)

Saved as `te-change-<change record>-pre.md`.

```text
PRE-CHANGE BASELINE  <change record>  captured <time> UTC  (windows: last 24 h and last 1 h)
Open issues before the change: <alert, event and outage IDs, or none>

Performance
| Test (ID) | Agent (site) | Metric (aggregation) | Value 24 h | Worst 24 h | Value 1 h | Rows |
|-----------|--------------|----------------------|------------|------------|-----------|------|

Paths
| Test (ID) | Agent (site) | Networks crossed | Egress (first provider network) | Last 3 hops | Server IP | Hops | Path MTU (if reported) | DSCP configured (get_test) |
|-----------|--------------|------------------|---------------------------------|-------------|-----------|------|------------------------|----------------------------|

Routing
| Prefix | Reachability (monitors reaching / total) | Path changes | Updates | Origin | Upstreams (share of monitors) | Prepending |
|--------|------------------------------------------|--------------|---------|--------|-------------------------------|------------|
```

## Watch log (Mode 3)

```text
CHANGE WATCH  <change record>
| UTC | MOP step | Check | Result (test or instant test ID, values) | Status | Action |
|-----|----------|-------|------------------------------------------|--------|--------|

Abort criteria hit: <none, or which and when>
```

## Verification report (Mode 4)

```text
CHANGE VERIFICATION  <change record>  window <start> to <end> UTC
Baseline: <file>   Post window: <start> to <end> (<n> rounds)
Open issues before the change: <IDs, or none>

Expected outcome
| Check | Expected | Observed | Verdict | Evidence |
|-------|----------|----------|---------|----------|

No regression
| Test (ID) | Agent | Metric (aggregation) | Before (value / worst) | After (value / worst) | Delta | Verdict |
|-----------|-------|----------------------|------------------------|-----------------------|-------|---------|

Path and routing changes: <test, agent: before -> after; prefix: before -> after>
New alerts or events since the change: <IDs, or none>
Unrelated events in the window: <outage or event IDs, or none>

OVERALL: GO | ROLL BACK | WATCH
Because: <2 to 4 lines of evidence>
Thresholds used: <defaults, or the ones you changed>
Follow-ups: <monitoring to add, move or retire; network map updates>
```

## Drift report (Mode 5)

```text
NETWORK DRIFT  <account group>  as of <time> UTC  (baseline <file>, captured <time>)

| Object | Expected | Observed | Since (UTC) | Explained by (change record) | Severity | Action |
|--------|----------|----------|-------------|------------------------------|----------|--------|

Unexplained deviations first. Severity follows the comparison rules in
baseline-format.md:
HIGH: monitors reaching a prefix fall by more than 10%, the origin changes, a
critical path's networks or egress change, critical DNS answers change, or
traffic crosses an unexpected network.
MEDIUM: a new upstream or a sharp shift in upstream shares, a non-critical path
change, a server IP change, a lower path MTU, a changed DSCP setting, a
performance breach, unusual routing churn.
LOW: hop changes inside the same networks.
```

## Change log entry

Append one line per event, newest last:

```text
<UTC time> | <change record> | <plan | baseline | watch | verify | drift | write> | <object> | <result, or field: old -> new> | evidence <IDs> | approved by <name>
```
