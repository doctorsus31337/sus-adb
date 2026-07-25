import unittest
from types import SimpleNamespace
from app.core.command_result import CommandResult
from app.core.content_provider_service import ContentProviderService
from app.core.storage_models import ContentQuerySpec
class ADB:
 adb_path="/adb"
 def __init__(self):self.calls=[]
 def run(self,*a,serial=None,**kw):self.calls.append((a,serial));return CommandResult(a,0,"Row: 0 name=alice, age=2")
class Components:
 def discover(self,s,p):return SimpleNamespace(ok=True,value=(SimpleNamespace(component_type=SimpleNamespace(value="provider"),authorities=("pkg.data",),name="P",exported=True,enabled=True,permission=""),))
class Session:
 scope=SimpleNamespace(device_serial="S",package_identifier="pkg")
 def permits(self,c):return True
class ProviderTests(unittest.TestCase):
 def test_records_preview_confirm_query_parse_and_limit(self):
  adb=ADB();svc=ContentProviderService(adb,Components(),lambda:Session(),max_rows=50);self.assertEqual(svc.list("S","pkg").value[0].authority,"pkg.data");spec=ContentQuerySpec("content://pkg.data/items",("name",),row_limit=100);preview=svc.build("S",spec);self.assertIn("--limit",preview.preview);self.assertFalse(svc.query("S","pkg",spec,False).ok);r=svc.query("S","pkg",spec,True);self.assertEqual(r.value[0]["name"],"alice");self.assertEqual(adb.calls[0][1],"S")
 def test_invalid_uri_no_fuzzing(self):self.assertFalse(ContentProviderService(ADB(),Components()).build("S",ContentQuerySpec("http://x")).ok)
