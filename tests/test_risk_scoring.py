import unittest
from app.core.risk_scoring import RiskScoring
class T(unittest.TestCase):
 def test_manual_matrix_custom(self):
  self.assertEqual(RiskScoring.manual("high").final_severity.value,"high");r=RiskScoring.matrix("high","critical",final_severity="medium",justification="context");self.assertEqual(r.calculated_severity.value,"critical");self.assertEqual(r.final_severity.value,"medium");self.assertRaises(ValueError,RiskScoring.matrix,"bad","low")
