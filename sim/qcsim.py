"""QC crisis-mesh simulator: always-on vs scheduled-rendezvous radios.

A coarse, transparent model — not a radio-accurate simulator. Every
assumption is a field of `Config` so results can be re-run under
different assumptions.

Model
-----
* Phones on a 2D area. Most people stay near gathering points (shelters,
  assembly areas); a fraction walk between them (random waypoint).
* Two awake phones within `ble_range` are linked. Messages cross a whole
  connected cluster in one tick (multi-hop mesh), like a BLE flood.
* Store-and-forward: the sender keeps the message and hands copies to
  phones it meets, up to `copies` copies in total (limited epidemic /
  spray). A copy holder meeting the recipient delivers it.
* Energy: idle drain + screen use for everyone; radio power only while the
  radio is on. A phone whose battery hits zero is dead: it can neither
  receive nor carry messages.
* Always-on mode: radio on all the time (like current phone mesh apps).
* Scheduled mode: everyone wakes together for `window_s` every `period_s`.
  Clocks drift without a network; a phone widens its window by a guard
  time that grows since its last sync (GPS fix or meeting a peer).
  Battery-aware phones skip windows as battery drops, but the hourly
  windows are shared by all.
* Carriers: opt-in phones with a power source; radio always on, no drain.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree

DAY = 86400.0


@dataclass(frozen=True)
class Config:
    # world
    n_nodes: int = 500
    area_m: float = 2000.0
    n_hubs: int = 15
    hub_sigma_m: float = 60.0
    frac_in_hubs: float = 0.7
    frac_mobile: float = 0.25
    walk_speed_mps: float = 1.0
    pause_s: tuple[float, float] = (1800.0, 7200.0)
    ble_range_m: float = 50.0
    days: float = 7.0
    tick_s: float = 60.0
    # energy (assumptions; see sim/README.md)
    battery_j: float = 17.0 * 3600  # ~4500 mAh phone
    init_soc: tuple[float, float] = (0.2, 0.9)
    p_idle_w: float = 0.020  # screen off, airplane mode + Bluetooth on
    p_radio_w: float = 0.100  # extra while mesh radio + CPU are active
    wake_overhead_j: float = 0.5  # CPU wake-up per window
    screen_j_per_day: float = 15 * 60 * 1.2  # 15 min/day at 1.2 W
    # messaging
    msgs_per_day: float = 6.0
    copies: int = 8
    retention_s: float = 7 * DAY
    carry_quota: int = 300
    # radio schedule
    mode: str = "always"  # "always" | "scheduled"
    period_s: float = 600.0
    window_s: float = 30.0
    battery_aware: bool = False
    carrier_frac: float = 0.0
    # clocks (scheduled mode)
    clock_drift_s_per_day: float = 2.0  # 1-sigma
    gps_frac: float = 0.3  # phones that get a GPS time fix at wake-up
    name: str = ""


@dataclass
class Result:
    cfg: Config
    created: np.ndarray
    delivered_at: np.ndarray  # nan = not delivered
    dst_alive_at_send: np.ndarray
    t_axis: np.ndarray
    alive_frac: np.ndarray
    death_time: np.ndarray
    radio_j: float = 0.0
    extra: dict = field(default_factory=dict)

    def summary(self) -> dict:
        lat = self.delivered_at - self.created
        ok = ~np.isnan(self.delivered_at)
        n = len(self.created)
        reachable = self.dst_alive_at_send

        def alive_at(day: float) -> float:
            i = min(int(day * DAY / self.cfg.tick_s), len(self.alive_frac) - 1)
            return float(self.alive_frac[i])

        by_day = []
        for d in range(int(self.cfg.days)):
            sel = (self.created >= d * DAY) & (self.created < (d + 1) * DAY)
            by_day.append(float(ok[sel].mean()) if sel.any() else float("nan"))
        return {
            "messages": n,
            "delivered": float(ok.mean()) if n else 0.0,
            "delivered_reachable": float(ok[reachable].mean()) if reachable.any() else 0.0,
            "within_1h": float((ok & (lat <= 3600)).mean()) if n else 0.0,
            "within_6h": float((ok & (lat <= 6 * 3600)).mean()) if n else 0.0,
            "median_latency_min": float(np.median(lat[ok]) / 60) if ok.any() else float("nan"),
            "p90_latency_min": float(np.percentile(lat[ok], 90) / 60) if ok.any() else float("nan"),
            "alive_day1": alive_at(1),
            "alive_day3": alive_at(3),
            "alive_day7": alive_at(self.cfg.days),
            "delivered_by_send_day": by_day,
        }


def simulate(cfg: Config, seed: int = 0) -> Result:
    rng = np.random.default_rng(seed)
    n = cfg.n_nodes
    A = cfg.area_m

    # --- placement and mobility ------------------------------------------------
    hubs = rng.uniform(0.1 * A, 0.9 * A, size=(cfg.n_hubs, 2))
    pos = rng.uniform(0, A, size=(n, 2))
    in_hub = rng.random(n) < cfg.frac_in_hubs
    hub_of = rng.integers(0, cfg.n_hubs, size=n)
    pos[in_hub] = hubs[hub_of[in_hub]] + rng.normal(0, cfg.hub_sigma_m, size=(in_hub.sum(), 2))
    np.clip(pos, 0, A, out=pos)
    mobile = rng.random(n) < cfg.frac_mobile
    target = pos.copy()
    pause_until = np.zeros(n)

    def new_target(i: int) -> np.ndarray:
        return hubs[rng.integers(cfg.n_hubs)] + rng.normal(0, cfg.hub_sigma_m, 2)

    for i in np.flatnonzero(mobile):
        target[i] = new_target(i)

    # --- energy ----------------------------------------------------------------
    carrier = rng.random(n) < cfg.carrier_frac
    energy = cfg.battery_j * rng.uniform(*cfg.init_soc, size=n)
    alive = np.ones(n, dtype=bool)
    death_time = np.full(n, np.nan)
    radio_j = 0.0

    # --- clocks (scheduled mode) ----------------------------------------------
    drift_sigma = cfg.clock_drift_s_per_day / DAY
    has_gps = rng.random(n) < cfg.gps_frac
    last_sync = np.zeros(n)  # crisis starts with network-synced clocks

    # --- messages -------------------------------------------------------------
    src_l, dst_l, created_l, dst_alive_l = [], [], [], []
    delivered_at: list[float] = []
    holders: dict[int, set[int]] = {}
    carry = np.zeros(n, dtype=np.int64)

    def drop_holder(m: int, h: int) -> None:
        holders[m].discard(h)
        carry[h] -= 1

    def finish(m: int, t: float | None) -> None:
        if t is not None:
            delivered_at[m] = t
        for h in holders.pop(m):
            carry[h] -= 1

    steps = int(cfg.days * DAY / cfg.tick_s)
    t_axis = np.arange(steps + 1) * cfg.tick_s
    alive_frac = np.empty(steps + 1)
    alive_frac[0] = 1.0
    ticks_per_window = int(round(cfg.period_s / cfg.tick_s))
    send_p = cfg.msgs_per_day * cfg.tick_s / DAY

    for step in range(1, steps + 1):
        t = step * cfg.tick_s
        dt = cfg.tick_s

        # mobility
        mv = mobile & alive & (pause_until <= t)
        if mv.any():
            idx = np.flatnonzero(mv)
            d = target[idx] - pos[idx]
            dist = np.hypot(d[:, 0], d[:, 1])
            stepd = cfg.walk_speed_mps * dt
            arrive = dist <= stepd
            frac = np.where(arrive, 1.0, stepd / np.maximum(dist, 1e-9))
            pos[idx] += d * frac[:, None]
            for i in idx[arrive]:
                pause_until[i] = t + rng.uniform(*cfg.pause_s)
                target[i] = new_target(i)

        # baseline drain
        base = (cfg.p_idle_w * dt + cfg.screen_j_per_day * dt / DAY)
        drain = np.where(alive & ~carrier, base, 0.0)

        # who has the radio on this tick
        if cfg.mode == "always":
            awake = alive.copy()
            r = np.where(alive & ~carrier, cfg.p_radio_w * dt, 0.0)
            drain += r
            radio_j += r.sum()
        else:
            awake = alive & carrier
            if step % ticks_per_window == 0:
                widx = step // ticks_per_window
                soc = energy / cfg.battery_j
                if cfg.battery_aware:
                    mult = np.where(soc > 0.5, 1, np.where(soc > 0.2, 3, 6))
                else:
                    mult = np.ones(n, dtype=int)
                wake = alive & ~carrier & (widx % mult == 0)
                last_sync[wake & has_gps] = t
                guard = 1.0 + 3 * drift_sigma * (t - last_sync)
                e = np.where(wake, cfg.p_radio_w * (cfg.window_s + 2 * guard) + cfg.wake_overhead_j, 0.0)
                drain += e
                radio_j += e.sum()
                awake |= wake

        energy -= drain
        died = alive & (energy <= 0) & ~carrier
        if died.any():
            alive &= ~died
            awake &= ~died
            death_time[died] = t
            for i in np.flatnonzero(died):
                for m in [m for m, hs in holders.items() if i in hs]:
                    drop_holder(m, i)

        # new messages (composed now; they wait in the sender's outbox)
        senders = np.flatnonzero(alive & (rng.random(n) < send_p))
        for s in senders:
            d = int(rng.integers(n - 1))
            d += d >= s
            m = len(src_l)
            src_l.append(int(s)); dst_l.append(d); created_l.append(t)
            dst_alive_l.append(bool(alive[d])); delivered_at.append(math.nan)
            holders[m] = {int(s)}
            carry[s] += 1

        # connectivity among awake phones
        aw = np.flatnonzero(awake)
        comp_of = np.full(n, -1)
        members: dict[int, list[int]] = {}
        if len(aw) >= 2:
            pairs = cKDTree(pos[aw]).query_pairs(cfg.ble_range_m, output_type="ndarray")
            if len(pairs):
                k = len(aw)
                g = coo_matrix((np.ones(len(pairs)), (pairs[:, 0], pairs[:, 1])), shape=(k, k))
                _, lab = connected_components(g, directed=False)
                sizes = np.bincount(lab)
                linked = sizes[lab] >= 2
                comp_of[aw[linked]] = lab[linked]
                for node, c in zip(aw[linked], lab[linked]):
                    members.setdefault(int(c), []).append(int(node))
                # clocks re-sync when phones meet
                if cfg.mode == "scheduled":
                    for mem in members.values():
                        last_sync[mem] = last_sync[mem].max()

        # routing
        for m in list(holders):
            hs = holders[m]
            if not hs:
                finish(m, None)
                continue
            if t - created_l[m] > cfg.retention_s:
                finish(m, None)
                continue
            if not members:
                continue
            hcomps = {comp_of[h] for h in hs if comp_of[h] >= 0}
            if not hcomps:
                continue
            dc = comp_of[dst_l[m]]
            if dc >= 0 and dc in hcomps:
                finish(m, t)
                continue
            budget = cfg.copies - len(hs)
            for c in hcomps:
                if budget <= 0:
                    break
                cand = [x for x in members[c] if x not in hs and carry[x] < cfg.carry_quota]
                if not cand:
                    continue
                pick = rng.choice(cand, size=min(budget, len(cand)), replace=False)
                for x in pick:
                    hs.add(int(x))
                    carry[x] += 1
                budget -= len(pick)

        alive_frac[step] = alive.mean()

    return Result(
        cfg=cfg,
        created=np.array(created_l),
        delivered_at=np.array(delivered_at),
        dst_alive_at_send=np.array(dst_alive_l, dtype=bool),
        t_axis=t_axis,
        alive_frac=alive_frac,
        death_time=death_time,
        radio_j=radio_j,
    )


# --- scenarios -------------------------------------------------------------------
BASE = Config()

SCENARIOS = {
    "A": replace(BASE, name="A: Always-on, 24 h retention (Bitchat-like)", mode="always", retention_s=1 * DAY),
    "B": replace(BASE, name="B: Always-on, 7 d retention", mode="always"),
    "C": replace(BASE, name="C: Scheduled 30 s / 10 min", mode="scheduled"),
    "D": replace(BASE, name="D: Scheduled + battery-aware + 5% carriers", mode="scheduled",
                 battery_aware=True, carrier_frac=0.05),
    "E": replace(BASE, name="E: Always-on + 5% carriers (control)", mode="always", carrier_frac=0.05),
}
