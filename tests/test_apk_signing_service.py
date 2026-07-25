import unittest
from app.core.apk_signing_service import ApkSigningService
class T(unittest.TestCase):
 def test_redacted(self):self.assertIn("pass:<redacted>",ApkSigningService(None,lambda:"secret").preview("apksigner","a","k","alias"));self.assertNotIn("secret",str(ApkSigningService(None,lambda:"secret").preview("a","b","c","d")))
