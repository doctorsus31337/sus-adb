"""Read-only bundled official-plugin catalog; installation is always explicit."""
from __future__ import annotations
import shutil
from dataclasses import dataclass
from pathlib import Path,PurePosixPath
from app.plugins.plugin_package import PluginPackage
from app.plugins.plugin_validator import PluginValidator

@dataclass(frozen=True,slots=True)
class OfficialCatalogItem:
    path:Path;manifest:object;package_digest:str;valid:bool;errors:tuple[str,...]=();installed:bool=False

@dataclass(frozen=True,slots=True)
class TemplateExportResult:
    ok:bool;path:str="";file_count:int=0;total_bytes:int=0;source_digest:str="";error:str=""

class OfficialPluginCatalog:
    def __init__(self,root,tracked_paths=None):
        self.root=Path(root).resolve();self.tracked_paths=None if tracked_paths is None else frozenset(str(v).replace("\\","/") for v in tracked_paths);self.validator=PluginValidator()
    def _tracked(self,path):
        if self.tracked_paths is None:return True
        prefix=path.relative_to(self.root).as_posix()+"/"
        return any(value.startswith(prefix) for value in self.tracked_paths)
    def list(self,installed_ids=()):
        values=[]
        if not self.root.is_dir():return ()
        for path in sorted(p for p in self.root.iterdir() if p.is_dir() and self._tracked(p)):
            inspection=PluginPackage.inspect(path);validation=self.validator.validate(inspection,root=path)
            if inspection.manifest:values.append(OfficialCatalogItem(path,inspection.manifest,inspection.package_digest,validation.valid,validation.errors,inspection.manifest.plugin_id in installed_ids))
        return tuple(sorted(values,key=lambda item:item.manifest.plugin_id))
    def get(self,plugin_id,installed_ids=()):return next((item for item in self.list(installed_ids) if item.manifest.plugin_id==plugin_id),None)
    def export_template(self,plugin_id,action_id,destination,expected_digest="",max_files=64,max_bytes=2*1024*1024):
        item=self.get(plugin_id)
        if not item or not item.valid:return TemplateExportResult(False,error="Validated official addon was not found.")
        current=PluginPackage.inspect(item.path)
        if not current.ok or current.package_digest!=item.package_digest or expected_digest and current.package_digest!=expected_digest:return TemplateExportResult(False,error="Official template digest changed before export.")
        action=next((v for v in item.manifest.addon_ui.get("catalog_actions",()) if v.get("action_id")==action_id and v.get("kind")=="export-template"),None)
        if not action:return TemplateExportResult(False,error="Approved template export action was not found.")
        destination_name=str(action.get("destination_name","")).strip();includes=tuple(action.get("include",()))
        if not destination_name or PurePosixPath(destination_name).name!=destination_name:return TemplateExportResult(False,error="Unsafe template destination name.")
        target=Path(destination).expanduser().resolve()/destination_name
        if target.exists():return TemplateExportResult(False,error="Template destination already exists; choose another directory.")
        files=[];total=0
        for value in includes:
            rel=PurePosixPath(str(value).replace("\\","/"))
            if rel.is_absolute() or ".." in rel.parts or any(part in {"__pycache__","state","logs"} for part in rel.parts) or rel.suffix.casefold() in {".pyc",".pyo"}:return TemplateExportResult(False,error="Unsafe template export path.")
            source=item.path.joinpath(*rel.parts)
            if source.is_symlink() or not source.is_file():return TemplateExportResult(False,error="Template export rejects missing files and symlinks.")
            size=source.stat().st_size;total+=size;files.append((source,rel))
            if len(files)>max_files:return TemplateExportResult(False,error="Template file-count limit exceeded.")
            if total>max_bytes:return TemplateExportResult(False,error="Template byte limit exceeded.")
        try:
            target.mkdir(parents=False)
            for source,rel in files:
                output=target.joinpath(*rel.parts);output.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,output)
        except OSError as exc:
            if target.exists():shutil.rmtree(target,ignore_errors=True)
            return TemplateExportResult(False,error=str(exc))
        return TemplateExportResult(True,str(target),len(files),total,item.package_digest)
