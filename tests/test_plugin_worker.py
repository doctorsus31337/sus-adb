import unittest
from app.plugins.plugin_worker import PluginWorker
class Proc:
 returncode=0
 def communicate(self,data,timeout):return ('{"ok":true}','diagnostic')
 def terminate(self):pass
 def wait(self,timeout):pass
class T(unittest.TestCase):
 def test_protocol_sanitized_fake_and_cancel(self):
  seen={}
  def factory(argv,**kw):seen.update(kw);return Proc()
  w=PluginWorker(factory);r=w.request(("fake",),{"x":1},"/tmp");self.assertTrue(r.ok);self.assertFalse(seen["shell"]);self.assertNotIn("SECRET",PluginWorker.sanitized_environment({"PATH":"x","SECRET":"y"}));w.cancel();self.assertTrue(w.cancelled)
