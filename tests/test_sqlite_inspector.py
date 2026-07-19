import sqlite3,unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from app.core.sqlite_inspector import SQLiteInspector
class SQLiteTests(unittest.TestCase):
 def test_readonly_schema_select_pagination_export_close(self):
  with TemporaryDirectory() as td:
   p=Path(td)/"d.db";c=sqlite3.connect(p);c.execute("create table parent(id integer primary key,name text)");c.execute("create table child(id integer,parent integer references parent(id))");c.execute("create index ix on child(parent)");c.execute("insert into parent values(1,'a')");c.commit();c.close();i=SQLiteInspector(max_rows=10);self.assertTrue(i.open(p).ok);schema=i.schema();self.assertTrue(schema.ok);r=i.select("SELECT id,name FROM parent WHERE id=?",(1,),5);self.assertEqual(r.value["rows"],((1,"a"),));self.assertTrue(i.export_json(Path(td)/"r.json",r.value).ok);self.assertTrue(i.export_csv(Path(td)/"r.csv",r.value).ok);i.close();self.assertIsNone(i.connection)
 def test_writes_multiple_pragma_extensions_rejected(self):
  for q in ("DELETE FROM x","SELECT 1; SELECT 2","PRAGMA writable_schema=1","SELECT load_extension('x')","ATTACH 'x' AS x"):
   self.assertIsNotNone(SQLiteInspector.validate_select(q),q)
