# Checks by change type: te-change-assurance

For each kind of change: the checks to plan, the ThousandEyes evidence for
them, and the traps. Every change also gets a smoke test per service in scope
and the standard no-regression checks on the critical journeys and paths.

## Network changes

| Change | Must-change checks (examples) | Evidence | Watch out for |
|---|---|---|---|
| Routing or BGP policy: advertisements, communities, local preference, prepends | The prefix stays reachable; the origin and upstreams are as intended; inbound and outbound traffic use the intended providers | BGP tests: `BGP_REACHABILITY`, `BGP_PATH_CHANGES` and `BGP_UPDATES` grouped by TEST, and by MONITOR for a few minutes before and after; AS paths per monitor from `get_bgp_route_test_results`; paths from Cloud Agents to the prefix (inbound); paths from site agents (outbound egress) | Convergence creates updates and path changes for a few minutes: judge the settled state. Communities and local preference are not in the route data: judge them by their effect on the paths |
| Circuit or ISP migration | The site's traffic leaves through the new provider; latency, loss and jitter within the SLA; path MTU as designed | Site agents' agent-to-server tests: the first provider network on the path and `NET_*`; agent-to-agent tests to the hubs; `pathMtu` from `get_path_visualization_results` where reported; page-load or transaction tests from the site | Traffic landing on the backup circuit; an asymmetric return path; an MTU black hole (network tests and handshakes pass while page loads and transfers stall) |
| Firewall, ACL or NAT | The service answers on its ports from the sites that need it | Scheduled agent-to-server tests with `protocol: tcp` and the service `port`; HTTP tests (`WEB_CONNECT_ERROR_COUNT`). For destination NAT, test the translated address and port; for source NAT, check the agents' `publicIpAddresses` | An agent-to-server instant test cannot set a port: use an http-server instant test with the port in the URL, or the scheduled test. ICMP-only tests miss port changes. ThousandEyes proves what its agents can reach, not what is blocked for everyone else |
| SD-WAN policy: application-aware routing, transport preference, local breakout | Each traffic class uses the intended transport or egress | Site agents' paths: the egress network for internet and SaaS targets; agent-to-agent tests over the overlay; each transport's metrics | The overlay hides the underlay hops: test both. Application-aware routing steers the agents' probes only when a policy sequence matches them (by DSCP, prefix or port, for example): check which transport they took before trusting them for a class |
| QoS policy | Markings survive the provider; the real-time class keeps its quality at peak | DSCP changes in the ThousandEyes path visualization view, or a path trace alert rule on hop DSCP; voice tests (`VOIP_MOS`, `VOIP_PDV`, `VOIP_LOSS`); each test's configured DSCP from `get_test` | The MCP path data has no DSCP values. A marked test beats an unmarked twin only on a congested path, and a night window has no congestion, so class treatment is untested, not passed, at verify time: say so, and check again at the next peak |
| Device upgrade, replacement or HA failover | The same paths and performance afterwards | Tests through the device: hop IPs and networks before and after; loss and latency during and after; `agentState` of agents near the device | An agent hosted on the device goes offline for the upgrade: watch from agents elsewhere. With ECMP or a cluster, one bad member fails some agents and flows and not others |
| Data center, cloud or application move | Sites reach the new location within latency targets; the journeys still complete | agent-to-server, HTTP and journey tests from the sites to the new targets; path and latency against the old target's baseline | The old target still answering hides a move that did not happen |
| Security edge or proxy (SSE) | Traffic reaches the internet through the new point of presence within targets | The egress network and location on the paths; HTTP tests through the proxy; `PROXY_NET_*` metrics where tests use a proxy; `WEB_SSL` and `WEB_SSL_ERROR_COUNT` | The first hops on every path change, which is expected. TLS inspection can break certificate pinning for some services only |

## Service and application changes

| Change | Must-change checks (examples) | Evidence | Watch out for |
|---|---|---|---|
| Application release | The journey completes from every region; the changed steps meet their times; no new errors | Journey tests (`WEB_TRANSACTION_COMPLETION`, `WEB_TRANSACTION_TIME`, `API_REQUEST_COMPLETION`, `API_TRANSACTION_TIME`); `get_detailed_test_results` step times and domains against the saved baseline round; `WEB_HTTP_ERROR_COUNT`, `WEB_CONTENT_ERROR_COUNT`; `get_service_map` where tracing is on | A canary or staged rollout serves the new release to some agents only: compare by agent. Content checks in tests may need updating with the release |
| Load balancer or WAF rule | Every pool member answers; legitimate requests pass | HTTP and journey tests from several regions (`WEB_HTTP_ERROR_COUNT`, `WEB_WAIT`); server IPs in the path data | One bad pool member fails a share of rounds, not all: look for partial failure by agent and round. A WAF can block the test agents themselves: check before blaming the rule |
| Certificate rotation | The new certificate is served everywhere and trusted | HTTP tests from every region (`WEB_SSL_ERROR_COUNT`, `WEB_SSL`); the certificate details in the ThousandEyes UI where needed | Some edges or CDN points of presence keep the old certificate; clients that pin certificates fail while the tests pass |
| DNS change | Names resolve to the new answers, quickly, from every site | dns-server tests (`DNS_SERVER_AVAILABILITY`, `DNS_SERVER_TIME`); dns-trace tests for delegation; HTTP tests that resolve the name | TTLs delay the change; caches keep answering with old records: check after the old TTL has passed |
| CDN configuration | Content is served from the intended edges, quickly | page-load tests and their page requests (`get_detailed_test_results`): CDN domains and times; the last-hop networks and server IPs per region | Caches warm slowly: a fresh change looks slower for a while. Behavior differs by region |
| SaaS tenant or identity provider change (SSO, conditional access, tenant region) | Users still sign in and reach the service from every site | Journey tests through sign-in; page requests showing the identity provider's domains; `WEB_AUTHENTICATION_ERROR_COUNT` | Test accounts may be exempt from policies real users hit: say what the test account proves and what it does not |

## Instant tests in the window

| Instant test | Takes | Result type for `get_instant_test_metrics` |
|---|---|---|
| `agent-to-server` | `server` (host or IP, no port), `protocol` (`tcp`, `icmp` or `udp`), `agent_ids` | `network` |
| `agent-to-agent` | `target_agent_id`, `agent_ids`, `port` (default 49153), `protocol` (`tcp` or `udp`) | `network` |
| `http-server` | `url`, `agent_ids` | `http-server` |
| `dns-server` | `domain`, `dns_servers`, `agent_ids` | `dns-server` |
| `dns-trace` | `domain`, `agent_ids` | `dns-trace` |
| `api`, `page-load`, `web-transactions` | `url` and the type's fields, `agent_ids` | `api`, `page-load`, `web-transaction` |

There are no BGP or voice instant tests: watch those through their scheduled
tests. Instant tests have basic options only: no DSCP marking and no path MTU,
bandwidth or throughput measurement. Each run is one round: enough for a smoke
test, not for a loss figure.

## Timing

- Smoke tests: the first round after each step.
- Subtler checks: at least 30 minutes and 3 rounds of each test, whichever is
  longer, compared with the same hours on previous days.
- Routing changes converge over minutes: judge the settled state.
- DNS changes take effect as TTLs expire: check after the old TTL has passed.
- QoS and capacity changes only show under load: recheck at the next business
  peak and say so in the verdict.
