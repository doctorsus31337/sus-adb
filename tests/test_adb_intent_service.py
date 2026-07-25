import unittest
from app.core.adb_intent_service import ADBIntentService,IntentExtra
from app.core.command_result import CommandResult
class ADB:
 adb_path="adb"
 def __init__(self):self.calls=[]
 def run(self,*a,serial=None):self.calls.append((a,serial));return CommandResult(a,0,"Starting")
class Session:
 def __init__(self,yes=True):self.yes=yes
 def permits(self,c):return self.yes and c=="runtime-inspection"
class IntentTests(unittest.TestCase):
 def test_activity_deep_link_broadcast_service_and_typed_extras(self):
  s=ADBIntentService(ADB());a=s.build("S","activity",component="com.a/.Main",action="x",categories=("cat",),flags=("0x1",),extras=(IntentExtra("boolean","b",True),IntentExtra("integer","n",3)));self.assertIn("--ez",a.preview);self.assertIn("com.a/.Main",a.preview)
  self.assertTrue(s.build("S","deep-link",uri="demo://host/a b").ok);self.assertTrue(s.build("S","broadcast",action="x").ok);self.assertTrue(s.build("S","start-service",component="p/.S").ok)
 def test_malformed_and_scope_confirmation(self):
  adb=ADB();s=ADBIntentService(adb,lambda:Session(False));self.assertFalse(s.build("S","component",component="bad").ok);self.assertFalse(s.build("S","deep-link",uri="no-scheme").ok);self.assertFalse(s.execute("S","activity",package="p",confirmed=True).ok);self.assertFalse(adb.calls)
  s=ADBIntentService(adb,lambda:Session());self.assertFalse(s.execute("S","activity",package="p").ok);self.assertTrue(s.execute("S","activity",package="p",confirmed=True).ok);self.assertEqual(adb.calls[-1][1],"S")

if __name__=="__main__":unittest.main()
