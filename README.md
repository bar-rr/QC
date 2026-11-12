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

There are many P2P messengers. Most of them still assume *the internet*: a DHT, bootstrap servers, relays, Tor, or at least an uplink. QC starts from the opposite assumption — **the infrastructure may not exist at all**.

| | Typical P2P messenger | QC |
|---|---|---|
| **Unit of communication** | A live connection | A self-contained *sealed envelope* that can travel over any medium |
| **Transport** | Internet (often + relays / bootstrap nodes) | Pluggable: LAN today, a USB stick or any shared folder today; radio (LoRa), Bluetooth, serial next |
| **Needs internet?** | Usually | Never — a local network or a USB stick is enough |
| **Footprint** | Electron apps, hundreds of MB | ~800 lines of Python, one dependency, runs on old hardware and Raspberry Pi |
| **Account / registry** | Phone number, username server, or DHT | None — a node *is* its key pair; contacts are exchanged as a one-line card |
| **Quantum** | Rarely considered | Roadmap: hybrid post-quantum key exchange (X25519 + ML-KEM) |

The core idea: **the message, not the network, carries the security.** Because envelopes are end-to-end encrypted and signed, *anything* can carry them — a stranger's USB stick, an untrusted sync folder, a radio link — and the carrier learns nothing but the recipient id.

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
- [ ] Store-and-forward: nodes carry envelopes for others (mesh without internet)
- [ ] LoRa / Bluetooth / serial transports
- [ ] Hybrid post-quantum key exchange (X25519 + ML-KEM)
- [ ] Double-ratchet forward secrecy
- [ ] Optional local AI assistant running fully on-device

## Status

🚧 Early stage — working prototype (v0.1).

## Topics

`decentralized` `quantum-communication` `p2p` `zero-server` `edge-computing` `local-first` `network-architecture` `privacy`

## License

[GNU Affero General Public License v3.0](LICENSE) — any modified version, including one offered over a network, must remain open source under the same license.
