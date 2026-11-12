"""Sealed envelopes: the only thing that ever leaves a node.

An envelope is self-contained. It carries everything the recipient needs to
decrypt and authenticate it, so it can travel over any medium, be stored,
copied and forwarded by untrusted carriers, and still only be readable by its
recipient.

Construction (v1):
  * Fresh ephemeral X25519 key per message  -> forward secrecy for the sender side
  * X25519(ephemeral, recipient) -> HKDF-SHA256 -> ChaCha20-Poly1305 key
  * Sender signs the whole envelope with Ed25519 -> authenticity

Planned: hybrid post-quantum key exchange (X25519 + ML-KEM) as envelope v2.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass

from cryptography.exceptions import InvalidSignature, InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey,
    X25519PublicKey,
)
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from .identity import Contact, Identity, b64d, b64e

VERSION = 1
MAX_ENVELOPE_BYTES = 1 << 20  # 1 MiB


class EnvelopeError(Exception):
    """Envelope is malformed, not for us, tampered with, or forged."""


@dataclass(frozen=True)
class Message:
    sender: Contact
    text: str
    timestamp: int


def _derive_key(shared: bytes, eph_pub: bytes, recipient_pub: bytes) -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=b"qc-envelope-v1" + eph_pub + recipient_pub,
    ).derive(shared)


def _signed_bytes(env: dict) -> bytes:
    body = {k: v for k, v in env.items() if k != "sigv"}
    return json.dumps(body, sort_keys=True, separators=(",", ":")).encode()


def seal(sender: Identity, recipient: Contact, text: str, *, timestamp: int | None = None) -> bytes:
    """Encrypt and sign `text` for `recipient`. Returns envelope bytes."""
    eph = X25519PrivateKey.generate()
    eph_pub = eph.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    key = _derive_key(eph.exchange(recipient.encryption_key()), eph_pub, recipient.enc_pub)

    ts = int(time.time()) if timestamp is None else timestamp
    nonce = os.urandom(12)
    aad = f"{VERSION}|{sender.id}|{recipient.id}|{ts}".encode()
    plaintext = json.dumps({"text": text}).encode()
    ct = ChaCha20Poly1305(key).encrypt(nonce, plaintext, aad)

    env = {
        "v": VERSION,
        "from": sender.contact.to_dict(),
        "to": recipient.id,
        "ts": ts,
        "eph": b64e(eph_pub),
        "nonce": b64e(nonce),
        "ct": b64e(ct),
    }
    env["sigv"] = b64e(sender.sig.sign(_signed_bytes(env)))
    data = json.dumps(env, separators=(",", ":")).encode()
    if len(data) > MAX_ENVELOPE_BYTES:
        raise EnvelopeError("message too large")
    return data


def recipient_of(data: bytes) -> str:
    """Read the recipient id without decrypting (what a carrier may see)."""
    try:
        return str(json.loads(data)["to"])
    except (ValueError, KeyError, TypeError) as e:
        raise EnvelopeError(f"malformed envelope: {e}") from e


def open_envelope(me: Identity, data: bytes) -> Message:
    """Verify and decrypt an envelope addressed to `me`."""
    if len(data) > MAX_ENVELOPE_BYTES:
        raise EnvelopeError("envelope too large")
    try:
        env = json.loads(data)
        if env.get("v") != VERSION:
            raise EnvelopeError(f"unsupported envelope version {env.get('v')!r}")
        sender = Contact.from_dict(env["from"])
        to, ts = str(env["to"]), int(env["ts"])
        eph_pub, nonce, ct = b64d(env["eph"]), b64d(env["nonce"]), b64d(env["ct"])
        sigv = b64d(env["sigv"])
    except EnvelopeError:
        raise
    except (ValueError, KeyError, TypeError) as e:
        raise EnvelopeError(f"malformed envelope: {e}") from e

    if to != me.id:
        raise EnvelopeError("envelope is not addressed to this node")

    try:
        sender.verify_key().verify(sigv, _signed_bytes(env))
    except InvalidSignature as e:
        raise EnvelopeError("bad signature: envelope forged or tampered with") from e

    try:
        shared = me.enc.exchange(X25519PublicKey.from_public_bytes(eph_pub))
        key = _derive_key(shared, eph_pub, me.contact.enc_pub)
        aad = f"{VERSION}|{sender.id}|{to}|{ts}".encode()
        plaintext = ChaCha20Poly1305(key).decrypt(nonce, ct, aad)
        text = json.loads(plaintext)["text"]
    except (InvalidTag, ValueError, KeyError) as e:
        raise EnvelopeError("decryption failed") from e

    return Message(sender=sender, text=str(text), timestamp=ts)
