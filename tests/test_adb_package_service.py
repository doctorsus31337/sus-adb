import unittest
from app.core.adb_package_service import ADBPackageService
from app.core.command_result import CommandResult

class FakeADB:
 adb_path="/fake/adb"
 def __init__(self):self.calls=[];self.outputs=[]
 def run(self,*args,serial=None,**kw):
  self.calls.append((args,serial));return self.outputs.pop(0) if self.outputs else CommandResult(tuple(args),0,"Success")
class Session:
 def __init__(self,allowed):self.allowed=set(allowed)
 def permits(self,c):return c in self.allowed
class Sink:
 def __init__(self):self.values=[]
 def append(self,v):self.values.append(v)
 def register(self,v):self.values.append(v)
class PackageServiceTests(unittest.TestCase):
 def test_list_kinds_and_explicit_serial(self):
  adb=FakeADB();adb.outputs=[CommandResult((),0,"package:/data/app/a.apk=com.a")];s=ADBPackageService(adb);r=s.list_packages("SER","user")
  self.assertTrue(r.ok);self.assertEqual(r.value[0].identifier,"com.a");self.assertEqual(adb.calls[0][1],"SER");self.assertIn("-3",adb.calls[0][0])
 def test_inspect_split_permissions_and_debuggable(self):
  adb=FakeADB();adb.outputs=[CommandResult((),0,"versionName=1.2\nversionCode=8\nuserId=10001\ndataDir=/data/user/0/com.a\nDEBUGGABLE\nrequested permissions:\n    android.permission.CAMERA\ninstall permissions:\n    android.permission.CAMERA: granted=true"),CommandResult((),0,"package:/base.apk\npackage:/split.apk")];r=ADBPackageService(adb).inspect("S","com.a")
  self.assertEqual(r.value.apk_paths,("/base.apk","/split.apk"));self.assertTrue(r.value.debuggable);self.assertIn("android.permission.CAMERA",r.value.granted_permissions)
 def test_scope_typed_confirmation_timeline_and_change(self):
  adb=FakeADB();timeline=Sink();changes=Sink();service=ADBPackageService(adb,lambda:Session({"destructive-testing","state-changing-testing"}),lambda:timeline,lambda:changes)
  denied=service.execute("S","clear-data","com.a",confirmed=True,typed_confirmation="wrong");self.assertFalse(denied.ok);self.assertFalse(adb.calls)
  done=service.execute("S","uninstall","com.a",confirmed=True,typed_confirmation="com.a");self.assertTrue(done.ok);self.assertEqual(adb.calls[-1][1],"S");self.assertTrue(timeline.values)
  service.execute("S","disable","com.a",confirmed=True);self.assertTrue(changes.values)
 def test_install_preview_and_excluded_scope(self):
  adb=FakeADB();service=ADBPackageService(adb,lambda:Session(set()));r=service.execute("S","install",value="/tmp/a.apk",confirmed=True)
  self.assertFalse(r.ok);self.assertEqual(r.preview[-2:],("install","/tmp/a.apk"));self.assertFalse(adb.calls)

if __name__=="__main__":unittest.main()
