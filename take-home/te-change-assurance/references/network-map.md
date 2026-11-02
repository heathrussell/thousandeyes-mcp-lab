# Network map: te-network-map.yaml

The network map describes the parts of the network that matter and how
ThousandEyes observes each one. All four te-* skills read it.
te-service-fulfillment adds to it when it commissions something,
te-change-assurance updates it after a change, and te-noc-assurance can draft
one from what ThousandEyes already sees. Keep it in Git with the rest of your
network source of truth. Never put credentials or personal data in it.

## Example

```yaml
# te-network-map.yaml: the network as ThousandEyes assures it.
# Names or IDs both work for agents and tests; the skills resolve names.
map_version: "1"
account_group: "Production"            # the skills resolve its aid

sites:
  - name: "Brisbane branch"
    code: "BNE01"
    criticality: "high"                 # high | medium | low
    city: "Brisbane"
    country: "AU"
    enterprise_agents: ["bne01-ea"]     # agents hosted at this site
    controllers:                        # optional: the same site in your controllers
      meraki_network: "Brisbane branch"   # Meraki network name or ID
      catalyst_center_site: "Global/Australia/Brisbane/BNE01"
    sdwan: true                         # site joins the SD-WAN overlay
    circuits:
      - id: "CCT-0001"
        role: "primary"                 # primary | secondary | backup
        type: "dia"                     # dia | mpls | broadband | cellular | p2p
        provider: "Provider A"
        provider_asn: 64500
        bandwidth_mbps: 500
        sla: {latency_ms: 20, loss_pct: 0.1, jitter_ms: 5, availability_pct: 99.95}
      - id: "CCT-0002"
        role: "backup"
        type: "broadband"
        provider: "Provider B"
        provider_asn: 64501
        bandwidth_mbps: 100
    expected_internet_egress: "CCT-0001"  # a circuit ID for local breakout, or a hub name for backhaul
    tests:                              # tests that observe this site
      - "BNE01 | SYD-DC | agent-to-agent"
      - "BNE01 | Microsoft 365 | http-server"

hubs:                                   # data centers, cloud regions, SD-WAN hubs, internet edges
  - name: "SYD-DC"
    kind: "dc"                          # dc | cloud | sdwan-hub | internet-edge
    enterprise_agents: ["syd-dc-ea"]

prefixes:                               # what the internet should see
  - prefix: "203.0.113.0/24"
    origin_asn: 64496
    expected_upstreams: [64500, 64501]
    bgp_test: "203.0.113.0/24 | bgp"

services:                               # destinations the business depends on
  - name: "Microsoft 365"
    kind: "saas"                        # saas | app | dns | voice
    tests: ["BNE01 | Microsoft 365 | http-server"]
    slo: {availability_pct: 99.9, latency_ms: 150}

dscp_classes:                           # QoS classes to verify end to end (optional)
  - {name: "voice", dscp: 46}           # EF
  - {name: "video", dscp: 34}           # AF41
```

ASNs 64496 to 64511 and prefix 203.0.113.0/24 are reserved for documentation;
replace them with yours.

## Fields

| Section | Field | Meaning |
|---|---|---|
| `sites` | `enterprise_agents` | The ThousandEyes Enterprise Agents at the site: its inside-out view |
| `sites` | `controllers` | Optional: the site's Meraki network and Catalyst Center site hierarchy, so device-side evidence joins on the site |
| `sites` | `circuits` | Each WAN or internet circuit, its provider and the provider's ASN, bandwidth and SLA |
| `sites` | `expected_internet_egress` | Where the site's internet traffic should leave: a circuit (local breakout) or a hub (backhaul) |
| `sites` | `tests` | Tests that observe the site |
| `hubs` | `kind`, `enterprise_agents` | Data centers, cloud regions, SD-WAN hubs and internet edges, and their agents |
| `prefixes` | `origin_asn`, `expected_upstreams`, `bgp_test` | How the internet should route to your public prefixes, and the BGP test that watches them |
| `services` | `tests`, `slo` | Critical destinations, the tests that measure them, and their targets |
| `dscp_classes` | `dscp` | QoS markings that should survive end to end |

## How the skills use it

- **Scope.** A site resolves to its agents and tests, a circuit to the tests
  whose paths cross its provider, a prefix to its BGP test.
- **Correlation.** Alerts, events and path faults are grouped by site,
  circuit, provider and hub, not only by test.
- **Circuit attribution.** From a site's agent, the first hops past the site
  edge belong to the circuit's provider. Compare the network of those hops in
  the path data with `provider_asn` to see which circuit carried the traffic.
  Through an encrypted SD-WAN or IPsec overlay, the underlay hops are usually
  hidden inside the tunnel, so pair overlay tests (agent-to-agent between
  sites) with underlay tests (agent-to-server to targets reached outside the
  tunnel).
- **Device side.** When a Meraki or Catalyst Center MCP server is connected,
  `controllers` says which Meraki network and Catalyst Center site to read
  for a site's devices, uplinks, issues and events. Without it, match the
  site's devices by an agent's public IP or host device: an agent's location
  alone can be wrong.
- **Coverage.** Every site, circuit, hub, prefix and service should have at
  least one observing test (te-noc-assurance, Mode 5).
- **Expected behavior.** `expected_internet_egress`, `expected_upstreams`,
  `origin_asn` and `dscp_classes` are what te-change-assurance and
  te-service-fulfillment verify. Drift is measured against the saved
  baseline (te-change-assurance, Mode 5).

## Without a map

The skills still work. They use the Local context in each `SKILL.md`, derive
sites from agent names and locations, circuits from the networks in path data,
and services from test targets. Offer to save what you derived as a draft map
and ask the user to confirm it before relying on it.
