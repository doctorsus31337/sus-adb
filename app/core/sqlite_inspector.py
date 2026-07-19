"""Strictly read-only local SQLite inspection and bounded SELECT execution."""
from __future__ import annotations
import csv,hashlib,json,re,sqlite3
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote
from app.core.storage_models import SQLiteColumnRecord,SQLiteDatabaseRecord,SQLiteTableRecord

@dataclass(frozen=True,slots=True)
class SQLiteResult:
 ok:bool;value:object=None;error:str|None=None;warning:str|None=None;path:str|None=None

class SQLiteInspector:
 def __init__(self,connection_factory=sqlite3.connect,max_rows=500):self.factory=connection_factory;self.max_rows=max_rows;self.connection=None;self.record=None
 def open(self,path,remote_path="",device_serial="",target_identifier=""):
  p=Path(path).expanduser().resolve()
  if not p.is_file():return SQLiteResult(False,error="Select an existing local database.")
  try:
   uri=f"file:{quote(str(p))}?mode=ro";self.connection=self.factory(uri,uri=True);self.connection.execute("PRAGMA query_only=ON");self.connection.enable_load_extension(False) if hasattr(self.connection,"enable_load_extension") else None
   digest=hashlib.sha256(p.read_bytes()).hexdigest();count=self.connection.execute("SELECT count(*) FROM sqlite_master WHERE type IN ('table','view')").fetchone()[0];self.record=SQLiteDatabaseRecord(remote_path or str(p),str(p),p.stat().st_size,digest,False,tuple(str(p)+s for s in ("-wal","-shm") if Path(str(p)+s).exists()),count,device_serial,target_identifier);return SQLiteResult(True,self.record)
  except (sqlite3.Error,OSError,ValueError) as exc:self.close();return SQLiteResult(False,error=f"Database is encrypted, SQLCipher/Realm, corrupt, or unreadable: {exc}")
 def schema(self):
  if not self.connection:return SQLiteResult(False,error="Open a database first.")
  try:
   rows=self.connection.execute("SELECT name,type FROM sqlite_master WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall();items=[]
   for name,kind in rows:
    safe=name.replace('"','""');cols=tuple(SQLiteColumnRecord(name,r[1],r[2] or "",not bool(r[3]),r[4],r[5]) for r in self.connection.execute(f'PRAGMA table_info("{safe}")'))
    indexes=tuple({"name":r[1],"unique":bool(r[2])} for r in self.connection.execute(f'PRAGMA index_list("{safe}")'));foreign=tuple({"table":r[2],"from":r[3],"to":r[4]} for r in self.connection.execute(f'PRAGMA foreign_key_list("{safe}")'));count=self.connection.execute(f'SELECT count(*) FROM "{safe}"').fetchone()[0] if kind=="table" else None
    items.append(SQLiteTableRecord(self.record.remote_path,name,kind,min(count,self.max_rows) if count is not None else None,cols,tuple(c.column_name for c in cols if c.primary_key_order),foreign,indexes))
   triggers=tuple(self.connection.execute("SELECT name,tbl_name,sql FROM sqlite_master WHERE type='trigger' ORDER BY name").fetchall());return SQLiteResult(True,{"objects":tuple(items),"triggers":triggers})
  except sqlite3.Error as exc:return SQLiteResult(False,error=str(exc))
 @staticmethod
 def validate_select(query):
  clean=query.strip().rstrip(";").strip()
  if not clean:return "A SELECT query is required."
  if ";" in clean:return "Multiple SQL statements are forbidden."
  first=re.match(r"^[A-Za-z]+",clean)
  if not first or first.group(0).casefold() not in ("select","with"):return "Only read-only SELECT queries are permitted."
  if re.search(r"\b(insert|update|delete|drop|alter|attach|detach|vacuum|pragma|load_extension|replace|create)\b",clean,re.I):return "State-changing SQL, PRAGMA, attachment, and extension loading are forbidden."
  return None
 def select(self,query,parameters=(),limit=None,offset=0):
  if not self.connection:return SQLiteResult(False,error="Open a database first.")
  if (e:=self.validate_select(query)):return SQLiteResult(False,error=e)
  limit=min(max(1,int(limit or self.max_rows)),self.max_rows);offset=max(0,int(offset))
  try:
   cursor=self.connection.execute(f"SELECT * FROM ({query.strip().rstrip(';')}) LIMIT ? OFFSET ?",tuple(parameters)+(limit,offset));columns=tuple(d[0] for d in cursor.description or ());return SQLiteResult(True,{"columns":columns,"rows":tuple(cursor.fetchall()),"limit":limit,"offset":offset})
  except sqlite3.Error as exc:return SQLiteResult(False,error=str(exc))
 def export_json(self,path,result):return self._export(path,json.dumps([dict(zip(result["columns"],row)) for row in result["rows"]],indent=2,sort_keys=True,default=str))
 def export_csv(self,path,result):
  p=Path(path).expanduser().resolve()
  if p.exists():return SQLiteResult(False,error="Destination exists; overwrite was not authorized.")
  try:
   p.parent.mkdir(parents=True,exist_ok=True)
   with p.open("w",newline="",encoding="utf-8") as f:w=csv.writer(f);w.writerow(result["columns"]);w.writerows(result["rows"])
   return SQLiteResult(True,path=str(p))
  except OSError as exc:return SQLiteResult(False,error=str(exc))
 @staticmethod
 def _export(path,text):
  p=Path(path).expanduser().resolve()
  if p.exists():return SQLiteResult(False,error="Destination exists; overwrite was not authorized.")
  try:p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding="utf-8");return SQLiteResult(True,path=str(p))
  except OSError as exc:return SQLiteResult(False,error=str(exc))
 def close(self):
  if self.connection:self.connection.close();self.connection=None
