# Optimization levers: te-performance-optimization

The biggest win for users is often outside the network. Match the evidence to
a lever and its owner, confirm it with a second signal, then prove the
fix with an experiment (Mode 2) before anyone changes the network.

## Where latency accrues on the path

From `get_full_path_visualization`: the segment where response time jumps and
stays high to the target.

| Latency jumps at | Usually means | Confirm with | Typical actions |
|---|---|---|---|
| Site LAN or edge (first hops) | A congested uplink, an overloaded edge device, or Wi-Fi | The site's other agents; Endpoint gateway metrics; the device side from a Cisco controller | Rebalance or upgrade uplinks, QoS at the edge, fix Wi-Fi |
| Access circuit (first provider hops) | Last-mile congestion or a long access tail | Business-hours pattern; the site's other circuit | Upgrade the circuit, steer traffic across circuits with SD-WAN, escalate to the provider |
| Provider core | Distance or the provider's internal routing | Distance check; agents on other providers to the same target | Another provider or product; ask the provider for better routing |
| Peering or transit | Congested or distant interconnection between networks | Agents on other providers to the same target; time of day | A better-connected ISP, direct peering, a cloud on-ramp or exchange |
| Destination network | The data center, cloud or SaaS edge | Every vantage point slow at the same networks | A closer region or point of presence, a cloud on-ramp |

## Loss and jitter

| Signal | Usually means | Confirm with | Typical actions |
|---|---|---|---|
| Loss and jitter rise in business hours, recover off-peak | Congestion | Peak against off-peak; bandwidth or throughput measurements where tests have them | Capacity, QoS for real-time traffic, traffic steering |
| Loss on one circuit or provider only | That circuit or provider | The site's other circuit; other sites on the same provider | Fail over, escalate with path evidence, change provider |
| Loss or latency in one direction only (agent-to-agent) | One-way congestion or asymmetric routing | The path in each direction | Fix the congested direction or the routing policy |
| Jitter on real-time traffic with low loss | Queuing without priority | Marked against unmarked test; voice `VOIP_PDV` | End-to-end QoS policy; check the provider honors the markings |

## QoS and MTU

| Signal | Usually means | Typical actions |
|---|---|---|
| DSCP changes along the path (path visualization view or a path trace DSCP alert) | A provider or device remarks the class | Fix the policy, or take it to the provider with the evidence |
| Unmarked twin impaired at peak, marked test just as impaired | The class is not prioritized where the congestion is | Find the congested hop and its policy (both clean means QoS is untested, not passed) |
| Path MTU below 1500 bytes on a path with no tunnels | PPPoE broadband (1492 is normal), a tunnel you did not expect, or a misconfigured interface | Find it on the path; correct the MTU or clamp TCP MSS |
| Path MTU dropped after a change | New encapsulation (IPsec, GRE, SD-WAN) | Clamp TCP MSS at the tunnel edge, or raise the underlay MTU |

## Routing and design

| Signal | Usually means | Typical actions |
|---|---|---|
| Round trip far above the distance floor | A detour: tromboning through a distant hub or region | Local breakout, regional hubs, better peering |
| SaaS reached through a distant hub | Centralized internet egress | Local breakout through SD-WAN for trusted SaaS |
| Internet egress differs from the network map | Policy or routing not as designed | Fix the policy; verify with te-change-assurance |
| Frequent path changes | Unstable routing in a provider | Provider escalation with the path history |

## Application, dependencies and third parties

From `get_detailed_test_results` (page requests for page-load and
web-transactions tests, request steps for api tests) and the journey metrics.

| Signal | Usually means | Owner | Typical actions |
|---|---|---|---|
| One transaction step or api request dominates the journey time | That step's backend or API | Application team | Hand over the step, its timing split and the rounds; prove the fix with the same journey test |
| Identity redirects (sign-in domains) take a large share of the time | The identity provider, its region, or conditional access checks | Identity team or provider | A closer tenant region or endpoint; review the sign-in flow's redirects |
| Third-party scripts, tags or fonts on the critical path | Content the page waits for, owned by someone else | Application or web team | Defer or remove them; self-host critical assets |
| CDN domains slow from some regions only | The CDN's point of presence or routing for those users | Web team, CDN provider | Check the edges serving those regions; compare CDNs (Mode 2) |
| Many objects, or large ones, on the page (`WEB_PAGE_COMPONENT_COUNT`) | Page weight | Web team | Fewer and smaller objects, caching |
| Real-user page load (Endpoint) much worse than synthetic from the same location | The user side, or content the synthetic test does not load | Service desk, web team | Compare Endpoint gateway and Wi-Fi metrics; align the test with what users open |

## HTTP split (separating network from application)

| Signal | Usually means | Typical actions |
|---|---|---|
| `WEB_CONNECT` high (about one network round trip) | The network path | The path levers above |
| `WEB_WAIT` high, `WEB_CONNECT` normal | Server time, not the network (`WEB_WAIT` includes about one round trip, so server time is roughly `WEB_WAIT` minus `WEB_CONNECT`) | Hand to the application owner with the evidence |
| `WEB_DNS` high | Resolver distance or performance | A closer or anycast resolver; test resolver A against B (Mode 2) |
| `WEB_SSL` rises with `WEB_CONNECT` | Distance (the handshake costs round trips) | The path levers above |

## Last mile (Endpoint Agents)

| Signal | Usually means | Typical actions |
|---|---|---|
| Low Wi-Fi signal quality or SNR, high retransmission | Coverage or interference | Access point placement, channel planning |
| High gateway latency or loss | The local network or home router | Local fixes, guidance for remote workers |
| High VPN latency with a healthy gateway | VPN concentrator location or load | A closer concentrator, split tunneling for trusted SaaS |

## Projections

- Use weekly medians and at least 8 weeks of history.
- Fit a straight line; report the slope per week and how well it fits (for
  example R squared). A poor fit means "no clear trend".
- Time to threshold = (threshold - latest weekly median) / slope, only when the
  slope moves toward the threshold.
- Never project further ahead than the history you have.
