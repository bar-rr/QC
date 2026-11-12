"""Node identity and contact book, stored as plain JSON on the user's own disk.

There is no account, no server and no registry: a node *is* its key pair.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey,
    X25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)

CARD_PREFIX = "qc1:"


def b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _raw_pub(key) -> bytes:
    return key.public_bytes(Encoding.Raw, PublicFormat.Raw)


def _raw_priv(key) -> bytes:
    return key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())


def node_id(enc_pub: bytes, sig_pub: bytes) -> str:
    """Short, stable fingerprint of a node's public keys."""
    return hashlib.sha256(enc_pub + sig_pub).hexdigest()[:16]


@dataclass(frozen=True)
class Contact:
    """Public half of a node: what you share with others."""

    name: str
    enc_pub: bytes  # X25519, for encryption to this node
    sig_pub: bytes  # Ed25519, for verifying this node's signatures

    @property
    def id(self) -> str:
        return node_id(self.enc_pub, self.sig_pub)

    def to_dict(self) -> dict:
        return {"name": self.name, "enc": b64e(self.enc_pub), "sig": b64e(self.sig_pub)}

    @classmethod
    def from_dict(cls, d: dict) -> "Contact":
        enc, sig = b64d(d["enc"]), b64d(d["sig"])
        if len(enc) != 32 or len(sig) != 32:
            raise ValueError("invalid key length in contact")
        return cls(name=str(d["name"]), enc_pub=enc, sig_pub=sig)

    def to_card(self) -> str:
        """One-line shareable string (QR code, chat, paper, USB...)."""
        payload = json.dumps(self.to_dict(), separators=(",", ":")).encode()
        return CARD_PREFIX + b64e(payload)

    @classmethod
    def from_card(cls, card: str) -> "Contact":
        card = card.strip()
        if not card.startswith(CARD_PREFIX):
            raise ValueError(f"contact card must start with {CARD_PREFIX!r}")
        return cls.from_dict(json.loads(b64d(card[len(CARD_PREFIX):])))

    def encryption_key(self) -> X25519PublicKey:
        return X25519PublicKey.from_public_bytes(self.enc_pub)

    def verify_key(self) -> Ed25519PublicKey:
        return Ed25519PublicKey.from_public_bytes(self.sig_pub)


class Identity:
    """Private keys of this node."""

    def __init__(self, name: str, enc: X25519PrivateKey, sig: Ed25519PrivateKey):
        self.name = name
        self.enc = enc
        self.sig = sig
        self.contact = Contact(name, _raw_pub(enc.public_key()), _raw_pub(sig.public_key()))

    @property
    def id(self) -> str:
        return self.contact.id

    @classmethod
    def generate(cls, name: str) -> "Identity":
        return cls(name, X25519PrivateKey.generate(), Ed25519PrivateKey.generate())

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "enc_priv": b64e(_raw_priv(self.enc)),
            "sig_priv": b64e(_raw_priv(self.sig)),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Identity":
        return cls(
            d["name"],
            X25519PrivateKey.from_private_bytes(b64d(d["enc_priv"])),
            Ed25519PrivateKey.from_private_bytes(b64d(d["sig_priv"])),
        )


class Store:
    """Everything a node keeps lives in one local directory (default ~/.qc)."""

    def __init__(self, home: str | os.PathLike | None = None):
        self.home = Path(home or os.environ.get("QC_HOME") or Path.home() / ".qc")
        self.identity_path = self.home / "identity.json"
        self.contacts_path = self.home / "contacts.json"

    # -- identity ---------------------------------------------------------
    def has_identity(self) -> bool:
        return self.identity_path.exists()

    def create_identity(self, name: str) -> Identity:
        if self.has_identity():
            raise FileExistsError(f"identity already exists at {self.identity_path}")
        self.home.mkdir(parents=True, exist_ok=True)
        ident = Identity.generate(name)
        self._write_private(self.identity_path, ident.to_dict())
        return ident

    def load_identity(self) -> Identity:
        if not self.has_identity():
            raise FileNotFoundError("no identity yet — run `qc init <name>` first")
        return Identity.from_dict(json.loads(self.identity_path.read_text()))

    # -- contacts ---------------------------------------------------------
    def contacts(self) -> dict[str, Contact]:
        if not self.contacts_path.exists():
            return {}
        raw = json.loads(self.contacts_path.read_text())
        return {cid: Contact.from_dict(d) for cid, d in raw.items()}

    def add_contact(self, contact: Contact) -> bool:
        """Add a contact. Returns False if it was already known."""
        book = self.contacts()
        if contact.id in book and book[contact.id] == contact:
            return False
        book[contact.id] = contact
        self.home.mkdir(parents=True, exist_ok=True)
        self.contacts_path.write_text(
            json.dumps({cid: c.to_dict() for cid, c in book.items()}, indent=2)
        )
        return True

    def find_contact(self, ref: str) -> Contact:
        """Find a contact by exact id, id prefix, or name."""
        book = self.contacts()
        if ref in book:
            return book[ref]
        matches = [c for cid, c in book.items() if cid.startswith(ref) or c.name == ref]
        if len(matches) == 1:
            return matches[0]
        if not matches:
            raise KeyError(f"no contact matches {ref!r}")
        ids = ", ".join(f"{c.name}({c.id})" for c in matches)
        raise KeyError(f"{ref!r} is ambiguous: {ids}")

    @staticmethod
    def _write_private(path: Path, data: dict) -> None:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
