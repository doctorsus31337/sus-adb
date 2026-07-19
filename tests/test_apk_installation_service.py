import unittest
from app.core.apk_installation_service import ApkInstallationService
class A:adb_path="adb"
class T(unittest.TestCase):
 def test_preview_serial_flags(self):self.assertEqual(ApkInstallationService(A()).preview("S",("a",),True,True)[:3],("adb","-s","S"))
