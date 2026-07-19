"""User-local atomic configuration persistence with quarantine and migration."""
from __future__ import annotations
import json,os,shutil,tempfile
from dataclasses import dataclass
from pathlib import Path
from app.core.config_schema import SCHEMA_VERSION,defaults,validate
from app.core.config_migrations import migrate
@dataclass(frozen=True,slots=True)
class ConfigResult:
    ok:bool;data:dict|None=None;path:str|None=None;warning:str|None=None;error:str|None=None;migrations:tuple[int,...]=()
class ConfigManager:
    def __init__(self,config_dir=None,platform_name=None,environ=None):self.directory=Path(config_dir or self.resolve_directory(platform_name,environ)).expanduser().resolve();self.path=self.directory/"config.json"
    @staticmethod
    def resolve_directory(platform_name=None,environ=None):
        env=dict(environ or os.environ);name=(platform_name or os.name).lower()
        if name.startswith("win") or name=="nt":return Path(env.get("APPDATA",Path.home()))/"SUS-ADB"
        return Path(env.get("XDG_CONFIG_HOME",Path.home()/".config"))/"sus-adb"
    def load(self):
        if not self.path.exists():return ConfigResult(True,defaults(),str(self.path),warning="First run: using safe defaults.")
        try:
            raw=json.loads(self.path.read_text(encoding="utf-8"));errors=validate(raw)
            if errors:raise ValueError("; ".join(errors))
            migrated,applied=migrate(raw);merged=defaults();self._merge(merged,migrated)
            if applied:
                shutil.copy2(self.path,self.path.with_suffix(".json.bak"));self.save(merged)
            return ConfigResult(True,merged,str(self.path),migrations=applied)
        except (OSError,ValueError,TypeError,json.JSONDecodeError) as exc:
            try:self.directory.mkdir(parents=True,exist_ok=True);q=self.directory/"config.malformed.json";self.path.replace(q)
            except OSError:q=None
            return ConfigResult(True,defaults(),str(self.path),warning=f"Malformed configuration quarantined: {exc}")
    @staticmethod
    def _merge(base,updates):
        for k,v in updates.items():
            if isinstance(v,dict) and isinstance(base.get(k),dict):ConfigManager._merge(base[k],v)
            else:base[k]=v
    def save(self,data):
        errors=validate(data)
        if errors:return ConfigResult(False,error="; ".join(errors))
        try:
            self.directory.mkdir(parents=True,exist_ok=True);fd,tmp=tempfile.mkstemp(prefix="config-",suffix=".tmp",dir=self.directory)
            with os.fdopen(fd,"w",encoding="utf-8") as f:json.dump(data,f,indent=2,sort_keys=True);f.write("\n");f.flush();os.fsync(f.fileno())
            os.replace(tmp,self.path);return ConfigResult(True,dict(data),str(self.path))
        except OSError as exc:return ConfigResult(False,error=str(exc))
    def export(self,path,data,redact_paths=False):
        out=json.loads(json.dumps(data))
        if redact_paths:
            for key in ("workspace_root","script_library_root","plugin_storage_root","last_active_case"):
                if out.get(key):out[key]="[LOCAL-PATH-REDACTED]"
        p=Path(path).resolve();p.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n",encoding="utf-8");return ConfigResult(True,out,str(p))
