import unittest
from app.core.adb_component_service import ADBComponentService
from app.core.command_result import CommandResult

class ADB:
 def __init__(self,text):self.text=text;self.calls=[]
 def run(self,*a,serial=None):self.calls.append((a,serial));return CommandResult(a,0,self.text)
class ComponentTests(unittest.TestCase):
 TEXT='''Activities:\n  123 com.demo/.MainActivity exported=true enabled=true\n    Action: android.intent.action.MAIN\n    Category: android.intent.category.LAUNCHER\nServices:\n  456 com.demo/.SyncService exported=false permission=com.demo.SYNC\nReceivers:\n  789 com.demo/.Boot Receiver exported=true\nProviders:\n  abc com.demo/.DataProvider authority=com.demo.data;com.demo.files\n'''
 def test_types_permissions_actions_and_serial(self):
  adb=ADB(self.TEXT);r=ADBComponentService(adb).discover("SER","com.demo");self.assertTrue(r.ok);self.assertEqual(adb.calls[0][1],"SER");self.assertEqual({x.component_type.value for x in r.value},{"activity","service","receiver","provider"});self.assertIn("android.intent.action.MAIN",r.value[0].intent_actions)
 def test_search_filter_and_no_launch(self):
  service=ADBComponentService(ADB(self.TEXT));service.discover("S","com.demo");self.assertEqual(len(service.filter("sync","service")),1)
 def test_malformed_is_warning(self):
  r=ADBComponentService(ADB("unexpected Android output")).discover("S","p");self.assertTrue(r.ok);self.assertTrue(r.warning)

if __name__=="__main__":unittest.main()
