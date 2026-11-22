"""Run all scenarios and sensitivity sweeps; write results/ (JSON, PNG, Markdown).

    python -m sim.run            # full run (several minutes, uses all cores)
    python -m sim.run --quick    # 2-day, 1-seed smoke run
"""

from __future__ import annotations

import argparse
import json
import os
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np

from .qcsim import DAY, SCENARIOS, simulate

OUT = Path(__file__).parent / "results"


def _run(job):
    key, cfg, seed = job
    r = simulate(cfg, seed)
    s = r.summary()
    s["alive_curve"] = r.alive_frac[:: int(3600 / cfg.tick_s)].tolist()  # hourly
    lat = (r.delivered_at - r.created) / 3600
    s["latency_h"] = np.sort(lat[~np.isnan(lat)]).tolist()
    s["messages_total"] = len(r.created)
    return key, seed, s


def _mean(runs, k):
    vals = [r[k] for r in runs]
    return float(np.nanmean(vals))


def _nanmean_cols(rows):
    a = np.array(rows, dtype=float)
    return [float(np.nanmean(c)) if not np.isnan(c).all() else float("nan") for c in a.T]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--seeds", type=int, default=3)
    args = ap.parse_args()
    days = 2.0 if args.quick else 7.0
    seeds = 1 if args.quick else args.seeds

    experiments: dict[str, object] = {}
    for k, cfg in SCENARIOS.items():
        experiments[k] = replace(cfg, days=days)
    # sensitivity: radio power, crowd density, radio range
    for p in (0.05, 0.20):
        for k in ("A", "D"):
            experiments[f"{k}@radio{int(p*1000)}mW"] = replace(SCENARIOS[k], days=days, p_radio_w=p)
    for nn in (250, 1000):
        for k in ("A", "D"):
            experiments[f"{k}@n{nn}"] = replace(SCENARIOS[k], days=days, n_nodes=nn)
    for rng_m in (30.0,):
        for k in ("A", "D"):
            experiments[f"{k}@range{int(rng_m)}m"] = replace(SCENARIOS[k], days=days, ble_range_m=rng_m)

    jobs = [(k, cfg, s) for k, cfg in experiments.items() for s in range(seeds)]
    results: dict[str, list] = {k: [] for k in experiments}
    with ProcessPoolExecutor(max_workers=os.cpu_count()) as ex:
        for key, seed, s in ex.map(_run, jobs):
            results[key].append(s)
            print(f"done {key} seed={seed}", flush=True)

    OUT.mkdir(exist_ok=True)
    summary = {}
    for k, runs in results.items():
        cfg = experiments[k]
        summary[k] = {
            "name": cfg.name or k,
            "config": {kk: v for kk, v in asdict(cfg).items() if kk != "name"},
            "seeds": len(runs),
            **{m: _mean(runs, m) for m in (
                "delivered", "delivered_reachable", "within_1h", "within_6h",
                "median_latency_min", "p90_latency_min", "alive_day1", "alive_day3", "alive_day7",
            )},
            "delivered_by_send_day": _nanmean_cols([r["delivered_by_send_day"] for r in runs]),
            "alive_curve": np.mean([r["alive_curve"] for r in runs], axis=0).tolist(),
        }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1))
    _plots(summary, results, days)
    _markdown(summary)
    print((OUT / "results.md").read_text())


def _plots(summary, results, days):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    main_keys = list(SCENARIOS)
    colors = dict(zip(main_keys, ["#c0392b", "#e67e22", "#2980b9", "#27ae60", "#8e44ad"]))
    fig, axes = plt.subplots(1, 3, figsize=(17, 4.8))

    ax = axes[0]
    for k in main_keys:
        c = summary[k]["alive_curve"]
        ax.plot(np.arange(len(c)) / 24, np.array(c) * 100, label=summary[k]["name"], color=colors[k])
    ax.set(title="Phones still alive (battery > 0)", xlabel="Day", ylabel="%", ylim=(0, 102))
    ax.grid(alpha=0.3)

    ax = axes[1]
    width = 0.16
    nd = int(days)
    for i, k in enumerate(main_keys):
        v = np.array(summary[k]["delivered_by_send_day"]) * 100
        ax.bar(np.arange(nd) + (i - 2) * width, v, width, label=k, color=colors[k])
    ax.set(title="Messages delivered, by day they were sent", xlabel="Send day",
           ylabel="% delivered", xticks=range(nd), xticklabels=[str(d + 1) for d in range(nd)])
    ax.grid(alpha=0.3, axis="y")

    ax = axes[2]
    for k in main_keys:
        lat = np.sort(np.concatenate([r["latency_h"] for r in results[k]]))
        total = sum(r["messages_total"] for r in results[k])
        if len(lat):
            ax.step(lat, np.arange(1, len(lat) + 1) / total * 100, where="post", color=colors[k], label=k)
    ax.set(title="Share of all messages delivered within…", xlabel="Hours after sending",
           ylabel="% of messages", xscale="log", xlim=(0.05, days * 24))
    ax.grid(alpha=0.3)

    fig.legend(*axes[0].get_legend_handles_labels(), loc="lower center", ncol=3, fontsize=9)
    fig.tight_layout(rect=(0, 0.1, 1, 1))
    fig.savefig(OUT / "comparison.png", dpi=130)


def _markdown(summary):
    def pct(x):
        return "—" if x != x else f"{x * 100:.0f}%"  # nan -> no messages sent (all phones dead)

    def row(k):
        s = summary[k]
        return (f"| {s['name']} | {pct(s['delivered'])} | {pct(s['within_1h'])} | {pct(s['within_6h'])} | "
                f"{s['median_latency_min']:.0f} | {pct(s['alive_day1'])} | {pct(s['alive_day3'])} | "
                f"{pct(s['alive_day7'])} |")

    head = ("| Scenario | Delivered | ≤1 h | ≤6 h | Median latency (min) | Alive day 1 | Alive day 3 | Alive day 7 |\n"
            "|---|---|---|---|---|---|---|---|")
    lines = ["## Main scenarios", "", head] + [row(k) for k in SCENARIOS]
    lines += ["", "### Delivered, by day the message was sent", "",
              "| Scenario | " + " | ".join(f"Day {d + 1}" for d in range(len(summary["A"]["delivered_by_send_day"]))) + " |",
              "|---|" + "---|" * len(summary["A"]["delivered_by_send_day"])]
    for k in SCENARIOS:
        lines.append(f"| {k} | " + " | ".join(pct(v) for v in summary[k]["delivered_by_send_day"]) + " |")
    lines += ["", "## Sensitivity (A = always-on 24 h, D = scheduled + battery-aware + carriers)", "", head]
    lines += [row(k).replace(summary[k]["name"], k) for k in summary if "@" in k]
    (OUT / "results.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
