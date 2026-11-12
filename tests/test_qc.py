import json
import tempfile
import threading
import time
import unittest

from qc.envelope import EnvelopeError, open_envelope, seal
from qc.identity import Contact, Identity, Store, b64d, b64e
from qc.transports import folder
from qc.transports.lan import LanNode


class EnvelopeTest(unittest.TestCase):
    def setUp(self):
        self.alice = Identity.generate("alice")
        self.bob = Identity.generate("bob")
        self.eve = Identity.generate("eve")

    def test_roundtrip(self):
        msg = open_envelope(self.bob, seal(self.alice, self.bob.contact, "merhaba 🛰️"))
        self.assertEqual(msg.text, "merhaba 🛰️")
        self.assertEqual(msg.sender.id, self.alice.id)

    def test_wrong_recipient_rejected(self):
        env = seal(self.alice, self.bob.contact, "secret")
        with self.assertRaises(EnvelopeError):
            open_envelope(self.eve, env)

    def test_tampered_ciphertext_rejected(self):
        env = json.loads(seal(self.alice, self.bob.contact, "secret"))
        ct = bytearray(b64d(env["ct"]))
        ct[0] ^= 1
        env["ct"] = b64e(bytes(ct))
        with self.assertRaises(EnvelopeError):
            open_envelope(self.bob, json.dumps(env).encode())

    def test_forged_sender_rejected(self):
        # Eve seals a message but claims to be Alice.
        env = json.loads(seal(self.eve, self.bob.contact, "I am alice"))
        env["from"] = self.alice.contact.to_dict()
        with self.assertRaises(EnvelopeError):
            open_envelope(self.bob, json.dumps(env).encode())

    def test_plaintext_not_in_envelope(self):
        env = seal(self.alice, self.bob.contact, "very-secret-words")
        self.assertNotIn(b"very-secret-words", env)

    def test_card_roundtrip(self):
        c = Contact.from_card(self.alice.contact.to_card())
        self.assertEqual(c, self.alice.contact)


class StoreTest(unittest.TestCase):
    def test_identity_and_contacts_persist(self):
        with tempfile.TemporaryDirectory() as d:
            s = Store(d)
            me = s.create_identity("alice")
            self.assertEqual(Store(d).load_identity().id, me.id)
            bob = Identity.generate("bob").contact
            self.assertTrue(s.add_contact(bob))
            self.assertFalse(s.add_contact(bob))
            self.assertEqual(s.find_contact("bob"), bob)
            self.assertEqual(s.find_contact(bob.id[:6]), bob)


class FolderTransportTest(unittest.TestCase):
    def test_drop_and_collect(self):
        alice, bob = Identity.generate("alice"), Identity.generate("bob")
        with tempfile.TemporaryDirectory() as d:
            folder.drop(d, seal(alice, bob.contact, "one"))
            folder.drop(d, seal(alice, bob.contact, "two"))
            texts = [open_envelope(bob, data).text for _, data in folder.pending(d, bob.id)]
            self.assertEqual(texts, ["one", "two"])
            self.assertEqual(list(folder.pending(d, alice.id)), [])


class LanTransportTest(unittest.TestCase):
    def test_discover_and_deliver_on_loopback(self):
        alice, bob = Identity.generate("alice"), Identity.generate("bob")
        got, done = [], threading.Event()

        def bob_receives(data, host):
            got.append(open_envelope(bob, data).text)
            done.set()

        # Distinct discovery ports + direct peer addresses: works without broadcast.
        a = LanNode(alice, lambda d, h: None, discovery_port=47561,
                    static_peers=[("127.0.0.1", 47562)], broadcast=False).start()
        b = LanNode(bob, bob_receives, discovery_port=47562, broadcast=False).start()
        try:
            deadline = time.time() + 5
            while bob.id not in a.peers and time.time() < deadline:
                time.sleep(0.05)
            self.assertIn(bob.id, a.peers, "alice did not discover bob")
            # bob learns alice back from her announcement
            self.assertIn(alice.id, b.peers)
            a.send(bob.id, seal(alice, bob.contact, "doğrudan, aracısız"))
            self.assertTrue(done.wait(5))
            self.assertEqual(got, ["doğrudan, aracısız"])
        finally:
            a.stop()
            b.stop()


if __name__ == "__main__":
    unittest.main()
