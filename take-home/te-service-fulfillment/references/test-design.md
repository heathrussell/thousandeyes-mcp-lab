# Acceptance and assurance design: te-service-fulfillment

## Elements to checks

Instant results carry loss, latency and jitter but no path data, so every path
check (egress network, circuit, hub reached, inbound provider) runs on a
scheduled test.

| Element | Check | Test (from -> to) | Instant? | Pass when | Keep as ongoing test |
|---|---|---|---|---|---|
| Site to hubs | The site reaches each hub over the intended path, in both directions, within the SLA | agent-to-agent, site agent -> hub agent, direction set to both (a UI setting) | For a quick loss, latency and jitter reading (`agent-to-agent`, result type `network`; its direction cannot be set); the both-ways check and the path check need the scheduled test | `ONE_WAY_NET_*` within the SLA both ways; the hub reached over the intended circuit or overlay | Yes |
| Site to internet and SaaS | Internet breakout as designed | http-server or agent-to-server, site agent -> SaaS and internet targets | For reachability and timing; the egress check needs the scheduled test | Egress network matches `expected.internet_egress`; latency within target; no errors | Yes, for critical SaaS |
| Site DNS | The resolvers answer correctly and quickly | dns-server, site agent -> the site's resolvers | Yes | Correct answers; `DNS_SERVER_TIME` within target | Yes |
| Circuit SLA | The circuit meets its SLA | agent-to-server, or agent-to-agent to a hub, over that circuit | For loss, latency and jitter; the path check needs the scheduled test | Within the SLA; the first provider network on the path is the circuit's provider | Yes |
| Circuit rate | The ordered rate is delivered | agent-to-agent with TCP throughput measurement, from a server or VM agent at the site to one beyond the provider (a UI setting; Enterprise Agents at both ends; not recommended on Meraki-hosted agents) | No | `ONE_WAY_NET_THROUGHPUT_*` close to the ordered rate, in quiet hours. `NET_CAPACITY` and `NET_BANDWIDTH` from short probes are indicative only: a probe can ride a policer's burst allowance, and circuit load lowers both | Optional |
| Path MTU | The underlay carries the expected MTU | A scheduled network test with path MTU measurement on (a UI setting; `get_test` shows `mtuMeasurements`) | No | `pathMtu` from `get_path_visualization_results`, where the result reports it, equals `expected.path_mtu`; otherwise read the MTU in the ThousandEyes path visualization view | No |
| QoS | The classes survive the provider's network | Tests marked with each class's DSCP (agent-to-server, agent-to-agent or voice; set in the UI) and a voice test | No | DSCP preserved end to end in the ThousandEyes path visualization view (or a path trace DSCP alert stays clear), and voice MOS at or above the spec. A marked test against an unmarked twin proves something only when the path is congested: if both are clean, QoS is untested | The voice test and the DSCP alert |
| SD-WAN edge | Overlay and underlay both work | agent-to-agent between sites (overlay); agent-to-server to the remote tunnel termination points over each transport (underlay, which needs local breakout or a policy that directs the probes over that transport) | For loss, latency and jitter | Both within targets | Yes |
| Interconnect | The private path crosses the interconnect | agent-to-agent or agent-to-server from an on-premises agent to an agent or private address in the cloud or data center | For loss, latency and jitter; the path check needs the scheduled test | The path crosses the interconnect's known hop addresses or prefixes (private interconnect hops often carry private or link addresses with no AS attribution); latency within target | Yes |
| Prefix or peering | The internet routes to the prefix as intended | bgp test on the prefix | No (there are no BGP instant tests): create the scheduled test | Reachable from at least 95% of monitors; origin equals `origin_asn`; upstreams within `expected_upstreams`; path changes settle | Yes |
| Inbound service | Users reach the site's public service | agent-to-server or http-server from Cloud Agents on two or more providers -> the public address | For reachability and timing; the inbound-provider check needs the scheduled test | Reachable; latency within target; inbound through the expected provider | Yes |

Notes:

- **Traffic follows the routing.** A test measures the circuit its traffic
  actually uses. To accept a backup circuit, steer a test target through it
  (a static route or SD-WAN policy for that one target, agreed with the
  commissioning engineer), or test during a planned failover.
- **Settings only in the ThousandEyes UI:** DSCP marking, path MTU, bandwidth
  and throughput measurement, and the direction of agent-to-agent tests. Plan
  them as steps for the user, then confirm with `get_test` (`dscp` and
  `dscpId`, `mtuMeasurements`, `bandwidthMeasurements`).

## Tests the MCP server can create

`create_synthetic_test`, per type. Every type takes a unique `test_name` and
`enabled`; every type except `bgp` also takes an `interval`.

| Type | Fields |
|---|---|
| `agent-to-server` | `agent_ids`, `server` (host name, IP, or host:port), `protocol` (`tcp`, `icmp` or `udp`), `port`, `bgp_measurements` (false for private or local targets) |
| `agent-to-agent` | `agent_ids`, `target_agent_id`, `protocol` (`tcp` or `udp`), `port` |
| `bgp` | `prefix` (CIDR); no `agent_ids` |
| `dns-server` | `agent_ids`, `domain`, `dns_servers` |
| `http-server` | `agent_ids`, `url` |
| `voice`, `sip-server` | The tool accepts them, but they need SIP credentials in the call. Keep credentials out of the conversation: create these in the ThousandEyes UI |

`update_synthetic_test` can later change the name, agents, interval, enabled
state, server, target agent, protocol, port, URL or domain, but not a BGP
prefix, DNS servers or API steps.

## Instant tests

| Instant test | Takes | Result type for `get_instant_test_metrics` |
|---|---|---|
| `agent-to-server` | `server` (host or IP, no port), `protocol` (`tcp`, `icmp` or `udp`), `agent_ids` | `network` |
| `agent-to-agent` | `target_agent_id`, `agent_ids`, `port` (default 49153), `protocol` (`tcp` or `udp`) | `network` |
| `http-server` | `url`, `agent_ids` | `http-server` |
| `dns-server` | `domain`, `dns_servers`, `agent_ids` | `dns-server` |
| `dns-trace` | `domain`, `agent_ids` | `dns-trace` |
| `api`, `page-load`, `web-transactions` | `url` and the type's fields (an api test also takes `requests_config`), `agent_ids` | `api`, `page-load`, `web-transaction` |

## Enterprise Agents on Cisco platforms

A site needs an Enterprise Agent for the inside-out view. On Cisco gear it
runs on supported models only; check the support matrix for the model and its
minimum software.

| Platform | Supported models (examples) | Deploy with | Support matrix |
|---|---|---|---|
| Catalyst switches | Catalyst 9300, 9400, 9350 and 9550; IE3500, IE9310 and IE9320 | Application Hosting, or Catalyst Center at scale | [Switching platforms](https://docs.thousandeyes.com/product-documentation/global-vantage-points/enterprise-agents/installing/cisco-devices/supported-cisco-switching-platforms) |
| Routers | Catalyst 8200, 8200L, 8300, 8500, 8500L, 8550 and 8570; ISR 4221X and 4321 to 4461 (8 GB RAM and 8 GB flash); ISR 1100X-6G; ASR 1000 models; Cisco Secure Routers; industrial routers such as the IR1101 | Application Hosting, or SD-WAN Manager | [Routing platforms](https://docs.thousandeyes.com/product-documentation/global-vantage-points/enterprise-agents/installing/cisco-devices/supported-cisco-routing-platforms) |
| Catalyst SD-WAN edges | Supported routers with at least 8 GB DRAM | SD-WAN Manager (feature template, configuration group, or the ThousandEyes workflow in Manager 20.16 and later) | [Cisco SD-WAN guide](https://www.cisco.com/c/en/us/td/docs/routers/sdwan/17-x/systems-interfaces/systems-interfaces-guide-17-x/monitoring-with-thousandeyes.html) |
| Meraki MX | MX67 and MX68 families, MX75, MX85, MX95, MX105, MX250, MX450, and the C8111, C8121 and C8455 G2 MX models; NAT mode only, no vMX | Meraki dashboard (Meraki Insight, Active Application Monitoring) | [Meraki requirements](https://docs.thousandeyes.com/product-documentation/global-vantage-points/enterprise-agents/installing/cisco-devices/meraki) |
| Nexus | Nexus 9300 (FX, FX2, FX3, GX, GX2), 9400, 9500 (supported fabric modules), 9808 | Application Hosting | [Nexus switches](https://docs.thousandeyes.com/product-documentation/global-vantage-points/enterprise-agents/installing/cisco-devices/nexus-switches) |

Where the agent sits decides what it sees:

- **Catalyst SD-WAN.** Put the agent in a service VPN. ThousandEyes says to
  avoid VPN 0 "as it will limit your ability to test desired networks and
  services"
  ([SD-WAN Manager feature templates](https://docs.thousandeyes.com/product-documentation/global-vantage-points/enterprise-agents/installing/cisco-devices/installation-methods/installing-enterprise-agents-on-cisco-routers-using-sd-wan-manager-feature-templates)),
  and in VPN 0 the router load-balances the probes across all WAN links. From a service VPN the probes follow that VPN's routes: across the
  overlay to the hubs, or out of a local internet breakout if the VPN has one.
  Application-aware routing does not steer the probes; to test a specific
  underlay path, add a policy that directs the probe traffic over it.
- **Meraki MX.** MX 18.104 or later (MX 26.1 or later on the C8000 G2 MX
  models), in NAT mode, with an SD-WAN+ license (agent and test deployment)
  or an Advanced Security license (agent installation only). Agent traffic
  follows the MX routing table, with no local breakout; the agent has an
  internal 198.51.x.x address and uses the DNS servers of the MX uplink; it
  runs only on the primary of an HA pair; and an MX agent cannot be the
  target of an agent-to-agent or voice test. Page load and transaction tests
  are not supported. The agent is enabled in the Meraki dashboard, not
  through the Dashboard API. Meraki does not document whether firewall,
  traffic shaping or uplink selection rules apply to agent traffic: to verify
  those rules, use an agent behind the MX, which the MX treats like any
  client. Sources:
  [ThousandEyes](https://docs.thousandeyes.com/product-documentation/global-vantage-points/enterprise-agents/installing/cisco-devices/meraki),
  [Meraki configuration guide](https://documentation.meraki.com/MI/Meraki_MX_ThousandEyes_Configuration_Guide).
- **Measurements on device-hosted agents.** ThousandEyes does not recommend
  agent-to-agent tests with throughput measurement on agents hosted on Meraki
  appliances
  ([Meraki requirements](https://docs.thousandeyes.com/product-documentation/global-vantage-points/enterprise-agents/installing/cisco-devices/meraki)).
  For circuit rate tests, prefer an agent on a server or VM at the site,
  which also keeps the test load off the network device.

## Measurement notes

- **Bandwidth and capacity** (`NET_BANDWIDTH`, `NET_CAPACITY`) come only from
  Enterprise Agents; no value does not mean zero bandwidth.
- **Throughput** on agent-to-agent tests needs Enterprise Agents at both ends,
  and a test in both directions consumes units for both.
- **One-way latency and jitter** on agent-to-agent tests need clock
  synchronization between the agents. Without it, latency and jitter show no
  data while loss can remain valid; if a firewall drops the sync exchange
  entirely, the test reports nothing. Agent-to-agent tests default to TCP port
  49153, and firewall rules must allow the test both ways
  ([firewall configuration](https://docs.thousandeyes.com/product-documentation/global-vantage-points/enterprise-agents/configuring/firewall-configuration-for-enterprise-agents)).
- **Path MTU** depends on ICMP feedback along the path: use it only where the
  path returned enough information.
- **BGP tests** cost units per prefix per month, independent of the number of
  monitors. Besides public monitors, a router can peer with ThousandEyes as a
  private BGP monitor for the inside-out routing view (set up in the UI).

Sources: [network tests](https://docs.thousandeyes.com/product-documentation/tests/network-tests),
[agent-to-agent tests](https://docs.thousandeyes.com/product-documentation/tests/network-tests/agent-to-agent-test-overview),
[calculating units](https://docs.thousandeyes.com/product-documentation/user-management/usage-and-billing/calculating-units),
[BGP tests](https://docs.thousandeyes.com/product-documentation/tests/bgp-tests).

## Agents

- **Inside out:** the site's Enterprise Agents.
- **Far end:** the hubs' Enterprise Agents, for agent-to-agent tests.
- **Outside in:** Cloud Agents near the site's users, on different networks
  (`list_cloud_enterprise_agents` with `location` or `country_id`, and
  `include_network_details: true`).
- Cap at the tier's agent count; say which agents you dropped and why.

## Alert rule patterns

Before creating a rule, read an existing rule of the same kind with
`get_alert_rule` and copy its `alertType` and expression syntax. Take the
thresholds from the spec's SLA; the expressions below show the syntax with
example values.

| SLA item | `alert_type` | Expression (example values) |
|---|---|---|
| Network latency | `end-to-end-server` | `((avgLatency >= 150 ms))` |
| Packet loss | `end-to-end-server` | `((loss >= 1%))` |
| Jitter | `end-to-end-server` | `((jitter >= 30 ms))` |
| Routing | `bgp` | `((reachability < 90%) || (changes > 3))` |
| Availability (errors) | `http-server` | `((probDetail != ""))` |
| Response time | `http-server` | `((responseTime >= 2000 ms))` |

- **Agent-to-agent rules** have no pattern here: copy the `alert_type` and
  expression from an existing agent-to-agent rule, and set a `direction`
  (`to-target`, `from-target` or `bidirectional`).
- **Defaults:** `rounds_violating_required: 2`, `rounds_violating_out_of: 3`,
  `minimum_sources: 2` for tests that run from two or more agents (a site test
  from a single Enterprise Agent uses 1 source and 3 of 4 rounds instead),
  severity from the spec, `notify_on_clear: true`.
- **Severity** values are lowercase when you create or update a rule (`info`,
  `minor`, `major`, `critical`), although alerts report them in uppercase.
- **Notifications** are a `notifications` object (`email`, `thirdParty`,
  `webhook`, `customWebhook`). No tool maps integration names to IDs, so copy
  the object from an existing rule that uses them, or attach the integrations
  in the ThousandEyes UI.

Expression reference: https://developer.cisco.com/docs/thousandeyes/alert-rule-metadata/#expressions

## Naming

`<site or customer> | <element> | <destination> | <test type>`, for example
`BNE01 | CCT-0001 | SYD-DC | agent-to-agent`. Alert rules:
`<site or customer> | <SLA item>`.
