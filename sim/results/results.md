## Main scenarios

| Scenario | Delivered | ≤1 h | ≤6 h | Median latency (min) | Alive day 1 | Alive day 3 | Alive day 7 |
|---|---|---|---|---|---|---|---|
| A: Always-on, 24 h retention (Bitchat-like) | 54% | 18% | 44% | 113 | 100% | 48% | 0% |
| B: Always-on, 7 d retention | 57% | 18% | 44% | 121 | 100% | 48% | 0% |
| C: Scheduled 30 s / 10 min | 67% | 15% | 46% | 185 | 100% | 100% | 72% |
| D: Scheduled + battery-aware + 5% carriers | 66% | 10% | 41% | 248 | 100% | 100% | 80% |
| E: Always-on + 5% carriers (control) | 54% | 17% | 42% | 123 | 100% | 51% | 6% |

### Delivered, by day the message was sent

| Scenario | Day 1 | Day 2 | Day 3 | Day 4 | Day 5 | Day 6 | Day 7 |
|---|---|---|---|---|---|---|---|
| A | 72% | 60% | 40% | 21% | 6% | — | — |
| B | 76% | 63% | 43% | 22% | 2% | — | — |
| C | 76% | 75% | 74% | 73% | 66% | 58% | 39% |
| D | 75% | 74% | 73% | 71% | 68% | 58% | 39% |
| E | 76% | 63% | 46% | 23% | 6% | 2% | 1% |

## Sensitivity (A = always-on 24 h, D = scheduled + battery-aware + carriers)

| Scenario | Delivered | ≤1 h | ≤6 h | Median latency (min) | Alive day 1 | Alive day 3 | Alive day 7 |
|---|---|---|---|---|---|---|---|
| A@radio50mW | 56% | 18% | 45% | 115 | 100% | 77% | 11% |
| D@radio50mW | 66% | 10% | 41% | 245 | 100% | 100% | 81% |
| A@radio200mW | 52% | 18% | 43% | 108 | 80% | 0% | 0% |
| D@radio200mW | 66% | 9% | 40% | 256 | 100% | 100% | 78% |
| A@n250 | 53% | 12% | 40% | 169 | 100% | 46% | 0% |
| D@n250 | 63% | 5% | 28% | 430 | 100% | 100% | 81% |
| A@n1000 | 58% | 24% | 49% | 83 | 100% | 48% | 0% |
| D@n1000 | 70% | 15% | 50% | 175 | 100% | 100% | 82% |
| A@range30m | 45% | 7% | 28% | 250 | 100% | 48% | 0% |
| D@range30m | 50% | 2% | 13% | 802 | 100% | 100% | 80% |
