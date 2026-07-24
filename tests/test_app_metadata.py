import json,tempfile,unittest
from pathlib import Path
from app.core.app_metadata import AppMetadata,create_metadata
class MetadataTests(unittest.TestCase):
 def test_injected_metadata_is_deterministic(self):
  value=create_metadata(version="1.0.0-rc.1",repository_revision="abc1234567890",repository_ref="feature/test",build_timestamp="2026-01-01T00:00:00Z",build_channel="current-testing",platform_name="TestOS",architecture="test64",python_version="3.13")
  self.assertIsInstance(value,AppMetadata);self.assertEqual(value.release_channel,"rc");self.assertIn("SUS Companion",value.display_version);self.assertIn("1.0.0-rc.1",value.display_version);self.assertEqual(value.descriptor,"Android Security & Recovery Workstation");self.assertEqual(value.short_revision,"abc123456789");self.assertIn("Branch/ref: feature/test",value.build_details);self.assertIn("Build channel: current-testing",value.build_details);self.assertEqual(value.configuration_schema_version,4)
 def test_packaged_build_info_and_environment_override(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);version=root/"VERSION";info=root/"build-info.json";version.write_text("2.0.0-test\n");info.write_text(json.dumps({"commit":"a"*40,"ref":"feature/from-file","timestamp":"2026-07-24T12:00:00Z","channel":"testing"}))
   value=AppMetadata.current(version,info,{});self.assertEqual(value.version,"2.0.0-test");self.assertEqual(value.repository_revision,"a"*40);self.assertEqual(value.repository_ref,"feature/from-file");self.assertEqual(value.build_channel,"testing")
   overridden=AppMetadata.current(version,info,{"SUS_ADB_REVISION":"b"*40,"SUS_ADB_REF":"chosen/ref","SUS_ADB_BUILD_TIMESTAMP":"later","SUS_ADB_BUILD_CHANNEL":"acceptance"});self.assertEqual(overridden.repository_revision,"b"*40);self.assertEqual(overridden.repository_ref,"chosen/ref");self.assertEqual(overridden.build_timestamp,"later");self.assertEqual(overridden.build_channel,"acceptance")
 def test_source_checkout_identity_is_read_without_process_launch(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);(root/"VERSION").write_text("1.0.0\n");git=root/".git";(git/"refs/heads/feature").mkdir(parents=True);(git/"HEAD").write_text("ref: refs/heads/feature/local\n");(git/"refs/heads/feature/local").write_text("c"*40)
   value=AppMetadata.current(root/"VERSION",root/"missing.json",{});self.assertEqual(value.repository_revision,"c"*40);self.assertEqual(value.repository_ref,"feature/local");self.assertEqual(value.build_channel,"source")
if __name__=="__main__":unittest.main()
