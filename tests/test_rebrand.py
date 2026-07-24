import json
import unittest
from pathlib import Path

from app.core.app_metadata import METADATA
from app.core.config_manager import ConfigManager


ROOT=Path(__file__).parents[1]


class RebrandTests(unittest.TestCase):
    def test_central_product_identity_and_legacy_storage(self):
        self.assertEqual(METADATA.application_name,"SUS Companion");self.assertEqual(METADATA.display_mark,"SUS COMPANION");self.assertEqual(METADATA.descriptor,"Android Security & Recovery Workstation");self.assertEqual(METADATA.preferred_executable,"sus-companion");self.assertEqual(METADATA.legacy_executable,"sus-adb")
        self.assertEqual(str(ConfigManager.resolve_directory("posix",{"XDG_CONFIG_HOME":"/tmp/config"})),"/tmp/config/sus-adb");self.assertIn("SUS-ADB",str(ConfigManager.resolve_directory("nt",{"APPDATA":"C:/Users/Test/AppData"})))

    def test_plugin_ids_and_public_api_remain_stable(self):
        ids={json.loads(path.read_text(encoding="utf-8"))["plugin_id"] for path in (ROOT/"plugins/official").glob("*/manifest.json")};self.assertEqual(ids,{"susadb.device-rescue-recovery","susadb.rootability-advisor","susadb.webview-security-inspector","susadb.skeleton-module","susadb.frida-tutorial","susadb.objection-tutorial"});self.assertEqual(METADATA.plugin_api_version,"1.0")

    def test_gui_and_package_metadata_use_new_brand(self):
        header=(ROOT/"app/gui/gothic_header.py").read_text(encoding="utf-8");desktop=(ROOT/"packaging/linux/sus-adb.desktop").read_text(encoding="utf-8");windows=(ROOT/"packaging/windows/version_info.txt").read_text(encoding="utf-8");spec=(ROOT/"packaging/pyinstaller/sus_adb.spec").read_text(encoding="utf-8")
        self.assertIn("METADATA.display_mark",header);self.assertNotIn("SUS-ADB COMPANION",header);self.assertIn("Name=SUS Companion",desktop);self.assertIn("Exec=sus-companion",desktop);self.assertIn("SUS Companion",windows);self.assertIn("name='sus-companion'",spec)


if __name__=="__main__":unittest.main()
