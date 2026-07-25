import unittest
from app.core.apk_build_service import ApkBuildService
class T(unittest.TestCase):
 def test_preview(self):self.assertEqual(ApkBuildService(None).preview_align("zipalign","a","b")[-2:],("a","b"))
