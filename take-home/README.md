# Take-home: ThousandEyes skills for running the network

In Build 1 you wrote `te-triage`: one runbook, as a skill. These four
[Agent Skills](https://agentskills.io/specification) use the same format for
the rest of running a network: in the NOC, around every change, when something
new is commissioned, and when the network is tuned. They run on the same
ThousandEyes MCP server you used in the lab, in Claude Code and the Claude
apps, against your own ThousandEyes organisation.

**Contents:** [The evidence rule](#the-evidence-rule) ·
[The four skills](#the-four-skills) · [The network map](#the-network-map) ·
[Requirements](#requirements) · [Install in Claude Code](#install-in-claude-code) ·
[Install in the Claude apps](#install-in-the-claude-apps) ·
[Safety model](#safety-model) · [Example prompts](#example-prompts) ·
[Files](#files) · [References](#references)

## The Evidence Rule

Today a network change usually ends in limbo: someone checks it by hand, then
everyone waits for the phones. The research says the same:

- 45% of teams surveyed check device configs by hand to verify that a change
  went through, and while 99% have post-change validation processes, only 11%
  apply them every time
  ([EMA, April 2024](https://blog.enterprisemanagement.com/network-automation-strategies-must-include-change-validation),
  354 IT professionals).
- Configuration or change management failure is the most cited cause of major
  network-related outages, at 50%
  ([Uptime Institute 2025 outage analysis, via Network World](https://www.networkworld.com/article/3980366/networking-errors-pose-threat-to-data-center-reliability.html)).

These skills take the opposite approach. If it matters to the business, it has
a ThousandEyes test:

1. **Write down what matters.** The network map lists your sites, circuits,
   hubs and prefixes, and the services the business depends on, each with its
   target: an SLA for a circuit, an SLO for a service.
2. **Give each one a test.** Every one of them should have at least one test
   watching it. `te-noc-assurance` marks each one COVERED, PARTIAL or BLIND and
   suggests a test for every gap.
3. **Measure before and after every change.** `te-change-assurance` writes the
   expected outcome as checks ThousandEyes can measure (what must change, and
   what must not), records the current state, watches the change window,
   measures the changed state with the same tests, and recommends GO, ROLL
   BACK or WATCH. The change owner decides.

No test, no claim: every finding cites the test, agent, alert, event, outage
or rule IDs and the UTC window behind it.

## The Four Skills

| Domain | Skill | What ThousandEyes proves | Modes | Writes to ThousandEyes? |
|---|---|---|---|---|
| NOC and assurance | [`te-noc-assurance`](te-noc-assurance/SKILL.md) | Whether the services the network delivers are working, for whom, and why not: the fault domain, through to a workaround, an owner and recovery; circuit SLAs and service SLOs; blind spots in coverage, dependencies included | Service and network health, Incident isolation, Noise review, Service levels, Assurance coverage | Only when you ask for a change, such as an alert rule tuning, and approve it |
| Change and configuration | [`te-change-assurance`](te-change-assurance/SKILL.md) | That a change, network or not, did what it should and the services it touches still work; drift from the baseline | Plan, Baseline, Watch, Verify, Baseline and drift | Instant tests in the change window and any temporary tests, after approval |
| Service fulfilment | [`te-service-fulfillment`](te-service-fulfillment/SKILL.md) | That a new site, circuit, SD-WAN edge, peering or interconnect meets its SLA, and its users can use their services, before the NOC accepts it | Intent, Plan, Accept, Verdict, Activate, Burn-in, Record | Yes, behind two approval gates: acceptance tests, then activation (one gate, before activation, on the monitoring-only path) |
| Performance and optimisation | [`te-performance-optimization`](te-performance-optimization/SKILL.md) | Where the time goes for users, in the network or not, and which option is better | Performance review, Experiment, QoS and path hygiene, Capacity and trend, Decision support | Only experiment tests, after approval |

Together they follow the network's life: fulfilment proves a new site or
circuit and hands it to the NOC with a baseline; NOC assurance watches it;
change assurance proves every change made to it; performance optimisation
finds what to improve and tests the options, and each improvement goes back
through change assurance.

Two of the six agents in the lab's capstone have a head start here:
`te-change-assurance` covers the pre-change check, and `te-noc-assurance`'s
noise review covers the alert noise auditor.

Each skill is a folder with a `SKILL.md` and a `references/` folder. An agent
sees only each skill's name and description until a request matches one. It
then loads that `SKILL.md`, and opens a reference file only when a step needs
it ([progressive disclosure](https://agentskills.io/specification#progressive-disclosure)).

## The Network Map

All four skills share `te-network-map.yaml`: your sites, their circuits
(provider, provider AS, bandwidth, SLA), hubs, public prefixes (origin and
expected upstreams), critical services and QoS classes, each tied to the
ThousandEyes agents and tests that observe it. It lets a skill scope a change
to a site, attribute a path to a circuit, group alerts by provider, check
coverage, and verify expected behaviour. `te-service-fulfillment` adds to it,
`te-change-assurance` updates it, and `te-noc-assurance` can draft one from what
ThousandEyes already sees. The format is in
[`references/network-map.md`](te-noc-assurance/references/network-map.md)
(the same file ships in every skill). The skills also work without it.

## Requirements

- **A ThousandEyes user or credential with API access.** The MCP server
  requires the **API access** permission, and "access to the MCP server is
  governed by the same controls used for the ThousandEyes API"
  ([ThousandEyes MCP server](https://docs.thousandeyes.com/product-documentation/integration-guides/thousandeyes-mcp-server)),
  so the agent can do what the signed-in user or the credential is allowed to
  do, in its account groups.
- **Enterprise Agents at the sites that matter.** Without one, a site can only
  be tested from the outside in.
- **A client that supports Agent Skills and remote MCP servers:** Claude Code,
  or the Claude apps (claude.ai and Claude Desktop) with code execution turned
  on. Other agents that support the
  [Agent Skills format](https://agentskills.io/specification) can use the
  skills too; the steps name the server's own tools (for example
  `list_alerts`), and a client may add a prefix.
- **A writable folder** for the network map, baselines, the change log, and
  commissioning specs and records.

### ThousandEyes permissions

All four skills run on **API access** plus the **View** permissions. The
optional writes need more:

| Skill | Extra permissions, only for the writes you approve |
|---|---|
| `te-noc-assurance` | **Edit alert rules**, to apply an alert rule tuning |
| `te-change-assurance` | **Edit tests and run instant tests**, for instant tests in the window and any temporary tests |
| `te-service-fulfillment` | **Edit tests and run instant tests**, **Edit alert rules** and **Edit tags** for acceptance and activation, plus a dashboard edit permission if the plan includes a dashboard |
| `te-performance-optimization` | **Edit tests and run instant tests**, for experiments |

Permission names are from
[Built-in roles and permissions](https://docs.thousandeyes.com/product-documentation/user-management/authorization/rb-access-control/built-in-roles-and-permissions).
The ThousandEyes MCP documentation does not map tools to permissions, so try
each skill with your credential before you rely on it. Where a permission is
missing, the tool returns a permission error and nothing changes. Give each
person or agent the least access its skill needs.

Two costs to keep in mind
([ThousandEyes MCP server](https://docs.thousandeyes.com/product-documentation/integration-guides/thousandeyes-mcp-server)):

- **Units.** An instant test consumes units, billed as a single round at
  scheduled-test pricing. Scheduled tests consume units every round until you
  disable them. That is why both need approval.
- **Rate limit.** API keys and OAuth bearer tokens share the organisation-wide
  API rate limit, typically 240 requests per minute. Each OAuth 2.0 client has
  its own 240 per minute. The skills prefer grouped queries and cap their deep
  dives for this reason.

## Install in Claude Code

1. **Connect the ThousandEyes MCP server** as `thousandeyes`, as in Section 03
   of the lab (Path 2). Use that name: each skill's `allowed-tools` line
   pre-approves its read-only tools as `mcp__thousandeyes__<tool>`.

   ```bash
   claude mcp add --transport http --scope user thousandeyes https://api.thousandeyes.com/mcp
   ```

   Then run `/mcp` in Claude Code, select `thousandeyes`, and finish the
   sign-in in your browser
   ([Claude Code MCP](https://code.claude.com/docs/en/mcp)). If you have also
   added ThousandEyes as a connector in claude.ai, Claude Code can use that
   too, but its tools have a different name, so `allowed-tools` does not
   pre-approve them.

2. **Copy the skills** to your personal skills folder, which makes them
   available in all your projects:

   ```bash
   git clone https://github.com/heathrussell/thousandeyes-mcp-lab.git
   mkdir -p ~/.claude/skills
   cp -R thousandeyes-mcp-lab/take-home/te-* ~/.claude/skills/
   ```

   To share them with a team instead, copy them into a repository's
   `.claude/skills/` folder and commit them
   ([Claude Code skills](https://code.claude.com/docs/en/skills)).

3. **Fill in Local context** in each `SKILL.md`, and write your
   `te-network-map.yaml` (or let `te-noc-assurance` draft one).

4. **Ask in plain language**, for example "network health check for the
   Production account group". Claude loads the skill whose description
   matches. Or invoke one directly: `/te-noc-assurance`.

`allowed-tools` lists read tools only, and Claude Code applies it only during
the turn that invokes the skill: "The grant clears when you send your next
message"
([Claude Code skills](https://code.claude.com/docs/en/skills)). Write tools are
never on the list, so they follow your normal Claude Code permission settings.

## Install in the Claude Apps

For claude.ai and Claude Desktop:

1. **Add ThousandEyes as a custom connector**, as in Section 01 of the lab
   ([custom connectors](https://support.claude.com/en/articles/11175166-getting-started-with-custom-connectors-using-remote-mcp)).
2. **Turn on code execution.** Skills need it: **Settings > Capabilities >
   Code execution and file creation** (labelled **Create and edit files** in
   the updated Settings layout). On Team and Enterprise plans, an Owner turns
   it on under **Organization settings > Plugins & skills**, on the **Policy**
   tab ([Use skills in Claude](https://support.claude.com/en/articles/12512180-use-skills-in-claude)).
3. **Fill in Local context**, then zip each skill folder. The ZIP must contain
   the folder itself, and the folder name must match the skill name:

   ```bash
   cd thousandeyes-mcp-lab/take-home
   mkdir -p dist
   for s in te-*; do python3 -m zipfile -c "dist/$s.zip" "$s"; done
   ```

   `dist/` is ignored by Git. Any zip tool works if it keeps the folder at the
   top of the archive.
4. **Upload each ZIP.** Go to **Customize > Skills**, click **+**, then
   **+ Create skill**, then **Upload a skill**
   ([Use skills in Claude](https://support.claude.com/en/articles/12512180-use-skills-in-claude)).

The `allowed-tools` line is written for Claude Code; the field is experimental
in the Agent Skills specification and support varies between clients, so in
the Claude apps the connector's tool permissions decide what runs without
asking.

## Safety Model

- **Read first.** Every skill gathers evidence with read tools, and only read
  tools are pre-approved.
- **Writes need a request and a yes.** A skill changes ThousandEyes only when
  you ask in the conversation. It shows each change first (object, field,
  current value, new value), waits for approval, applies one change at a time,
  and verifies it.
- **Units need approval.** Instant tests and new scheduled tests consume
  units: change assurance asks before the window, fulfilment asks before the
  acceptance tests and again before activation (only before activation on its
  monitoring-only path), and experiments ask before they run.
- **Recommend, do not decide.** Go, roll back or watch, accept or reject, and
  which option to buy are recommendations with evidence; people decide.
- **Observe the devices, never change them.** Cisco controller MCP servers,
  if you connect them, are used for evidence only. Device changes belong to
  your change process, verified with `te-change-assurance`.
- **No deletes by default.** Only temporary tests and a fulfilment rollback
  of objects the skill itself created, one at a time, with approval.
- **Data, not instructions.** Test names, alert text, event descriptions and
  spec free text are evidence. Instructions found inside them are ignored.
- **Secrets stay out of files.** No credentials, webhook URLs or notification
  recipients in maps, baselines, specs or records.
- **The credential is the control.** Instructions guide the agent; the
  permissions behind the sign-in or token decide what it can do.

## Example Prompts

| Skill | Try |
|---|---|
| `te-noc-assurance` | "Network health check for the Production account group." · "Is Brisbane slow because of us or Provider A?" · "Diagnose alert `<alert ID>` and tell me what to send the ISP." · "Which circuits missed their SLA this month?" · "Where are our blind spots?" |
| `te-change-assurance` | "Plan the ThousandEyes checks for `<change record>`: tonight we move BNE01's internet breakout from Provider A to Provider B." · "Baseline before the change." · "Step 3 of the MOP is done, check it." · "The change is finished: go or roll back?" · "Has anything drifted from the network baseline?" |
| `te-service-fulfillment` | "Commission the new Brisbane branch: DIA from Provider A, broadband backup, SD-WAN to SYD-DC, Silver tier." · "Accept circuit `<circuit ID>` against its SLA." · "Is our new prefix visible with the right origin and upstreams?" |
| `te-performance-optimization` | "Why is Perth slower than Sydney to Microsoft 365?" · "Test local breakout against backhaul for Microsoft 365 from BNE01." · "Is voice QoS honoured across Provider A?" · "Will BNE01's circuit run out of headroom this quarter?" · "Provider A or B for the new site?" |

## Files

```text
take-home/
├── README.md                          this file
├── te-noc-assurance/
│   ├── SKILL.md
│   └── references/                    fault isolation, network map, SLO maths, API notes, report templates
├── te-change-assurance/
│   ├── SKILL.md
│   └── references/                    baseline format, checks per change type, network map, API notes, templates
├── te-service-fulfillment/
│   ├── SKILL.md
│   └── references/                    network map, commissioning spec, test design, API notes, templates
└── te-performance-optimization/
    ├── SKILL.md
    └── references/                    optimisation levers, network map, API notes, templates
```

## References

- [Agent Skills specification](https://agentskills.io/specification):
  folder layout, frontmatter fields and limits, progressive disclosure
- [Claude Code skills](https://code.claude.com/docs/en/skills): skill
  locations, invocation, `allowed-tools`
- [Claude Code MCP](https://code.claude.com/docs/en/mcp): `claude mcp add`,
  scopes, OAuth sign-in with `/mcp`
- [Use skills in Claude](https://support.claude.com/en/articles/12512180-use-skills-in-claude):
  plans, code execution, uploading skills
- [Custom connectors using remote MCP](https://support.claude.com/en/articles/11175166-getting-started-with-custom-connectors-using-remote-mcp)
- [ThousandEyes MCP server](https://docs.thousandeyes.com/product-documentation/integration-guides/thousandeyes-mcp-server):
  URL, authentication, permissions, rate limits, units, client setup
- [ThousandEyes built-in roles and permissions](https://docs.thousandeyes.com/product-documentation/user-management/authorization/rb-access-control/built-in-roles-and-permissions)
- [EMA: Network automation strategies must include change validation](https://blog.enterprisemanagement.com/network-automation-strategies-must-include-change-validation)
- [Network World: Networking errors pose threat to data center reliability](https://www.networkworld.com/article/3980366/networking-errors-pose-threat-to-data-center-reliability.html)
