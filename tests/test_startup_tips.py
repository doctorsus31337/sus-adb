import json
import tempfile
import unittest
from pathlib import Path

from app.core.startup_tips import FALLBACK_TIPS,load_startup_tips


class StartupTipTests(unittest.TestCase):
    def test_packaged_catalog_is_bounded_local_and_deterministic(self):
        catalog=load_startup_tips();self.assertGreaterEqual(len(catalog.tips),5);self.assertLessEqual(len(catalog.tips),24);self.assertEqual(catalog.select(0),catalog.select(len(catalog.tips)));self.assertFalse(catalog.warning)
        text=" ".join(catalog.tips).casefold();self.assertNotIn("http://",text);self.assertNotIn("https://",text);self.assertNotIn("always recover",text)

    def test_malformed_or_missing_resource_falls_back_safely(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"tips.json";path.write_text("{",encoding="utf-8");malformed=load_startup_tips(path);missing=load_startup_tips(path.with_name("missing.json"));self.assertEqual(malformed.tips,FALLBACK_TIPS);self.assertEqual(missing.tips,FALLBACK_TIPS);self.assertTrue(malformed.warning)

    def test_catalog_filters_invalid_and_limits_count(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"tips.json";path.write_text(json.dumps({"tips":["A valid local startup tip that is long enough.",7,"short","Another valid local startup tip for testing."]}),encoding="utf-8");catalog=load_startup_tips(path,maximum=2);self.assertEqual(catalog.tips,("A valid local startup tip that is long enough.",))


if __name__=="__main__":unittest.main()
