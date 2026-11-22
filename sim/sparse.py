"""Sparse-network fixes: do they cut latency without losing the energy win?

    python -m sim.sparse        # 7 days, 3 seeds (~10 min on 4 cores)

Variants (all scheduled ones use 30 s windows every 10 min as a base):
  A   always-on radio (Bitchat-like)
  C   scheduled rendezvous, no fix
  F1  lonely phones (saw nobody last window) open a 90 s window next time
  F2  walking phones also wake every 2 min
  F3  walking phones keep scanning; every phone emits a cheap BLE beacon
  F13 F1 + F3
Uses a 30 s tick so short contacts with walkers are not skipped.
"""

from __future__ import annotations

import json
import os
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from pathlib import Path

import numpy as np

from .qcsim import BASE, DAY, simulate

OUT = Path(__file__).parent / "results"
TICK = 30.0

VARIANTS = {
    "A": dict(mode="always", retention_s=1 * DAY),
    "C": dict(mode="scheduled"),
    "F1": dict(mode="scheduled", lonely_window_s=90.0),
    "F2": dict(mode="scheduled", moving_period_s=120.0),
    "F3": dict(mode="scheduled", mover_listen=True),
    "F13": dict(mode="scheduled", lonely_window_s=90.0, mover_listen=True),
}
LABELS = {
    "A": "Always-on (Bitchat-like)",
    "C": "Scheduled, no fix",
    "F1": "F1: longer window when alone",
    "F2": "F2: walkers wake every 2 min",
    "F3": "F3: walkers listen, all beacon",
    "F13": "F1 + F3",
}
SETTINGS = {
    "normal": dict(),
    "few people (250)": dict(n_nodes=250),
    "short range (30 m)": dict(ble_range_m=30.0),
    "both": dict(n_nodes=250, ble_range_m=30.0),
}
METRICS = ("delivered", "within_1h", "within_6h", "median_latency_min", "alive_day3", "alive_day7")


def _run(job):
    s_key, v_key, seed = job
    cfg = replace(BASE, tick_s=TICK, **SETTINGS[s_key], **VARIANTS[v_key], name=v_key)
    r = simulate(cfg, seed)
    out = r.summary()
    out["radio_wh_per_phone_day"] = r.radio_j / 3600 / cfg.n_nodes / cfg.days
    return s_key, v_key, seed, out


def main() -> None:
    jobs = [(s, v, seed) for s in SETTINGS for v in VARIANTS for seed in range(3)]
    acc: dict = {}
    with ProcessPoolExecutor(max_workers=os.cpu_count()) as ex:
        for s, v, seed, out in ex.map(_run, jobs):
            acc.setdefault(s, {}).setdefault(v, []).append(out)
            print(f"done {s} {v} seed={seed}", flush=True)

    summary = {
        s: {v: {m: float(np.nanmean([r[m] for r in runs])) for m in METRICS + ("radio_wh_per_phone_day",)}
            for v, runs in vs.items()}
        for s, vs in acc.items()
    }
    OUT.mkdir(exist_ok=True)
    (OUT / "sparse.json").write_text(json.dumps(summary, indent=1))
    _markdown(summary)
    _plot(summary)
    print((OUT / "sparse.md").read_text())


def _markdown(summary):
    pct = lambda x: f"{x * 100:.0f}%"
    lines = []
    for s in SETTINGS:
        lines += [f"### {s}", "",
                  "| Variant | Delivered | ≤1 h | ≤6 h | Median latency (min) | Alive day 3 | Alive day 7 | Radio energy (Wh/phone/day) |",
                  "|---|---|---|---|---|---|---|---|"]
        for v in VARIANTS:
            r = summary[s][v]
            lines.append(f"| {LABELS[v]} | {pct(r['delivered'])} | {pct(r['within_1h'])} | {pct(r['within_6h'])} | "
                         f"{r['median_latency_min']:.0f} | {pct(r['alive_day3'])} | {pct(r['alive_day7'])} | "
                         f"{r['radio_wh_per_phone_day']:.2f} |")
        lines.append("")
    (OUT / "sparse.md").write_text("\n".join(lines))


def _plot(summary):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colors = dict(zip(VARIANTS, ["#c0392b", "#2980b9", "#7f8c8d", "#f39c12", "#27ae60", "#16a085"]))
    panels = [("delivered", "Messages delivered (%)", 100),
              ("median_latency_min", "Median latency (hours)", 1 / 60),
              ("alive_day7", "Phones alive on day 7 (%)", 100)]
    fig, axes = plt.subplots(1, 3, figsize=(17, 4.8))
    x = np.arange(len(SETTINGS))
    w = 0.13
    for ax, (m, title, scale) in zip(axes, panels):
        for i, v in enumerate(VARIANTS):
            vals = [summary[s][v][m] * scale for s in SETTINGS]
            ax.bar(x + (i - 2.5) * w, vals, w, color=colors[v], label=LABELS[v])
        ax.set(title=title, xticks=x, xticklabels=list(SETTINGS))
        ax.grid(alpha=0.3, axis="y")
    fig.legend(*axes[0].get_legend_handles_labels(), loc="lower center", ncol=6, fontsize=9)
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    fig.savefig(OUT / "sparse.png", dpi=130)


if __name__ == "__main__":
    main()
