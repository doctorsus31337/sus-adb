import unittest
from app.core.security_finding import *
class T(unittest.TestCase):
 def test_roundtrip_immutable_labels(self):
  f=SecurityFinding("SQL issue",severity="high",affected_target_identifiers=("pkg",),reproduction_steps=("Open",));g=SecurityFinding.from_dict(f.to_dict());self.assertEqual(f,g);self.assertIn("HIGH",f.display_label);self.assertEqual(len(f.digest),64);self.assertIsInstance(f.evidence_ids,tuple)
