# Commissioning spec format: te-service-fulfillment

The commissioning spec is the request in a form the skill can test, activate
and repeat. Keep one file per commissioning, in Git. Never put credentials in
it. ASNs 64496 to 64511 and the 192.0.2.0/24, 198.51.100.0/24 and
203.0.113.0/24 prefixes are reserved for documentation; replace them with
yours.

## Example: a new branch with two circuits

```yaml
# ThousandEyes commissioning spec, read by te-service-fulfillment.
spec_version: "2"
commission:
  kind: "site"                  # site | circuit | sdwan-edge | interconnect | prefix | service
  name: "Brisbane branch"
  site_code: "BNE01"
  customer: ""                  # for providers and MSPs commissioning a customer service
  tier: "silver"                # gold | silver | bronze, as defined in Local context
  owner: "netops"               # a team name, not a personal email
  change_record: "CHG0012345"

account_group: "Production"     # confirmed with the user before activation

site:
  city: "Brisbane"
  country: "AU"
  devices: ["bne01-edge-1"]     # Cisco edge devices, for device-side checks
  enterprise_agents: ["bne01-ea"]   # empty if the site has none yet

circuits:
  - id: "CCT-0001"
    role: "primary"             # primary | secondary | backup
    type: "dia"                 # dia | mpls | broadband | cellular | p2p
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

expected:
  internet_egress: "CCT-0001"   # a circuit ID (local breakout) or a hub name (backhaul)
  hubs:
    - {name: "SYD-DC", via: "sdwan"}   # how the site should reach each hub
  path_mtu: 1500                # what the underlay should carry

prefixes:                       # public prefixes this commissioning announces
  - {prefix: "203.0.113.0/24", origin_asn: 64496, expected_upstreams: [64500]}

destinations:                   # what the site must reach
  - {name: "Microsoft 365", kind: "saas", url: "https://outlook.office365.com"}
  - {name: "Intranet", kind: "app", url: "https://intranet.example.com"}

dns_servers: ["192.0.2.53"]     # the site's resolvers

qos:                            # optional
  classes:
    - {name: "voice", dscp: 46}
  voice_mos_min: 4.0

alerting:
  severity: "major"
  rounds: "2 of 3"
  notify: ["NOC webhook"]       # integration names only, never URLs or secrets (see test-design.md)

dashboard: true
```

## Commissioning kinds

| Kind | Required fields | What acceptance proves |
|---|---|---|
| `site` | `site`, `circuits`, `expected`, `destinations` | The site reaches its hubs, the internet and its services as designed, within the SLA |
| `circuit` | `site`, one entry in `circuits` | The circuit meets its SLA and carries the traffic it should |
| `sdwan-edge` | `site`, `circuits`, `expected.hubs` | Overlay to the hubs and underlay to the internet both work |
| `interconnect` | `site` (the on-premises end), `destinations` (private cloud or data center targets) | The private path crosses the interconnect and meets its latency target |
| `prefix` | `prefixes` | The internet reaches the prefix as intended |
| `service` | `commission.customer` and the elements of the service | A provider's customer service meets the SLA sold to the customer |

## What the skill adds when it records the commissioning

The commissioning record (see [templates.md](templates.md)) keeps the spec
unchanged and adds the account group ID, every created object ID, the
acceptance and burn-in results and the timestamps. To commission the next site
or customer, copy the spec, change the fields that differ, and run the skill on
the new file.
