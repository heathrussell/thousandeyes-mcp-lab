# Fault isolation: te-noc-assurance

Evidence rules for the Mode 2 playbook. The SKILL.md says which check to run
next; this file says how to read what comes back.

## Compare vantage points

| Affected | Points to |
|---|---|
| Only agents at one site | That site: LAN, WAN edge or its circuit |
| Agents at several sites behind one provider | That provider: ISP, transit or peering |
| Agents across many sites and providers | Near the target: data center or cloud edge, security edge, the application or a shared dependency |
| Only Cloud Agents (outside in) | The internet edge, inbound routing, DDoS protection or public DNS |
| Only site-to-site (agent-to-agent) tests | The WAN or SD-WAN overlay between those sites |
| Endpoint Agents affected, site and Cloud Agents clean | The user side: Wi-Fi, home network, VPN or the device; compare gateway and VPN metrics |
| Several services sharing one dependency | That dependency: the identity provider, DNS, CDN or shared API |
| One agent only | That agent or its host |

Compare like with like. A name served from many places (SaaS, CDN, anycast)
can resolve to a different server for each agent and round, and latency moves
with the server. Compare runs that reached the same server IP (`serverIp` in
the path data); with anycast, also compare the network and location of the
last hops. Two agents at one site can use different resolvers: an agent on a
Meraki MX uses the DNS servers of the MX uplink. A pair of agents splits a
site: an agent on the edge device sees the edge and the WAN; an agent behind
it adds the LAN.

## Reading the application layer

### http-server timing split

| Signal | Points to |
|---|---|
| `WEB_DNS` high or `WEB_DNS_ERROR_COUNT` up | DNS: the resolver, or the authoritative servers (check with a dns-trace test) |
| `WEB_CONNECT` high (about one network round trip) or `WEB_CONNECT_ERROR_COUNT` up | The network path, or a firewall or load balancer refusing connections |
| `WEB_SSL` high or `WEB_SSL_ERROR_COUNT` up | TLS: certificate, cipher or inspection proxy; if it rises with `WEB_CONNECT`, it is distance |
| `WEB_WAIT` high, `WEB_CONNECT` normal | Server time, not the network (`WEB_WAIT` includes about one round trip, so server time is roughly `WEB_WAIT` minus `WEB_CONNECT`) |
| `WEB_RECEIVE` high | A large or slow response body, or throughput on the path |
| `WEB_HTTP_ERROR_COUNT` or `WEB_CONTENT_ERROR_COUNT` up, timings normal | The application answers wrongly: a release, a backend, or a content check that no longer matches |
| `WEB_AUTHENTICATION_ERROR_COUNT` up | The credentials the test uses, or the identity provider |

Through a proxy or CDN, these timings measure to the proxy or edge, not to
the origin.

### Detailed results (page-load, web-transactions, api)

From `get_detailed_test_results` for one affected agent, one round before
the onset and one after:

- **Which step.** For a transaction or api test, the first step, page or
  assertion that fails or slows. Steps before it worked; that narrows the
  fault to what that step touches.
- **Which domain.** For page requests, group by domain and compare the two
  rounds. A slow or failing domain that is not the service's own is a
  dependency or third party: an identity redirect, a CDN, a script or an API.
- **Whose problem.** Name the domain's owner where you can (the service, the
  identity provider, the CDN, a third party) and whether it is critical to
  the journey or only decorative.
- **Distributed tracing.** For http-server tests with tracing on,
  `get_service_map` names the slow backend service.

## Reading the path data

- **Persistence.** A hop adds the latency only if the higher response time
  persists on every later hop to the target. A single slow or silent hop that
  does not carry forward is usually a router that deprioritizes or ignores
  probes: mention it, do not blame it.
- **Return paths.** Each hop's response time includes that hop's reply
  coming back, which may take a different route. A jump that persists shows
  that latency is real, but the hop where it appears is not always where it
  is added: an asymmetric return path can add it elsewhere. Say so when the
  evidence rests on one path.
- **Where traces stop.** When the target is unreachable and every trace from
  several agents stops at the same hop or network, the problem is at or just
  past that hop. Pair it with the end-to-end loss from the metrics; the path
  data has no per-hop loss.
- **Networks.** Each hop node carries its network as "Organization (AS n)".
  The first networks past the site edge usually identify the circuit's
  provider; MPLS labels on hops show a provider's MPLS core. The link between
  your edge and the provider is often numbered from the provider's address
  space, so your own edge's WAN interface can appear as the provider's
  network: look at the next hops too before blaming the provider.
- **Overlays.** Through an encrypted SD-WAN or IPsec tunnel, the underlay hops
  usually do not appear. Compare with underlay tests from the same site. On
  Catalyst SD-WAN, from a service VPN the probes follow that VPN's routes,
  while in the transport VPN (VPN 0) they are load-balanced across the WAN
  links. On Meraki MX, agent traffic follows the MX routing table.
- **One-way metrics.** Agent-to-agent one-way latency and jitter need clock
  synchronization between the agents. Without it, latency and jitter show no
  data while loss can remain valid; if a firewall drops the sync exchange
  entirely, the test reports nothing. Missing latency with valid loss is a
  measurement gap, not path loss. A firewall that inspects the traffic
  between the agents is a documented cause
  ([Palo Alto App-ID](https://docs.thousandeyes.com/product-documentation/internet-and-wan-monitoring/troubleshooting/palo-alto-firewalls-break-agent-to-agent-clock-synchronization)).

## Reading the rest

- **Agent type.** "Our network" applies only to our Enterprise Agents. For a
  Cloud Agent, a problem in the first hops points to that agent's location.
- **Offline agents.** An Enterprise Agent that goes offline during an
  incident can mean the site lost its WAN, its host failed, or the agent
  stopped. Check the site's other agents and the device side before calling
  it. If the site went down with it, or you cannot tell, count its missing
  rounds as unavailable for the site's services; if only the agent or its
  host failed, those rounds are not observed, not down.
- **Partial failure.** Some agents or flows fail completely while others are
  fine: suspect load balancing or ECMP with one bad member, or a single bad
  backend behind a load balancer. Compare server IPs and paths between the
  failing and healthy agents.
- **Small passes, large fails.** Network tests and TCP handshakes clean while
  page loads or transfers stall: suspect a path MTU black hole.
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
- **Size.** Both outputs are large. Ask for one prefix and one round at a
  time. BGP metrics grouped by MONITOR have one row per monitor (the `SOURCE`
  column, names in `names.aggregatesMap`) per round: keep those to a few
  minutes, and group by TEST for longer windows.
- **Summarize in code:** the origin AS, the upstreams (the AS before the
  origin) with the share of monitors behind each, prepending (an AS repeated
  in a path), and how many monitors have no route. Compare a round before the
  onset with one after.

## Fault domains

| Domain | Signature |
|---|---|
| User side (device, Wi-Fi, home network, VPN) | Endpoint Agents affected while site and Cloud Agents are clean; gateway, Wi-Fi or VPN metrics degraded |
| Site LAN or agent host | Latency or loss starts in the first hops inside one site |
| WAN edge or circuit | Starts at the site edge or the first hops of the circuit's provider (beyond the provider-numbered interconnect); every test from the site over that circuit |
| SD-WAN overlay | Site-to-site tests degrade while underlay tests from the same sites stay clean |
| ISP, transit or peering | Starts at a provider or peering hop shared by several sites or agents |
| Routing | BGP reachability drops, the origin or upstreams change, traffic takes a new path |
| Security edge | Path ends at a firewall, proxy or SSE hop; TCP fails while ICMP passes; TLS errors from inspection |
| DNS | Resolution fails or slows while the path is clean |
| Identity provider | Sign-in steps, auth redirects or authentication errors fail across services that share it |
| Data center or cloud edge | Every vantage point degrades near the target network |
| Application front end | Clean path; `WEB_WAIT` up, HTTP or content errors, or the first transaction step fails |
| Application backend or API | Front end answers, but a later transaction step, an api request step or a traced backend service fails or slows |
| Third party or CDN | A domain the page or journey depends on, owned by someone else, fails or slows |
| Provider outage | A matching Internet Insights outage on the path (a `net` outage's `asn` among the path's networks) or for the SaaS (`app`); cite its ID |
