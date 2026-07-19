import tempfile,unittest
from pathlib import Path
from app.core.adb_explorer_models import AccessMethod
from app.core.adb_file_service import ADBFileService
from app.core.command_result import CommandResult
class ADB:
 def __init__(self):self.calls=[];self.results=[]
 def run(self,*a,serial=None):self.calls.append((a,serial));return self.results.pop(0) if self.results else CommandResult(a,0,"ok")
class Session:
 def __init__(self,allowed):self.allowed=set(allowed)
 def permits(self,c):return c in self.allowed
class FileTests(unittest.TestCase):
 def test_modes_listing_and_quoting(self):
  adb=ADB();adb.results=[CommandResult((),0,"-rw-r--r-- 1 u g 12 Jan 01 00:00 a b.txt")];s=ADBFileService(adb,lambda:Session({"storage-inspection","sensitive-data-inspection"}));r=s.list_directory("SER","/sdcard/a b",AccessMethod.ROOT,"p");self.assertTrue(r.ok);self.assertIn("'/sdcard/a b'",adb.calls[0][0][-1]);self.assertEqual(adb.calls[0][1],"SER")
  adb.results=[CommandResult((),0,"")];s.list_directory("SER","/data/user/0/p",AccessMethod.RUN_AS,"p");self.assertIn("run-as",adb.calls[-1][0])
 def test_delete_guard_confirmation_and_scope(self):
  adb=ADB();s=ADBFileService(adb,lambda:Session({"state-changing-testing"}));self.assertFalse(s.mutate("S","delete","/",confirmed=True,typed="/").ok);self.assertFalse(s.mutate("S","delete","/sdcard/x",confirmed=True,typed="wrong").ok);self.assertTrue(s.mutate("S","delete","/sdcard/x",confirmed=True,typed="/sdcard/x").ok)
 def test_push_pull_no_overwrite_and_no_execution(self):
  with tempfile.TemporaryDirectory() as d:
   src=Path(d)/"src";src.write_text("x");dest=Path(d)/"dest";dest.write_text("old");adb=ADB();s=ADBFileService(adb,lambda:Session({"state-changing-testing","storage-inspection"}));self.assertFalse(s.pull("S","/sdcard/x",dest).ok);self.assertTrue(s.push("S",src,"/sdcard/x",confirmed=True).ok);self.assertEqual(adb.calls[-1][1],"S")
 def test_remote_hash_and_metadata(self):
  adb=ADB();adb.results=[CommandResult((),0,"abc  /x"),CommandResult((),0,"size=1")];s=ADBFileService(adb);self.assertEqual(s.remote_hash("S","/x").value,"abc");self.assertTrue(s.metadata("S","/x").ok)

if __name__=="__main__":unittest.main()
