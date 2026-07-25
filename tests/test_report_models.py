import unittest
from app.core.report_models import *
class T(unittest.TestCase):
 def test_portable_roundtrip(self):
  p=ReportProfile("Default",logo_path_reference="/private/logo.png");self.assertFalse(p.logo_path_reference.startswith("/"));s=ReportSnapshot("c","d","active",p,output_paths=("/reports/a.html",));self.assertEqual(ReportSnapshot.from_dict(s.to_dict()).report_profile,p);self.assertFalse(s.output_paths[0].startswith("/"))
