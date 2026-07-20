import importlib.util,tempfile,unittest
from pathlib import Path
class ReleaseManifestTests(unittest.TestCase):
 def test_required_resources_and_spec_are_portable(self):
  root=Path(__file__).parents[1];required=("VERSION","packaging/pyinstaller/sus_adb.spec","packaging/linux/build_linux.sh","packaging/windows/build_windows.ps1","release/RC1_CHECKLIST.md")
  self.assertTrue(all((root/p).exists() for p in required));text=(root/required[1]).read_text();self.assertNotIn("/home/",text);self.assertNotIn("C:\\Users\\",text)
 def test_checksum_helper(self):
  root=Path(__file__).parents[1];spec=importlib.util.spec_from_file_location("checksums",root/"packaging/common/generate_checksums.py");module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/"artifact";p.write_bytes(b"abc");manifest=module.generate(Path(d));module.generate(Path(d));self.assertEqual(manifest["files"][0]["path"],"artifact");self.assertEqual(len(manifest["files"]),1);self.assertTrue((Path(d)/"SHA256SUMS").exists())
if __name__=="__main__":unittest.main()
