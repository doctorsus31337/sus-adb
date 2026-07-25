import json
import unittest
from dataclasses import FrozenInstanceError

from app.core.script_descriptor import ScriptDescriptor, ScriptKind, TrustState


class ScriptDescriptorTests(unittest.TestCase):
    def test_defaults_validation_serialization_and_immutability(self):
        item = ScriptDescriptor("id", "Agent", ScriptKind.FRIDA, "agent.js")
        self.assertTrue(item.validate().valid)
        self.assertEqual(item.trust, TrustState.UNTRUSTED)
        self.assertEqual(json.loads(json.dumps(item.to_dict()))["kind"], "frida")
        self.assertEqual(ScriptDescriptor.from_dict(item.to_dict()), item)
        with self.assertRaises(FrozenInstanceError): item.name = "Changed"

    def test_invalid_id_and_digest_are_structured(self):
        result = ScriptDescriptor("../bad", "", "frida", "x.js", sha256="bad").validate()
        self.assertFalse(result.valid); self.assertGreaterEqual(len(result.errors), 2)
