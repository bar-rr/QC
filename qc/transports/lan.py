"""LAN transport: direct node-to-node over the local network.

* Discovery: nodes announce a signed contact card over UDP broadcast, and to
  any manually given peer addresses (for networks where broadcast is blocked).
* Delivery: sealed envelopes go straight to the peer over TCP. No relay, no
  server, no internet uplink needed — a router, hotspot or ad-hoc network is enough.
"""

from __future__ import annotations

import json
import socket
import struct
import threading
import time
from dataclasses import dataclass
from typing import Callable

from cryptography.exceptions import InvalidSignature

from ..envelope import MAX_ENVELOPE_BYTES
from ..identity import Contact, Identity, b64d, b64e

DISCOVERY_PORT = 47474
ANNOUNCE_INTERVAL = 3.0
ANNOUNCE_MAX_AGE = 60
_LEN = struct.Struct("!I")


@dataclass
class Peer:
    contact: Contact
    host: str
    port: int
    last_seen: float


def _announce_bytes(me: Identity, tcp_port: int) -> bytes:
    body = {"qc": 1, "card": me.contact.to_dict(), "port": tcp_port, "ts": int(time.time())}
    blob = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    return json.dumps({"body": body, "sig": b64e(me.sig.sign(blob))}).encode()


def _parse_announce(data: bytes) -> tuple[Contact, int] | None:
    try:
        msg = json.loads(data)
        body = msg["body"]
        if body.get("qc") != 1 or abs(time.time() - int(body["ts"])) > ANNOUNCE_MAX_AGE:
            return None
        contact = Contact.from_dict(body["card"])
        blob = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        contact.verify_key().verify(b64d(msg["sig"]), blob)
        port = int(body["port"])
        if not 0 < port < 65536:
            return None
        return contact, port
    except (ValueError, KeyError, TypeError, InvalidSignature):
        return None


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("connection closed early")
        buf += chunk
    return bytes(buf)


class LanNode:
    def __init__(
        self,
        me: Identity,
        on_envelope: Callable[[bytes, str], None],
        on_peer: Callable[[Peer], None] | None = None,
        *,
        discovery_port: int = DISCOVERY_PORT,
        tcp_port: int = 0,
        static_peers: list[tuple[str, int]] | None = None,
        broadcast: bool = True,
    ):
        self.me = me
        self.on_envelope = on_envelope
        self.on_peer = on_peer
        self.discovery_port = discovery_port
        self.static_peers = list(static_peers or [])
        self.broadcast = broadcast
        self.peers: dict[str, Peer] = {}
        self._lock = threading.Lock()
        self._stop = threading.Event()

        self._tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._tcp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._tcp.bind(("", tcp_port))
        self._tcp.listen()
        self._tcp.settimeout(0.5)
        self.tcp_port = self._tcp.getsockname()[1]

        self._udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._udp.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self._udp.bind(("", discovery_port))
        self._udp.settimeout(0.5)

    # -- lifecycle ----------------------------------------------------------
    def start(self) -> "LanNode":
        for target in (self._serve_tcp, self._listen_udp, self._announce_loop):
            threading.Thread(target=target, daemon=True).start()
        return self

    def stop(self) -> None:
        self._stop.set()
        self._tcp.close()
        self._udp.close()

    # -- discovery ----------------------------------------------------------
    def _send_announce(self, addr: tuple[str, int]) -> None:
        try:
            self._udp.sendto(_announce_bytes(self.me, self.tcp_port), addr)
        except OSError:
            pass  # network down / broadcast not permitted: keep trying silently

    def _announce_loop(self) -> None:
        while not self._stop.is_set():
            if self.broadcast:
                self._send_announce(("<broadcast>", self.discovery_port))
            for addr in self.static_peers:
                self._send_announce(addr)
            self._stop.wait(ANNOUNCE_INTERVAL)

    def _listen_udp(self) -> None:
        while not self._stop.is_set():
            try:
                data, (host, udp_port) = self._udp.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                return
            parsed = _parse_announce(data)
            if not parsed:
                continue
            contact, tcp_port = parsed
            if contact.id == self.me.id:
                continue
            with self._lock:
                is_new = contact.id not in self.peers
                peer = Peer(contact, host, tcp_port, time.time())
                self.peers[contact.id] = peer
            if is_new:
                self._send_announce((host, udp_port))  # let them learn us right away
                if self.on_peer:
                    self.on_peer(peer)

    # -- delivery -----------------------------------------------------------
    def _serve_tcp(self) -> None:
        while not self._stop.is_set():
            try:
                conn, (host, _) = self._tcp.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            threading.Thread(target=self._handle_conn, args=(conn, host), daemon=True).start()

    def _handle_conn(self, conn: socket.socket, host: str) -> None:
        with conn:
            conn.settimeout(10)
            try:
                (n,) = _LEN.unpack(_recv_exact(conn, _LEN.size))
                if n > MAX_ENVELOPE_BYTES:
                    return
                self.on_envelope(_recv_exact(conn, n), host)
                conn.sendall(b"\x01")  # ack
            except (OSError, ConnectionError, struct.error):
                return

    def send(self, peer_id: str, envelope: bytes, timeout: float = 5.0) -> None:
        with self._lock:
            peer = self.peers.get(peer_id)
        if peer is None:
            raise KeyError(f"peer {peer_id} is not on this network right now")
        with socket.create_connection((peer.host, peer.port), timeout=timeout) as s:
            s.sendall(_LEN.pack(len(envelope)) + envelope)
            if _recv_exact(s, 1) != b"\x01":
                raise ConnectionError("peer did not acknowledge")

    def online(self, max_age: float = ANNOUNCE_INTERVAL * 4) -> list[Peer]:
        now = time.time()
        with self._lock:
            return [p for p in self.peers.values() if now - p.last_seen <= max_age]
