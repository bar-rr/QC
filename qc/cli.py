"""Command-line interface: `qc <command>`."""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime

from .envelope import EnvelopeError, open_envelope, seal
from .identity import Contact, Store
from .transports import folder


def _fmt_time(ts: int) -> str:
    return datetime.fromtimestamp(ts).strftime("%H:%M:%S")


def _remember(store: Store, contact: Contact) -> None:
    """Trust on first use: learn new contacts, warn when a known name changes keys."""
    same_name = [c for c in store.contacts().values() if c.name == contact.name and c.id != contact.id]
    if store.add_contact(contact):
        print(f"[+] new contact: {contact.name} ({contact.id})")
        if same_name:
            print(f"[!] WARNING: another contact is also named {contact.name!r} "
                  f"({', '.join(c.id for c in same_name)}) — verify ids out of band")


# -- commands ----------------------------------------------------------------
def cmd_init(store: Store, args) -> int:
    ident = store.create_identity(args.name)
    print(f"Identity created: {ident.name} ({ident.id})")
    print(f"Stored in {store.home}")
    print("Share your card with `qc card`.")
    return 0


def cmd_card(store: Store, args) -> int:
    me = store.load_identity()
    print(me.contact.to_card())
    return 0


def cmd_add(store: Store, args) -> int:
    contact = Contact.from_card(args.card)
    if contact.id == store.load_identity().id:
        print("That is your own card.")
        return 1
    if not store.add_contact(contact):
        print(f"Already known: {contact.name} ({contact.id})")
    else:
        print(f"Added {contact.name} ({contact.id})")
    return 0


def cmd_contacts(store: Store, args) -> int:
    me = store.load_identity()
    print(f"me: {me.name} ({me.id})")
    for c in store.contacts().values():
        print(f"    {c.name} ({c.id})")
    return 0


def cmd_send(store: Store, args) -> int:
    me = store.load_identity()
    to = store.find_contact(args.to)
    path = folder.drop(args.folder, seal(me, to, " ".join(args.text)))
    print(f"Sealed for {to.name} ({to.id}) -> {path}")
    return 0


def cmd_inbox(store: Store, args) -> int:
    me = store.load_identity()
    count = 0
    for path, data in folder.pending(args.folder, me.id):
        try:
            msg = open_envelope(me, data)
        except EnvelopeError as e:
            print(f"[!] {path.name}: {e}")
            continue
        _remember(store, msg.sender)
        print(f"[{_fmt_time(msg.timestamp)}] {msg.sender.name}: {msg.text}")
        count += 1
        if not args.keep:
            path.unlink()
    if count == 0:
        print("No new messages.")
    return 0


def _parse_hostport(text: str) -> tuple[str, int]:
    host, _, port = text.rpartition(":")
    if not host or not port.isdigit():
        raise argparse.ArgumentTypeError(f"expected host:port, got {text!r}")
    return host, int(port)


def cmd_chat(store: Store, args) -> int:
    from .transports.lan import LanNode  # imported lazily: opens sockets

    me = store.load_identity()

    def on_envelope(data: bytes, host: str) -> None:
        try:
            msg = open_envelope(me, data)
        except EnvelopeError as e:
            print(f"\r[!] rejected message from {host}: {e}")
            return
        _remember(store, msg.sender)
        print(f"\r[{_fmt_time(msg.timestamp)}] {msg.sender.name}: {msg.text}\n> ", end="", flush=True)

    def on_peer(peer) -> None:
        print(f"\r[~] {peer.contact.name} ({peer.contact.id}) is online at {peer.host}\n> ",
              end="", flush=True)
        _remember(store, peer.contact)

    node = LanNode(
        me, on_envelope, on_peer,
        discovery_port=args.discovery_port,
        tcp_port=args.port,
        static_peers=args.peer,
        broadcast=not args.no_broadcast,
    ).start()
    print(f"QC chat — {me.name} ({me.id}) listening on tcp/{node.tcp_port}, "
          f"discovery udp/{args.discovery_port}")
    print("Type a message to send to everyone online. Commands: /peers  /to <name> <text>  /quit")

    def deliver(peer_id: str, text: str) -> None:
        peer = next((p for p in node.online() if p.contact.id == peer_id), None)
        if peer is None:
            print(f"[!] {peer_id} is not online")
            return
        try:
            node.send(peer_id, seal(me, peer.contact, text))
        except (OSError, ConnectionError, KeyError) as e:
            print(f"[!] could not deliver to {peer.contact.name}: {e}")

    try:
        while True:
            try:
                line = input("> ").strip()
            except EOFError:
                break
            if not line:
                continue
            if line == "/quit":
                break
            if line == "/peers":
                peers = node.online()
                if not peers:
                    print("No peers online.")
                for p in peers:
                    print(f"  {p.contact.name} ({p.contact.id}) at {p.host}:{p.port}")
                continue
            if line.startswith("/to "):
                _, ref, *words = line.split(" ", 2)
                try:
                    deliver(store.find_contact(ref).id, " ".join(words))
                except KeyError as e:
                    print(f"[!] {e.args[0]}")
                continue
            peers = node.online()
            if not peers:
                print("[!] nobody online yet")
            for p in peers:
                deliver(p.contact.id, line)
    except KeyboardInterrupt:
        print()
    finally:
        node.stop()
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="qc", description="Zero-intermediary, local-first messaging.")
    p.add_argument("--home", help="data directory (default: $QC_HOME or ~/.qc)")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("init", help="create this node's identity")
    s.add_argument("name")
    s.set_defaults(func=cmd_init)

    sub.add_parser("card", help="print your shareable contact card").set_defaults(func=cmd_card)

    s = sub.add_parser("add", help="add a contact from their card")
    s.add_argument("card")
    s.set_defaults(func=cmd_add)

    sub.add_parser("contacts", help="list known contacts").set_defaults(func=cmd_contacts)

    s = sub.add_parser("send", help="seal a message into a folder (USB, shared drive, sync dir)")
    s.add_argument("--to", required=True, help="contact name or id")
    s.add_argument("--folder", required=True)
    s.add_argument("text", nargs="+")
    s.set_defaults(func=cmd_send)

    s = sub.add_parser("inbox", help="read your messages from a folder")
    s.add_argument("--folder", required=True)
    s.add_argument("--keep", action="store_true", help="do not delete messages after reading")
    s.set_defaults(func=cmd_inbox)

    s = sub.add_parser("chat", help="live chat with peers on the local network")
    s.add_argument("--port", type=int, default=0, help="tcp port (default: random)")
    s.add_argument("--discovery-port", type=int, default=47474)
    s.add_argument("--peer", type=_parse_hostport, action="append", default=[],
                   help="host:discovery_port of a peer to announce to directly (repeatable)")
    s.add_argument("--no-broadcast", action="store_true", help="only use --peer addresses")
    s.set_defaults(func=cmd_chat)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    store = Store(args.home)
    try:
        return args.func(store, args)
    except (FileNotFoundError, FileExistsError, KeyError, ValueError) as e:
        msg = e.args[0] if e.args else str(e)
        print(f"error: {msg}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
