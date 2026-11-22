# QC — Quantum Communications

> Zero-intermediary, decentralized communication architecture bypassing centralized servers, cloud gateways, and legacy infrastructure through pure peer-to-peer and quantum-inspired direct data transfer.

**🇹🇷** Merkezi sunucuları, bulut geçitlerini ve geleneksel altyapıları baypas eden; sıfır aracılı, fizik yasalarına dayalı bağımsız ve merkezsiz haberleşme mimarisi.

---

## Vision

QC is an architectural response to centralized technology: communication and computation that run on the user's own devices, without subscriptions, gatekeepers, or a server in the middle.

### 1. Against the centralized "wheel"
- **Bloat and hardware dependency** — Software (including AI) is increasingly built to demand more RAM, VRAM and specialized chips, pushing users into constant hardware upgrades (planned obsolescence).
- **Local-first intelligence** — Real autonomy comes from lightweight models that run on the user's own device (local / edge AI), independent of centralized providers.

### 2. Zero-intermediary architecture
- **Infrastructure independence** — Classical stacks (central servers, carrier networks, cloud gateways) tie users to subscription chains and centralized control over data.
- **Node-to-node** — QC aims for direct node-to-node information flow instead of the classical client–server hierarchy.

### 3. Quantum communication philosophy
- **Physics-based security** — Quantum mechanics (the observer effect, entanglement) allows communication layers in which eavesdropping is physically detectable.
- **Technology as discovery** — These capabilities are not invented from nothing; they are discovered from potentials that already exist in physics and logic.

See [`docs/VISION.md`](docs/VISION.md) for the full manifesto (Turkish).

## Principles

| Principle | Meaning |
|---|---|
| Zero-server | No central routing or relay that owns the data |
| Local-first | Runs on the user's own hardware, works offline |
| Lightweight | Minimal resource footprint; no hardware bloat |
| Privacy by design | Confidentiality guaranteed by architecture, not policy |

## What makes QC different

Phone-to-phone mesh messengers already exist — [Bitchat](https://github.com/permissionlesstech/bitchat), [Berty](https://github.com/berty/berty), [Briar](https://briarproject.org) — and [Reticulum](https://github.com/markqvist/Reticulum) is a mature medium-independent network stack. They work without the internet. What they share is an assumption: **radios stay on all the time** so that sender, relays and recipient happen to be awake at the same moment.

In a real collapse — no grid, no cell network, no internet, for days — **energy is the scarcest resource**, and always-on radios drain phones exactly when they are alone and need to last longest.

QC's approach is **energy-first, scheduled-rendezvous mesh**:

- **Everyone wakes up together.** Phones keep a shared schedule (phone clock, GPS time when available, corrected peer-to-peer) and turn the radio on only for short, synchronized windows — e.g. ~30 s every 10 minutes. Outside those windows the radio is off.
- **Messages never go into the void.** A message waits for the next shared window, when nearby phones are known to be awake.
- **Battery-aware, nested schedule.** As battery drops, a phone wakes less often (every 10 → 30 → 60 min), but the hourly windows are shared by everyone, so no phone falls off the network.
- **Volunteer carriers.** Users with a power source (power bank, car battery, solar) can opt in to let their phone stay on as a mailbox that stores and forwards others' encrypted messages.
- **Multi-day delivery.** Store-and-forward with retention measured in days, not hours.

Trade-off: delivery is not instant — each hop may wait up to one window. In a collapsed system, a message that arrives in 30 minutes beats one that never arrives because the battery died.

This is a design goal, not yet implemented or measured. See [`docs/DESIGN.md`](docs/DESIGN.md) (Turkish) for details.

## Prototype (v0.1)

### Install

```bash
pip install -e .        # Python 3.10+, depends only on `cryptography`
```

### Create your identity

```bash
qc init alice           # generates your keys in ~/.qc (no account, no server)
qc card                 # prints your one-line contact card: qc1:...
qc add qc1:...          # add a friend's card
qc contacts
```

### Live chat on a local network (no internet needed)

```bash
qc chat                 # peers on the same LAN / hotspot find each other automatically
```

Inside chat: type to message everyone online, `/to <name> <text>` for one person, `/peers`, `/quit`.
If broadcast is blocked on your network, point nodes at each other directly:
`qc chat --peer 192.168.1.20:47474`.

### Offline messaging over a USB stick or any shared folder

```bash
qc send --to bob --folder /media/usb "meet at 6"     # alice
# ...carry the stick to bob...
qc inbox --folder /media/usb                           # bob
```

The folder can also be a network share or a Syncthing directory: whoever carries it can't read the messages.

### Security model (v0.1)

- Each message: fresh ephemeral X25519 key → HKDF-SHA256 → ChaCha20-Poly1305; signed with the sender's Ed25519 key.
- Tampered, forged or misaddressed envelopes are rejected.
- Contacts are trusted on first use; compare ids (`qc contacts`) out of band for important contacts.
- Not yet: post-quantum key exchange, full forward secrecy for the recipient side (ratcheting), metadata hiding. This is an early prototype, not audited — don't rely on it for life-critical secrecy yet.

### Tests

```bash
python -m unittest discover -s tests -v
```

## Roadmap

- [x] Sealed envelopes (E2E encryption + signatures)
- [x] LAN transport with automatic discovery
- [x] Folder / USB transport (sneakernet)
- [ ] Simulation: scheduled-rendezvous vs always-on (delivery rate, latency, energy)
- [ ] Android app: Bluetooth LE with synchronized wake windows
- [ ] Volunteer carrier mode and multi-day store-and-forward
- [ ] Real-device energy measurements
- [ ] Optional Wi-Fi Aware / Wi-Fi Direct for large data
- [ ] iOS support (background wake is restricted)
- [ ] Hybrid post-quantum key exchange (X25519 + ML-KEM)

## Status

🚧 Early stage — desktop prototype (v0.1) of the encryption and transport layer; the energy-first mesh is in design.

## Topics

`decentralized` `quantum-communication` `p2p` `zero-server` `edge-computing` `local-first` `network-architecture` `privacy`

## License

[GNU Affero General Public License v3.0](LICENSE) — any modified version, including one offered over a network, must remain open source under the same license.
