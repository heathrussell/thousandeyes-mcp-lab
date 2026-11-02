# Checks by change type: te-change-assurance

For each kind of network change: the checks to plan, the ThousandEyes evidence
for them, and the traps. Every change also gets the standard no-regression
checks on the critical paths in scope.

| Change | Must-change checks (examples) | Evidence | Watch out for |
|---|---|---|---|
| Routing or BGP policy: advertisements, communities, local preference, prepends | The prefix stays reachable; the origin and upstreams are as intended; inbound traffic arrives through the intended provider; outbound traffic leaves as intended | BGP tests on the prefixes: `BGP_REACHABILITY`, `BGP_PATH_CHANGES` and `BGP_UPDATES` grouped by TEST for the window, and by MONITOR for a few minutes before and after (one row per monitor per round, so keep it short); AS paths per monitor from `get_bgp_route_test_results` (origin last, upstream before it, prepends as repeats); paths from Cloud Agents to the prefix (inbound provider); paths from site agents (outbound egress) | Convergence creates updates and path changes for a few minutes: judge after several rounds. Communities and local preference are not in the route data: judge them by their effect on the paths |
| Circuit or ISP migration | The site's traffic leaves through the new provider; latency, loss and jitter within the SLA; path MTU as designed | Site agents' agent-to-server tests: the first provider network (AS) on the path and `NET_*`; agent-to-agent tests to the hubs (`ONE_WAY_NET_*`); `pathMtu` from `get_path_visualization_results` where the result reports it; BGP for the site's prefix if it is multihomed | Traffic landing on the backup circuit; an asymmetric return path |
| Firewall, ACL or NAT | The service answers on its ports from the sites that need it | Scheduled agent-to-server tests with `protocol: tcp` and the service `port`; HTTP tests (`WEB_CONNECT_ERROR_COUNT`). For destination NAT, test the translated address and port; for source NAT, check the agents' `publicIpAddresses` (`list_cloud_enterprise_agents`): the path's server IP is only the address the agent targets | An agent-to-server instant test cannot set a port: use an http-server instant test with the port in the URL, or the scheduled test. ICMP-only tests miss port changes. ThousandEyes proves what its agents can reach, not what is blocked for everyone else |
| SD-WAN policy: application-aware routing, transport preference, local breakout | Each traffic class uses the intended transport or egress | Site agents' paths: the egress network for internet and SaaS targets; agent-to-agent tests between sites over the overlay; each transport's metrics | The overlay hides the underlay hops: test both |
| QoS policy | Markings survive the provider; the real-time class keeps its quality at peak | DSCP changes along the path in the ThousandEyes path visualization view, or a path trace alert rule on hop DSCP; voice tests (`VOIP_MOS`, `VOIP_PDV`, `VOIP_LOSS`); each test's configured DSCP from `get_test` (`dscpId`) | The MCP path data has no DSCP values, and DSCP marking is set in the ThousandEyes UI. A marked test against an unmarked twin only proves something when the path is congested: if both are clean, QoS is untested, not passed |
| Device upgrade, replacement or HA failover | The same paths and performance afterwards | Tests through the device: hop IPs and networks before and after; loss and latency during and after; `agentState` of agents near the device | An agent hosted on the device being upgraded goes offline for the upgrade: watch from agents elsewhere |
| DNS change | Names resolve to the new answers, quickly, from every site | dns-server tests (`DNS_SERVER_AVAILABILITY`, `DNS_SERVER_TIME`); dns-trace tests for delegation; HTTP tests that resolve the name | TTLs delay the change; caches keep answering with old records |
| Data center, cloud or application move | Sites reach the new location within latency targets | agent-to-server and HTTP tests from the sites to the new targets; path and latency against the old target's baseline | The old target still answering hides a move that did not happen |
| Security edge or proxy (SSE) | Traffic reaches the internet through the new point of presence within targets | The egress network and location on the paths; HTTP tests through the proxy; `PROXY_NET_*` metrics where tests use a proxy | The first hops on every path change, which is expected |

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
bandwidth or throughput measurement.

## Timing

- Judge a change only after at least 3 rounds of each test in scope.
- Routing changes converge over minutes: expect BGP updates and path changes
  during the window, then judge the settled state.
- DNS changes take effect as TTLs expire: check after the old TTL has passed.
