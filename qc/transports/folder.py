"""Folder transport: messages travel as files.

Point it at any directory and it becomes a mailbox: a USB stick or SD card
passed hand to hand ("sneakernet"), a shared network drive, a Syncthing
folder, or files moved over a radio/serial link. No network is required.

Layout:  <root>/<recipient-id>/<timestamp>-<random>.qcm
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Iterator

from ..envelope import recipient_of

SUFFIX = ".qcm"


def drop(root: str | os.PathLike, envelope: bytes) -> Path:
    """Write an envelope into the mailbox of its recipient."""
    box = Path(root) / recipient_of(envelope)
    box.mkdir(parents=True, exist_ok=True)
    name = f"{time.time_ns()}-{os.urandom(4).hex()}{SUFFIX}"
    tmp = box / (name + ".tmp")
    tmp.write_bytes(envelope)
    final = box / name
    tmp.rename(final)  # atomic: readers never see half-written files
    return final


def pending(root: str | os.PathLike, node_id: str) -> Iterator[tuple[Path, bytes]]:
    """Yield (path, envelope) for every message waiting for `node_id`, oldest first."""
    box = Path(root) / node_id
    if not box.is_dir():
        return
    for path in sorted(box.glob(f"*{SUFFIX}")):
        yield path, path.read_bytes()
