import tempfile,unittest
from pathlib import Path
from app.core.apk_comparison_service import ApkComparisonService
class T(unittest.TestCase):
 def test_diff(self):
  with tempfile.TemporaryDirectory() as d:
   a=Path(d)/"a";b=Path(d)/"b";a.mkdir();b.mkdir();(a/"x").write_text("1");(b/"x").write_text("2");(b/"y").write_text("y");self.assertEqual({x.difference_type.value for x in ApkComparisonService().compare(a,b)},{"modified","added"})
