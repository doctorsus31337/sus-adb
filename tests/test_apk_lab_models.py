import unittest
from app.core.apk_lab_models import *
class T(unittest.TestCase):
 def test_models(self):
  a=ApkArtifact("base-apk","/a","originals/a","d",1,"p");self.assertEqual(a.to_dict()["artifact_type"],"base-apk");self.assertIn("p",a.display_label);self.assertIn("complete",ApkSetRecord("p",a,complete=True).display_label);self.assertIn("SDK",ApkManifestSummary("p").display_label);self.assertEqual(ApkDifference("x","added").to_dict()["difference_type"],"added")
