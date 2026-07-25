"""Bounded, non-executing local plugin package inspection."""
from __future__ import annotations
import hashlib,json,zipfile
from dataclasses import dataclass,replace
from pathlib import Path,PurePosixPath
from app.plugins.plugin_manifest import PluginManifest
@dataclass(frozen=True,slots=True)
class PackageInspection:
    ok:bool;manifest:PluginManifest|None=None;files:tuple[tuple[str,str,int],...]=();package_digest:str="";error:str|None=None
class PluginPackage:
    MAX_FILES=1000;MAX_TOTAL=50*1024*1024;MAX_FILE=10*1024*1024
    @staticmethod
    def _valid(name):
        p=PurePosixPath(name.replace("\\","/"));return bool(name) and not p.is_absolute() and ".." not in p.parts and not any(part.startswith(".") and part not in {"."} for part in p.parts)
    @classmethod
    def inspect(cls,source):
        source=Path(source).resolve()
        try:
            values=[];manifest_data=None
            if source.is_dir():
                root=source
                for p in sorted(root.rglob("*")):
                    if p.is_symlink():raise ValueError("Plugin packages may not contain symlinks.")
                    if p.is_file():
                        rel=p.relative_to(root).as_posix();data=p.read_bytes();values.append((rel,hashlib.sha256(data).hexdigest(),len(data)))
                        if rel=="manifest.json":manifest_data=json.loads(data)
            elif zipfile.is_zipfile(source):
                with zipfile.ZipFile(source) as z:
                    infos=[i for i in z.infolist() if not i.is_dir()]
                    if len(infos)>cls.MAX_FILES or sum(i.file_size for i in infos)>cls.MAX_TOTAL:raise ValueError("Plugin archive exceeds bounded extraction limits.")
                    for i in sorted(infos,key=lambda x:x.filename):
                        symlink=((i.external_attr>>16)&0o170000)==0o120000
                        ratio=i.file_size/max(1,i.compress_size)
                        if not cls._valid(i.filename) or i.file_size>cls.MAX_FILE or symlink or ratio>100:raise ValueError("Unsafe, symlinked, oversized, or excessively compressed plugin archive entry.")
                        data=z.read(i);values.append((i.filename,hashlib.sha256(data).hexdigest(),len(data)))
                        if i.filename=="manifest.json":manifest_data=json.loads(data)
            else:return PackageInspection(False,error="Select a plugin directory or supported ZIP package.")
            if len(values)>cls.MAX_FILES or sum(v[2] for v in values)>cls.MAX_TOTAL:raise ValueError("Plugin package exceeds bounded limits.")
            if manifest_data is None:raise ValueError("Plugin package has no manifest.json.")
            digest=hashlib.sha256(json.dumps(values,separators=(",",":"),sort_keys=True).encode()).hexdigest();manifest=PluginManifest.from_dict({**manifest_data,"package_digest":digest});manifest=replace(manifest,manifest_digest=manifest.computed_manifest_digest())
            return PackageInspection(True,manifest,tuple(values),digest)
        except (OSError,ValueError,TypeError,zipfile.BadZipFile,json.JSONDecodeError) as exc:return PackageInspection(False,error=str(exc))
