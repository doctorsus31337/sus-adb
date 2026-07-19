import unittest
from types import SimpleNamespace
from app.core.proxy_workflow_service import ProxyWorkflowService

class Manager:
 serial="SER"
 @staticmethod
 def endpoint(h,p):return f"{h}:{int(p)}"
 def apply_proxy(self,*a):return a
 def add_mapping(self,*a):return SimpleNamespace(ok=True)
 def restore_all(self,c):return c
class ProxyWorkflowTests(unittest.TestCase):
 def test_plans_preview_without_execution(self):
  m=Manager();s=ProxyWorkflowService(None,m);p=s.build_plan("Physical Device","192.0.2.1",8080);self.assertIn("settings",p.display_text);self.assertEqual(p.host,"192.0.2.1")
  reverse=s.build_plan("ADB Reverse","127.0.0.1",8080);self.assertEqual(reverse.commands[0][3],"reverse");self.assertEqual(s.apply(p,False),(False,"Explicit confirmation is required."));self.assertIn("pinning",s.troubleshooting())
