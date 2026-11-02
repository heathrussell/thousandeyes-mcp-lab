# Output templates: te-service-fulfillment

Times in UTC.

## Commissioning plan (end of Step 2)

```text
COMMISSIONING PLAN  <what is commissioned>  (<site or customer>, tier <tier>, account group <name> / <aid>)
Spec: <file>   Defaults used: <list>
Readiness: Enterprise Agent at the site: <name (ID), online> | none (deploy one first, or accept outside-in only)

Acceptance checks
| # | Element | Check | Test (instant or scheduled, type) | From -> to | Pass when | Exists? |
|---|---------|-------|-----------------------------------|------------|-----------|---------|

Ongoing assurance to activate after acceptance
| # | Test name | Type | Agents (IDs) | Interval | Options (DSCP, MTU, bandwidth) | Template |
|---|-----------|------|--------------|----------|--------------------------------|----------|

Alert rules: <name>: <alert_type> <expression>, <X> of <Y> rounds, min sources <n>, severity <s>, tests <#s>  (new | reuse <rule ID>)
Tags: <site:x, circuit:y, provider:z, service:s, owner:o>  (exist | create)
Dashboard: <title> | none
Units: acceptance <n> instant tests; ongoing <n> tests on <n> agents at <interval>
Not automated: <steps for the ThousandEyes UI or the device side, and why>

Run the acceptance tests? (consumes units)
```

## Acceptance results (end of Step 4)

```text
ACCEPTANCE  <what is commissioned>  run <time> UTC

| # | Element | Check | Test (ID) | Agents | Result (values, rounds) | Pass when | Verdict | Evidence |
|---|---------|-------|-----------|--------|-------------------------|-----------|---------|----------|

Verdict per check: PASS, FAIL, or NOT RUN (why).
OVERALL: ACCEPT | ACCEPT WITH EXCEPTIONS (<list>) | REJECT
Provider evidence for each FAIL: <hop and network where loss or latency starts, UTC window, test IDs>

Activate ongoing assurance? (creates <n> tests, <n> rules, <n> tags, <dashboard>; starts ongoing unit consumption)
```

## Burn-in report (Step 6)

```text
BURN-IN  <what is commissioned>  <start> to <end> UTC (<hours> h)

| SLA item | Target | Measured | Rounds | Tests (IDs) | Verdict |
|----------|--------|----------|--------|-------------|---------|

Alerts during burn-in: <IDs, or none>
OVERALL: READY FOR HANDOVER | EXTEND BURN-IN | NOT ACCEPTED
```

## Commissioning record (Step 7)

```text
COMMISSIONING RECORD  <what is commissioned>
Account group: <name> (<aid>)   Approved by: <name>   Change record: <ref>
Commissioned: <time> UTC   Handed over to the NOC: <time> UTC

Spec: <file>, unchanged
Acceptance: <overall, with instant test IDs>
Burn-in: <overall, with values>

Created
| Object | ID | Name |
|--------|----|------|

Network map: <file> updated (<objects added>)
Baseline for te-change-assurance: <file>
Follow-ups: <steps not automated, owners>
Rollback: delete exactly the objects listed under Created, with approval
```
