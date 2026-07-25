import unittest
from app.core.apk_decode_service import ApkDecodeService
class T(unittest.TestCase):
 def test_preview_confirmation(self):self.assertIn("-o",ApkDecodeService().preview("apktool","a","b"));self.assertFalse(ApkDecodeService().extract("a","b",False)[0])
