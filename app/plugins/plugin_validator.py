"""Static plugin validation that never imports executable modules."""
from dataclasses import dataclass
import json
from pathlib import Path,PurePosixPath
from app.plugins.plugin_capabilities import CAPABILITIES,HIGH_IMPACT
from app.plugins.plugin_manifest import CONTRIBUTION_TYPES
@dataclass(frozen=True,slots=True)
class PluginValidation:
    errors:tuple[str,...]=();warnings:tuple[str,...]=();capability_cautions:tuple[str,...]=();compatibility_suggestions:tuple[str,...]=()
    @property
    def valid(self):return not self.errors
class PluginValidator:
    def __init__(self,api_version="1.0"):self.api_version=api_version
    def validate(self,inspection,root=None,existing_ids=()):
        if not inspection.ok or not inspection.manifest:return PluginValidation((inspection.error or "Package inspection failed.",))
        m=inspection.manifest;errors=[];warnings=[];cautions=[];suggestions=[];files={v[0] for v in inspection.files}
        entry=m.entry_point.split(":",1)[0].replace("\\","/")
        if not entry.endswith(".py"):entry=entry.replace(".","/")+".py"
        if entry not in files:errors.append("Declared entry-point module is missing.")
        if m.plugin_api_version!=self.api_version:errors.append(f"Plugin API {m.plugin_api_version} is incompatible with host API {self.api_version}.")
        if m.plugin_id in existing_ids:errors.append("Duplicate plugin ID.")
        unknown=set(m.requested_capabilities)-set(CAPABILITIES)
        if unknown:errors.append("Unknown capabilities: "+", ".join(sorted(unknown)))
        bad_types=sorted({c.contribution_type for c in m.contributed_components}-set(CONTRIBUTION_TYPES))
        if bad_types:errors.append("Unsupported contribution types: "+", ".join(bad_types))
        for c in sorted(set(m.requested_capabilities)&HIGH_IMPACT):cautions.append(f"{c} requires explicit high-impact approval and active scope where applicable.")
        declared={entry,"manifest.json"}|{str(c.metadata.get("path","")).replace("\\","/") for c in m.contributed_components}
        undeclared=[f for f in files if f.endswith((".py",".pyc",".pyd",".so",".dll",".dylib")) and f not in declared]
        if undeclared:warnings.append("Undeclared executable/native files: "+", ".join(sorted(undeclared)))
        hidden=[f for f in files if any(part.startswith(".") for part in PurePosixPath(f).parts)]
        if hidden:warnings.append("Suspicious hidden files are present.")
        if inspection.package_digest!=m.package_digest:errors.append("Package digest mismatch.")
        for c in m.contributed_components:
            path=str(c.metadata.get("path","")).replace("\\","/")
            if path and (PurePosixPath(path).is_absolute() or ".." in PurePosixPath(path).parts):errors.append(f"Unsafe contribution path: {path}")
            if path and path not in files:errors.append(f"Missing contributed file: {path}")
        if root:
            package_root=Path(root).resolve()
            for rel in sorted(f for f in files if f.endswith(".meta.json") or "report" in f.casefold() and f.endswith(".json")):
                try:json.loads((package_root/rel).read_text(encoding="utf-8"))
                except (OSError,ValueError,TypeError):errors.append(f"Malformed plugin metadata/template JSON: {rel}")
        if m.optional_dependencies:suggestions.append("Optional dependencies must be reviewed and installed separately; no automatic installation occurs.")
        return PluginValidation(tuple(dict.fromkeys(errors)),tuple(dict.fromkeys(warnings)),tuple(cautions),tuple(suggestions))
