import tempfile,unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from app.core.assessment_scope import AssessmentScope
from app.core.evidence_store import EvidenceStore
from app.core.frida_target import FridaTarget,TargetType
from app.core.pentest_session import PentestSession
from app.core.runtime_explorer_models import HookTarget,RuntimeHookSpec
from app.core.runtime_explorer_service import RuntimeExplorerService
from app.core.runtime_script_builder import RuntimeScriptBuilder
from app.core.script_event import ScriptEvent,ScriptEventType
from app.core.script_library import ScriptLibrary
from app.core.session_timeline import SessionTimeline

class Discovery:
 def __init__(self):self.stale=False
 def select(self,s,t):self.selection=(s,t)
 def mark_stale(self,r=""):self.stale=True
 def readiness(self):return SimpleNamespace(ok=True,value={"javaAvailable":True})
class Runtime:
 def __init__(self):self.listeners=[];self.loaded={};self.serial="D";self.target=None
 def add_event_listener(self,c):self.listeners.append(c)
 def remove_event_listener(self,c):self.listeners.remove(c)
 def load_script(self,d,**kw):
  record=SimpleNamespace(descriptor=d,loaded_at="now");self.loaded[d.script_id]=record;return SimpleNamespace(ok=True,value=record,warning=None)
 def unload_script(self,s):self.loaded.pop(s,None);return SimpleNamespace(ok=True,error=None)
 def emit(self,payload):
  event=ScriptEvent(ScriptEventType.SEND,"runtime",payload={"payload":payload})
  for listener in tuple(self.listeners):listener(event)

class RuntimeExplorerServiceTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.library=ScriptLibrary(Path(self.temp.name)/"scripts");self.runtime=Runtime();self.discovery=Discovery();self.target=FridaTarget("App","com.app",1,TargetType.APPLICATION,True);self.runtime.target=self.target
  scope=AssessmentScope("case","Case",authorization_confirmed=True,device_serial="D",package_identifier="com.app",allowed_actions=("runtime-inspection","state-changing-testing","evidence-collection"),start_date=date.today().isoformat())
  self.session=PentestSession.draft(scope,Path(self.temp.name)/"case").start().session;self.timeline=SessionTimeline(Path(self.temp.name)/"case");self.evidence=EvidenceStore(self.temp.name,"case");self.evidence.load();self.opened=[]
  self.service=RuntimeExplorerService(self.discovery,RuntimeScriptBuilder(),self.library,self.runtime,lambda:self.session,lambda:self.timeline,lambda:self.evidence,self.opened.append,max_events=10);self.service.select("D",self.target)
 def tearDown(self):self.temp.cleanup()
 def spec(self,changing=False):return RuntimeHookSpec(HookTarget.JAVA_METHOD,"com.app.C","run",("int",),modification_settings={"mode":"replace-return","value":1} if changing else {},changes_runtime=changing,selected_target="com.app",hook_id="hook")
 def test_generate_save_duplicate_open_and_no_auto_load(self):
  self.assertTrue(self.service.readiness().ok);self.assertTrue(self.service.generate(self.spec()).ok);self.assertFalse(self.runtime.loaded)
  saved=self.service.save_preview();self.assertTrue(saved.ok);self.assertTrue(Path(saved.value.path).is_relative_to(self.library.root));self.assertFalse(self.runtime.loaded)
  metadata=Path(saved.value.metadata_path).read_text();self.assertIn('"path": "frida/generated/',metadata);self.assertNotIn(str(self.library.root),metadata)
  self.assertTrue(self.service.save_preview().ok);self.assertTrue(self.service.open_in_script_studio().ok);self.assertEqual(self.opened[-1].script_id,saved.value.script_id)
 def test_confirmation_hook_event_unload_and_timeline(self):
  self.service.generate(self.spec());self.service.save_preview();self.assertFalse(self.service.load_preview().ok);self.assertTrue(self.service.load_preview(True).ok);self.assertIn("hook",self.service.active)
  self.runtime.emit({"channel":"sus-adb-runtime","hookId":"hook","eventType":"method-enter","owner":"C","member":"run","payload":{"arguments":[1]}});self.assertEqual(self.service.events[-1].arguments,(1,));self.assertEqual(self.service.active["hook"].event_count,1)
  self.assertTrue(self.service.unload("hook").ok);self.assertFalse(self.runtime.loaded);self.assertTrue(any("Runtime hook" in event.title for event in self.timeline.events()))
 def test_state_scope_exclusion_and_target_cleanup(self):
  self.service.generate(self.spec(True));self.service.save_preview();self.assertTrue(self.service.load_preview(True).ok);self.assertTrue(self.runtime.loaded)
  excluded=AssessmentScope.from_dict({**self.session.scope.to_dict(),"excluded_actions":["state-changing-testing"]});self.session=PentestSession.draft(excluded,Path(self.temp.name)/"case").start().session
  self.service.unload_all();self.service.generate(self.spec(True));self.service.save_preview();self.assertFalse(self.service.load_preview(True).ok)
  self.service.select("D",FridaTarget("Other","other",2,TargetType.APPLICATION,True));self.assertTrue(self.discovery.stale);self.assertFalse(self.service.preview)
 def test_evidence_export_buffer_and_cleanup(self):
  self.service.generate(self.spec());self.service.save_preview();self.service.load_preview(True)
  for i in range(12):self.runtime.emit({"channel":"sus-adb-runtime","hookId":"hook","eventType":"method-leave","payload":{"returnValue":i}})
  self.assertEqual(len(self.service.events),10);self.assertEqual(self.service.dropped,2);self.assertTrue(self.service.add_evidence(self.service.events[:1]).ok)
  path=Path(self.temp.name)/"events.jsonl";self.assertTrue(self.service.export_jsonl(path).ok);self.assertTrue(path.read_text())
  self.service.cleanup();self.assertFalse(self.runtime.loaded);self.assertFalse(self.runtime.listeners)
