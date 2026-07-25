import unittest
from app.core.finding_validator import FindingValidator
from app.core.security_finding import SecurityFinding
class T(unittest.TestCase):
 def test_errors_warnings_and_transitions(self):
  v=FindingValidator().validate(SecurityFinding(""));self.assertTrue(v.errors);self.assertTrue(v.warnings);self.assertFalse(FindingValidator().transition("draft","closed").valid);self.assertTrue(FindingValidator().transition("draft","open").valid)
