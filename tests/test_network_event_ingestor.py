import unittest
from tempfile import TemporaryDirectory
from pathlib import Path
from types import SimpleNamespace
from app.core.network_event_ingestor import NetworkEventIngestor

class Runtime:
 def __init__(self):self.listeners=[]
 def add_event_listener(self,c):self.listeners.append(c)
 def remove_event_listener(self,c):self.listeners.remove(c)
class NetworkEventTests(unittest.TestCase):
 def test_additive_normalize_filter_bound_export_cleanup(self):
  runtime=Runtime();existing=lambda e:None;runtime.listeners.append(existing);i=NetworkEventIngestor(runtime,2)
  self.assertIsNone(i.ingest(SimpleNamespace(payload={"payload":{"type":"log"}})))
  for host in ("a.test","b.test","c.test"):i.ingest(SimpleNamespace(script_id="s",payload={"payload":{"channel":"sus-adb-network","event_type":"request","host":host,"port":443,"method":"GET"}}))
  self.assertEqual(len(i.events),2);self.assertEqual(i.dropped,1);self.assertEqual(i.filter(host="c")[0].host,"c.test")
  with TemporaryDirectory() as td:self.assertEqual(len(Path(i.export_jsonl(Path(td)/"e.jsonl")).read_text().splitlines()),2)
  i.close();self.assertEqual(runtime.listeners,[existing])
 def test_malformed_and_pause_collection(self):
  i=NetworkEventIngestor(Runtime());i.paused=True;seen=[];i.add_listener(seen.append);self.assertIsNone(i.ingest({"payload":{"channel":"sus-adb-network","event_type":"request","port":"bad"}}));self.assertIsNotNone(i.ingest({"payload":{"channel":"sus-adb-network","event_type":"dns","host":"x"}}));self.assertEqual(len(i.events),1);self.assertFalse(seen)
