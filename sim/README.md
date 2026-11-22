# QC Crisis-Mesh Simulation

Compares **always-on** phone mesh (how current apps such as Bitchat work) with QC's **scheduled-rendezvous** design (see [`docs/DESIGN.md`](../docs/DESIGN.md)) in a 7-day collapse: no grid, no cell network, no internet.

```bash
pip install numpy scipy matplotlib
python -m sim.run            # full run: 7 days, 3 seeds, all scenarios + sensitivity (~5 min on 4 cores)
python -m sim.run --quick    # 2-day smoke run
```

Outputs go to [`sim/results/`](results/): `results.md`, `summary.json`, `comparison.png`.

![comparison](results/comparison.png)

## Scenarios

| | Radio | Retention | Extras |
|---|---|---|---|
| **A** | Always on | 24 h | — (Bitchat-like) |
| **B** | Always on | 7 days | — |
| **C** | 30 s every 10 min, all phones together | 7 days | — |
| **D** | Like C, but battery-aware (10 → 30 → 60 min as battery drops) | 7 days | 5% carrier phones with a power source |
| **E** | Always on | 7 days | 5% carriers (control for D) |

## Results (mean of 3 seeds)

| Scenario | Delivered | ≤1 h | ≤6 h | Median latency | Alive day 3 | Alive day 7 |
|---|---|---|---|---|---|---|
| A: Always-on, 24 h | 54% | 18% | 44% | 113 min | 48% | 0% |
| B: Always-on, 7 d | 57% | 18% | 44% | 121 min | 48% | 0% |
| **C: Scheduled 10 min** | **67%** | 15% | 46% | 185 min | **100%** | **72%** |
| **D: Scheduled + battery-aware + carriers** | **66%** | 10% | 41% | 248 min | **100%** | **80%** |
| E: Always-on + carriers | 54% | 17% | 42% | 123 min | 51% | 6% |

Messages delivered, by the day they were sent:

| | Day 1 | Day 2 | Day 3 | Day 4 | Day 5 | Day 6 | Day 7 |
|---|---|---|---|---|---|---|---|
| A | 72% | 60% | 40% | 21% | 6% | — | — |
| C | 76% | 75% | 74% | 73% | 66% | 58%* | 39%* |
| D | 75% | 74% | 73% | 71% | 68% | 58%* | 39%* |

\* Partly a simulation-end effect: messages sent late have less time left to be delivered before day 7 ends.

### What this shows

1. **Always-on phones die by day 5.** Half are dead by day 3; messages sent on day 4 or later almost never arrive. Longer retention (B) or carriers (E) do not fix this — the phones that would carry the messages are dead.
2. **Scheduled rendezvous keeps the network alive for the whole week** and keeps delivery at ~73% through day 4, giving **more delivered messages overall (67% vs 54%)**.
3. **The price is latency.** On day 1, always-on is faster (18% vs 15% within 1 hour; median ~2 h vs ~3 h). Scheduled mode trades speed for survival.
4. **Battery-aware schedule and carriers add little in this model.** D keeps more phones alive on day 7 (80% vs 72%) but is slower than C. The main gain comes from the synchronized windows themselves. The battery thresholds need tuning.

### Sensitivity

| Variation | A delivered | D delivered | A alive day 3 | D alive day 3 | D median latency |
|---|---|---|---|---|---|
| Radio power 50 mW (default 100) | 56% | 66% | 77% | 100% | 245 min |
| Radio power 200 mW | 52% | 66% | 0% | 100% | 256 min |
| 250 people (default 500) | 53% | 63% | 46% | 100% | 430 min |
| 1000 people | 58% | 70% | 48% | 100% | 175 min |
| BLE range 30 m (default 50) | 45% | 50% | 48% | 100% | 802 min |

The scheduled design delivers more in every variation. Its weak spot is **sparse networks** (fewer people, shorter range): latency grows to many hours, because short windows give walkers fewer chances to meet. Possible fixes to explore: longer windows when no neighbours are seen, or more frequent windows for phones that are moving.

## Model and assumptions

All values are fields of `Config` in [`qcsim.py`](qcsim.py).

- **World:** 500 phones on 2 × 2 km. 70% near 15 gathering points (σ 60 m), 30% scattered. 25% walk between gathering points at 1 m/s, pausing 30–120 min.
- **Radio:** Bluetooth range 50 m, unit-disk model. Awake phones in range form a cluster; a message crosses a whole cluster in one tick (multi-hop mesh).
- **Store-and-forward:** Up to 8 copies per message (sender + carriers), 300 carried messages per phone. A copy holder meeting the recipient delivers it; acknowledgements clear all copies instantly (idealized).
- **Energy (assumed, not measured):** 17 Wh battery, initial charge 20–90%. Idle 20 mW (airplane mode + Bluetooth on), mesh radio + CPU 100 mW extra while on, 0.5 J per wake-up, 15 min/day of screen use at 1.2 W.
- **Clocks:** Drift 2 s/day (1σ). 30% of phones get a GPS time fix at wake-up; phones re-sync when they meet. Each phone widens its window by a guard time of 1 s + 3σ × time since last sync, and pays the energy for it.
- **Traffic:** Each living phone sends 6 messages/day to a random other person (the hardest case: recipient anywhere in the area).

### Limitations

- No radio collisions, bandwidth limits or packet loss; contacts are binary.
- Energy figures are estimates. **They must be measured on real phones** before making public claims.
- Mobility is a simple random-waypoint model.
- Clock guard assumes drift stays within 3σ.
- iOS background restrictions and Android vendor battery killers are not modelled.
