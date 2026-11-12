"""Transports move sealed envelopes. They never see plaintext.

Any medium that can carry bytes can be a transport: a LAN socket, a folder on
a USB stick, a synced directory, a serial/radio link. The envelope format is
the same everywhere, so a message can change medium mid-route.
"""
