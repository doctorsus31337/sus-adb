import unittest
from datetime import date,timedelta
from app.core.assessment_scope import AssessmentScope,HIGH_IMPACT_CATEGORIES
class AssessmentScopeTests(unittest.TestCase):
 def scope(self,**kw):
  data=dict(scope_id="s",case_name="Case",authorization_confirmed=True,device_serial="D",package_identifier="com.app",allowed_actions=("recon","destructive-testing"),start_date=date.today().isoformat());data.update(kw);return AssessmentScope(**data)
 def test_authorization_required_and_missing_device_target(self):self.assertFalse(self.scope(authorization_confirmed=False).validate(for_start=True).valid);self.assertFalse(self.scope(device_serial="",package_identifier="",target_name="").validate().valid)
 def test_allowed_excluded_precedence_and_dates(self):
  self.assertFalse(self.scope(excluded_actions=("recon",)).allows("recon"));self.assertFalse(self.scope(end_date=(date.today()-timedelta(days=1)).isoformat()).allows("recon"));self.assertTrue(self.scope().allows("recon"))
 def test_serialization_digest_identifier_and_labels(self):
  item=self.scope(package_identifier="Com.Exact.App");self.assertEqual(AssessmentScope.from_dict(item.to_dict()).digest,item.digest);self.assertIn("Com.Exact.App",item.display_summary);self.assertIn("destructive-testing",HIGH_IMPACT_CATEGORIES)
 def test_bad_dates(self):self.assertFalse(self.scope(start_date="bad").validate().valid)
