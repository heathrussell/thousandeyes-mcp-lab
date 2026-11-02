# Fault isolation: te-noc-assurance

Decision tables and evidence rules for Mode 2.

## Compare vantage points

| Affected | Points to |
|---|---|
| Only agents at one site | That site: LAN, WAN edge or its circuit |
| Agents at several sites behind one provider | That provider: ISP, transit or peering |
| Agents across many sites and providers | Near the target: data center or cloud edge, security edge, the application |
| Only Cloud Agents (outside in) | The internet edge, inbound routing, DDoS protection or public DNS |
| Only site-to-site (agent-to-agent) tests | The WAN or SD-WAN overlay between those sites |
| One agent only | That agent or its host |

Compare like with like. A name served from many places (SaaS, CDN, anycast)
can resolve to a different server for each agent and round, and latency moves
with the server. Compare runs that reached the same server IP (`serverIp` in
the path data); with anycast, one IP can be served from different places, so
also compare the network and location of the last hops. Two agents at one
site can use different resolvers: an agent
on a Meraki MX uses the DNS servers of the MX uplink. A pair of agents splits
a site: an agent on the edge device sees the edge and the WAN; an agent
behind it adds the LAN.

## Reading the path data

- **Persistence.** A hop adds the latency only if the higher response time
  persists on every later hop to the target. A single slow or silent hop that
  does not carry forward is usually a router that deprioritizes or ignores
  probes: mention it, do not blame it.
- **Where traces stop.** When the target is unreachable and every trace from
  several agents stops at the same hop or network, the problem is at or just
  past that hop. Pair it with the end-to-end loss from the metrics; the path
  data has no per-hop loss.
- **Networks.** Each hop node carries its network as "Organization (AS n)".
  The first networks past the site edge identify the circuit's provider; MPLS
  labels on hops show a provider's MPLS core.
- **Overlays.** Through an encrypted SD-WAN or IPsec tunnel, the underlay hops
  usually do not appear. Compare with underlay tests from the same site. On
  Catalyst SD-WAN, where the agent sits matters: from a service VPN the
  probes follow that VPN's routes (across the overlay to the hubs, or out of a
  local internet breakout if the VPN has one), while in the transport VPN
  (VPN 0) they are load-balanced across the WAN links. On Meraki MX, agent
  traffic follows the MX routing table.
- **One-way metrics.** Agent-to-agent one-way latency and jitter need clock
  synchronization between the agents. Without it, latency and jitter show no
  data while loss can remain valid; if a firewall drops the sync exchange
  entirely, the test reports nothing. Loss with no latency or jitter points to
  a middlebox such as a stateful firewall.

## Reading the rest

- **Agent type.** "Our network" applies only to our Enterprise Agents. For a
  Cloud Agent, a problem in the first hops points to that agent's location.
- **Offline agents.** An Enterprise Agent that goes offline during an incident
  can mean the site lost its WAN, its host failed, or the agent stopped. Check
  the site's other agents and the device side before calling it.
- **Shared path.** Agents on different networks all affected: near the target.
  Only agents sharing a provider affected: that provider.
- **Clean path, bad response.** A clean path with HTTP errors, slow time to
  first byte or DNS failures puts the problem at the target or in DNS.
- **Planned work.** If a maintenance or change window overlaps, say so first.

## BGP route detail

`get_bgp_route_test_results` for one prefix and one round returns a row per
monitor. Its `hops` list (`asn`, `asName`) is the AS path from the monitor to
the origin, which is the last hop. A row without `hops` has no route; do not
rely on `isActive`.

- **IDs.** The prefix ID comes from an alert whose target type is `prefix`, or
  from `get_instant_test_metrics` with result type `bgp` over a single round.
  The round ID is the `r` of a BGP metric row. Network tests with BGP
  measurements on have the same data for their target's covering prefix.
- **Size.** Both outputs are large (one row per monitor, per round). Ask for
  one prefix and one round at a time. The same goes for BGP metrics grouped by
  MONITOR: each row is one monitor (the `SOURCE` column, names in
  `names.aggregatesMap`) per round, so keep that to a few minutes and group by
  TEST for longer windows.
- **Summarize in code:** the origin AS, the upstreams (the AS before the
  origin) with the share of monitors behind each, prepending (an AS repeated
  in a path), and how many monitors have no route. Compare a round before the
  onset with one after.

## Fault domains

| Domain | Signature |
|---|---|
| Site LAN or agent host | Latency or loss starts in the first hops inside one site |
| WAN edge or circuit | Starts at the site edge or the first hops of the circuit's provider (its AS, any MPLS labels); every test from the site over that circuit |
| SD-WAN overlay | Site-to-site tests degrade while underlay tests from the same sites stay clean |
| ISP, transit or peering | Starts at a provider or peering hop shared by several sites or agents |
| Routing | BGP reachability drops, the origin or upstreams change, traffic takes a new path |
| Security edge | Path ends at a firewall, proxy or SSE hop; TCP fails while ICMP passes |
| DNS | Resolution fails or slows while the path is clean |
| Data center or cloud edge | Every vantage point degrades near the target network |
| Destination application | Clean path, bad HTTP responses or slow time to first byte |
| Provider outage | A matching Internet Insights outage on the path (a `net` outage's `asn` among the path's networks); cite its ID |
