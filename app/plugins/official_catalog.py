"""Read-only bundled official-plugin catalog; installation is always explicit."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from app.plugins.plugin_package import PluginPackage
from app.plugins.plugin_validator import PluginValidator

@dataclass(frozen=True,slots=True)
class OfficialCatalogItem:
    path:Path;manifest:object;package_digest:str;valid:bool;errors:tuple[str,...]=();installed:bool=False

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
