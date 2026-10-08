# Network between the two machines

Measured on 8 October 2026 at 11:51:30 UTC, from the load generator (`kais-macbook-pro`) to the service host
(`omarchy`), before the campaign started. The full write-up is in [`../test-environment.md`](../test-environment.md),
section 3. The bullets below are what Slide 7 shows.

- Separate machines: JMeter on kais-macbook-pro (Apple M3 Pro); service and Ollama on omarchy (Ryzen 9 5900X)
- Same home LAN, 192.168.50.0/24: service host wired Gigabit Ethernet, load generator 5 GHz Wi-Fi (802.11ac, 866 Mb/s)
- Round trip 2.2 / 3.5 / 6.8 ms (min / avg / max, 20 pings, 0% loss) — under 0.1% of R1's 10 s threshold
- HTTP connect 3.0–4.0 ms; JMeter targets the IP address, so no DNS lookup inside a sample

Commands (on the MacBook):

```
ping -c 20 -i 0.5 192.168.50.130
#   20 packets transmitted, 20 packets received, 0.0% packet loss
#   round-trip min/avg/max/stddev = 2.218/3.515/6.797/1.638 ms
curl -s -o /dev/null -w "connect=%{time_connect}s total=%{time_total}s\n" http://192.168.50.130:8000/health   # x5
#   connect=0.003913s total=0.015215s
#   connect=0.003302s total=0.014999s
#   connect=0.003143s total=0.014771s
#   connect=0.003029s total=0.019776s
#   connect=0.003965s total=0.015466s
```
