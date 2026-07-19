import unittest
from app.core.app_metadata import AppMetadata,create_metadata
class MetadataTests(unittest.TestCase):
 def test_injected_metadata_is_deterministic(self):
  value=create_metadata(version="1.0.0-rc.1",repository_revision="abc123",build_timestamp="2026-01-01T00:00:00Z",platform_name="TestOS",architecture="test64",python_version="3.13")
  self.assertIsInstance(value,AppMetadata);self.assertEqual(value.release_channel,"rc");self.assertIn("1.0.0-rc.1",value.display_version);self.assertEqual(value.repository_revision,"abc123")
if __name__=="__main__":unittest.main()
