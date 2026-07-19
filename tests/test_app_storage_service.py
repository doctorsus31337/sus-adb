import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from app.core.command_result import CommandResult
from app.core.app_storage_service import AppStorageService
class ADB:
 def __init__(self):self.calls=[]
 def run(self,*a,serial=None,**kw):self.calls.append((a,serial));return CommandResult(a,0,"uid=0")
class Files:
 def list_directory(self,*a):return SimpleNamespace(ok=True,value=("file",),error=None,warning=None)
 def pull(self,*a,**k):return SimpleNamespace(ok=True,value=a[2],error=None)
class Packages:
 def inspect(self,s,p):return SimpleNamespace(ok=True,value=SimpleNamespace(data_directory=f"/data/user/0/{p}"))
class Session:
 scope=SimpleNamespace(device_serial="S",package_identifier="pkg")
 def __init__(self,allowed=True):self.allowed=allowed
 def permits(self,c):return self.allowed
class StorageServiceTests(unittest.TestCase):
 def test_explicit_selection_modes_scope_and_hash(self):
  adb=ADB();s=AppStorageService(adb,Files(),Packages(),lambda:Session());self.assertFalse(s.discover().ok);s.select("S","pkg");r=s.discover();self.assertTrue(r.ok);self.assertEqual(len(r.value),5);self.assertEqual(adb.calls[0][1],"S");self.assertTrue(s.browse(r.value[0]).ok)
  with TemporaryDirectory() as td:p=Path(td)/"x";p.write_bytes(b"x");self.assertEqual(len(s.local_hash(p).value),64)
 def test_scope_and_other_package_blocked(self):
  s=AppStorageService(ADB(),Files(),Packages(),lambda:Session(False));s.select("S","pkg");self.assertFalse(s.discover().ok)
