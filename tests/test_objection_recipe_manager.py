import unittest

from app.core.command_result import CommandResult
from app.core.objection_recipe_manager import ObjectionCapabilities, ObjectionRecipeManager, RecipeResult


class Objection:
    def __init__(self, installed=True): self.installed=installed; self.launched=[]
    def version(self): return CommandResult.from_command(("objection","version"),0,stdout="1") if self.installed else CommandResult.from_command(("objection",),-1,error="missing")
    def build_attach_command(self,target,transport,serial): return ("objection","-S","socket","-n",target,"start")
    def launch_external_session(self,command): self.launched.append(command); return CommandResult.from_command(command,0)


class ObjectionRecipeTests(unittest.TestCase):
    def test_parse_comments_blank_lines_and_order(self): self.assertEqual(ObjectionRecipeManager.parse("# c\nhelp\n\n env\n; x"),("help","env"))
    def test_confirmation_supported_option_and_no_deprecated_syntax(self):
        objection=Objection(); manager=ObjectionRecipeManager(objection,lambda: ObjectionCapabilities(startup_script=True))
        self.assertFalse(manager.prepare("app","socket","s","r.txt","help").ok)
        prepared=manager.prepare("app","socket","s","r.txt","help",confirmed=True); self.assertTrue(prepared.ok); self.assertIn("--startup-script",prepared.launch_command); self.assertNotIn("explore",prepared.launch_command)
        manager.launch(prepared); self.assertEqual(len(objection.launched),1)
    def test_unsupported_fallback_and_missing_objection(self):
        manager=ObjectionRecipeManager(Objection(),lambda: ObjectionCapabilities()); result=manager.prepare("app","socket","s","r","help\nenv",confirmed=True); self.assertFalse(result.ok); self.assertIn("Copy",result.guidance)
        self.assertFalse(ObjectionRecipeManager(Objection(False),lambda: ObjectionCapabilities()).prepare("app","socket","s","r","help",confirmed=True).ok)
