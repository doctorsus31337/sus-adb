"""Safe isolated plugin storage. Installation never imports or executes code."""
from __future__ import annotations
import json,os,shutil,tempfile,zipfile
from dataclasses import dataclass
from pathlib import Path
from app.plugins.plugin_package import PluginPackage,PackageInspection
@dataclass(frozen=True,slots=True)
class StoreResult:
    ok:bool;inspection:PackageInspection|None=None;path:str|None=None;error:str|None=None
class PluginStore:
    LAYOUT=("installed","disabled","quarantine","state","examples")
    def __init__(self,root="plugins"):self.root=Path(root).resolve();[ (self.root/p).mkdir(parents=True,exist_ok=True) for p in self.LAYOUT ]
    def _safe(self,path):
        p=Path(path).resolve()
        if p!=self.root and self.root not in p.parents:raise ValueError("Plugin path escapes the plugin store.")
        return p
    def state_path(self,plugin_id):return self._safe(self.root/"state"/f"{plugin_id}.json")
    def _write_state(self,plugin_id,data):
        p=self.state_path(plugin_id);p.parent.mkdir(parents=True,exist_ok=True)
        descriptor,name=tempfile.mkstemp(prefix=f".{plugin_id}-",suffix=".tmp",dir=p.parent)
        temporary=Path(name)
        try:
            with os.fdopen(descriptor,"w",encoding="utf-8") as stream:json.dump(data,stream,indent=2,sort_keys=True)
            temporary.replace(p)
        except Exception:
            try:os.close(descriptor)
            except OSError:pass
            temporary.unlink(missing_ok=True)
            raise
        return data
    def install(self,source):
        inspection=PluginPackage.inspect(source)
        if not inspection.ok:return StoreResult(False,inspection,error=inspection.error)
        m=inspection.manifest;dest=self._safe(self.root/"disabled"/m.plugin_id/m.version)
        if dest.exists():return StoreResult(False,inspection,error="This plugin version is already stored.")
        staging=Path(tempfile.mkdtemp(prefix="sus-adb-plugin-",dir=self.root/"disabled"))
        try:
            src=Path(source).resolve()
            if src.is_dir():shutil.copytree(src,staging/"package",dirs_exist_ok=True,symlinks=False)
            else:
                (staging/"package").mkdir()
                with zipfile.ZipFile(src) as z:
                    for i in z.infolist():
                        if i.is_dir():continue
                        target=(staging/"package"/i.filename).resolve()
                        if staging/"package" not in target.parents:raise ValueError("Archive traversal rejected.")
                        target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(z.read(i))
            dest.parent.mkdir(parents=True,exist_ok=True);shutil.move(str(staging/"package"),dest);self.set_enabled(m.plugin_id,m.version,False,m.package_digest);return StoreResult(True,inspection,str(dest))
        except (OSError,ValueError,zipfile.BadZipFile) as exc:return StoreResult(False,inspection,error=str(exc))
        finally:shutil.rmtree(staging,ignore_errors=True)
    def set_enabled(self,plugin_id,version,enabled,digest=""):
        data=self.state(plugin_id)
        if data.get("package_digest")!=digest:
            data.pop("reviewed_update_digest",None);data.pop("reviewed_for_digest",None)
        data.update({"plugin_id":plugin_id,"version":version,"enabled":bool(enabled),"package_digest":digest})
        return self._write_state(plugin_id,data)
    def mark_update_reviewed(self,plugin_id,installed_digest,candidate_digest):
        data=self.state(plugin_id)
        if data.get("package_digest")!=installed_digest:return StoreResult(False,error="Installed package changed before update review was recorded.")
        data.update({"reviewed_for_digest":installed_digest,"reviewed_update_digest":candidate_digest})
        self._write_state(plugin_id,data);return StoreResult(True)
    def update_reviewed(self,plugin_id,installed_digest,candidate_digest):
        data=self.state(plugin_id)
        return data.get("reviewed_for_digest")==installed_digest and data.get("reviewed_update_digest")==candidate_digest
    def state(self,plugin_id):
        try:return json.loads(self.state_path(plugin_id).read_text(encoding="utf-8"))
        except (OSError,ValueError):return {"plugin_id":plugin_id,"enabled":False}
    def installed(self):
        values=[]
        for base in (self.root/"disabled",self.root/"installed"):
            for p in sorted(base.glob("*/*")):
                inspection=PluginPackage.inspect(p)
                if inspection.ok:values.append((p,inspection))
        return tuple(values)
    def package_path(self,plugin_id,version):
        for part in ("installed","disabled"):
            p=self._safe(self.root/part/plugin_id/version)
            if p.is_dir():return p
        return None
    def _replace_path(self,source,destination):Path(source).replace(destination)
    def replace_package(self,plugin_id,current_version,current_digest,source,expected_digest):
        candidate=PluginPackage.inspect(source)
        if not candidate.ok:return StoreResult(False,candidate,error=candidate.error)
        manifest=candidate.manifest
        if manifest.plugin_id!=plugin_id:return StoreResult(False,candidate,error="Update candidate plugin ID does not match the installed addon.")
        if candidate.package_digest!=expected_digest:return StoreResult(False,candidate,error="Update candidate digest changed before replacement.")
        current=self.package_path(plugin_id,current_version)
        current_inspection=PluginPackage.inspect(current) if current else None
        if not current_inspection or not current_inspection.ok or current_inspection.package_digest!=current_digest:return StoreResult(False,candidate,error="Installed package changed before replacement.")
        destination=self._safe(self.root/"disabled"/plugin_id/manifest.version)
        if destination.exists() and destination!=current:return StoreResult(False,candidate,error="The update destination already contains another package.")
        staging=Path(tempfile.mkdtemp(prefix=".sus-companion-update-",dir=self.root/"state"))
        staged=staging/"candidate";backup=staging/"previous"
        try:
            src=Path(source).resolve()
            if src.is_dir():shutil.copytree(src,staged,symlinks=False)
            else:
                staged.mkdir()
                with zipfile.ZipFile(src) as archive:
                    for item in archive.infolist():
                        if item.is_dir():continue
                        target=(staged/item.filename).resolve()
                        if staged not in target.parents:raise ValueError("Archive traversal rejected.")
                        target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(archive.read(item))
            copied=PluginPackage.inspect(staged)
            if not copied.ok or copied.package_digest!=expected_digest:raise ValueError("Copied update candidate failed digest verification.")
            destination.parent.mkdir(parents=True,exist_ok=True)
            self._replace_path(current,backup)
            try:
                self._replace_path(staged,destination)
                self._write_state(plugin_id,{"plugin_id":plugin_id,"version":manifest.version,"enabled":False,"package_digest":expected_digest})
            except Exception:
                if destination.exists():shutil.rmtree(destination)
                if backup.exists():self._replace_path(backup,current)
                raise
            return StoreResult(True,copied,str(destination))
        except (OSError,ValueError,zipfile.BadZipFile) as exc:return StoreResult(False,candidate,error=str(exc))
        finally:shutil.rmtree(staging,ignore_errors=True)
    def quarantine(self,plugin_id,version,reason=""):
        src=self.package_path(plugin_id,version)
        if not src:return StoreResult(False,error="Plugin package was not found.")
        dest=self._safe(self.root/"quarantine"/plugin_id/version)
        try:dest.parent.mkdir(parents=True,exist_ok=True);shutil.move(str(src),dest);self.set_enabled(plugin_id,version,False);(dest/"QUARANTINE.txt").write_text(reason,encoding="utf-8");return StoreResult(True,path=str(dest))
        except OSError as exc:return StoreResult(False,error=str(exc))
    def uninstall(self,plugin_id,version,confirmed=False):
        if not confirmed:return StoreResult(False,error="Explicit uninstall confirmation is required.")
        src=self.package_path(plugin_id,version)
        if not src:return StoreResult(False,error="Plugin package was not found.")
        try:shutil.rmtree(src);return StoreResult(True)
        except OSError as exc:return StoreResult(False,error=str(exc))
