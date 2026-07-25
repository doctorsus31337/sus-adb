import tempfile
import threading
import unittest
from pathlib import Path

from app.plugins.contribution_registry import ContributionRegistry
from app.plugins.plugin_manager import PluginManager
from app.plugins.plugin_store import PluginStore
from app.plugins.plugin_trust import PluginTrustStore


ROOT=Path(__file__).parents[1]


class LazyStartupTests(unittest.TestCase):
    def test_main_does_not_import_heavy_panels_eagerly(self):
        source=(ROOT/"app/gui/main_window.py").read_text(encoding="utf-8")
        prefix=source.split("class SusADBWindow",1)[0]
        for module in ("instrumentation_panel","script_studio_panel","pentest_workspace"):
            self.assertNotIn(f"from app.gui.{module} import",prefix)
        self.assertIn("LazyPanelHost",source);self.assertIn("first-responsive-idle",source)

    def test_pentest_heavy_sections_are_not_called_by_constructor(self):
        source=(ROOT/"app/gui/pentest_workspace.py").read_text(encoding="utf-8");constructor=source.split("def __init__",1)[1].split("def _button",1)[0]
        for builder in ("_build_adb_explorer()","_build_runtime_explorer()","_build_network()","_build_storage()","_build_apk_lab()","_build_findings_reporting()","_build_plugins()"):
            self.assertNotIn(builder,constructor)
        for section in ("ADB Explorer","Runtime Explorer","Network","Storage","APK Lab","Findings","Reports","Plugins"):
            self.assertIn(f'"{section}"',source)

    def test_plugin_indexing_can_be_deferred_without_loading(self):
        with tempfile.TemporaryDirectory() as directory:
            store=PluginStore(Path(directory)/"store");calls=[];original=store.installed
            store.installed=lambda:(calls.append(threading.get_ident()) or original())
            manager=PluginManager(store,PluginTrustStore(store.root/"state/trust.json"),ContributionRegistry(),auto_refresh=False)
            self.assertFalse(calls);self.assertFalse(manager.records);self.assertFalse(manager.loader.statuses);manager.ensure_refreshed();self.assertEqual(len(calls),1);self.assertFalse(manager.loader.statuses)

    def test_lazy_host_enforces_gui_thread_construction_contract(self):
        source=(ROOT/"app/gui/lazy_panel_host.py").read_text(encoding="utf-8")
        self.assertIn("threading.main_thread()",source);self.assertNotIn("BackgroundWorker",source);self.assertIn("shutdown_started",source)


if __name__=="__main__":unittest.main()
