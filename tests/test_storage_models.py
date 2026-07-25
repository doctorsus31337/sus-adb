import unittest
from dataclasses import FrozenInstanceError
from app.core.storage_models import *
class StorageModelTests(unittest.TestCase):
 def test_serialization_labels_and_immutability(self):
  loc=AppStorageLocation("S","pkg","Data","/data/user/0/pkg","data","run-as",True);self.assertEqual(loc.to_dict()["access_mode"],"run-as");self.assertIn("/data",loc.display_label)
  pref=SharedPreferenceEntry("a.xml","key","string","value","value");self.assertIn("key",pref.display_label)
  col=SQLiteColumnRecord("t","id","INTEGER",False,primary_key_order=1);table=SQLiteTableRecord("d","t",columns=(col,),primary_keys=("id",));self.assertIn("t",table.display_label)
  self.assertIn("authority",ContentProviderRecord("p","C","authority").display_label)
  self.assertEqual(StorageDifference("x","added").to_dict()["status"],"added")
  with self.assertRaises(FrozenInstanceError):loc.remote_path="x"
