"""Bounded, non-executing static inspection for local plugin candidates."""
from __future__ import annotations

import ast
import hashlib
import json
import re
import stat
import zipfile
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Callable, Mapping

from app.plugins.plugin_api import PluginAPI, PluginContext, PluginResult
from app.plugins.plugin_capabilities import CAPABILITIES, HIGH_IMPACT
from app.plugins.plugin_manifest import (
    CONTRIBUTION_TYPES,
    PluginManifest,
)
from app.plugins.plugin_package import PackageInspection, PluginPackage
from app.plugins.plugin_ui import (
    AddonCardSpec,
    AddonCatalogAction,
    AddonUIMode,
    AddonWindowSpec,
    PluginPanelSpec,
    PluginView,
)
from app.plugins.contribution_registry import Contribution
from app.plugins.plugin_validator import PluginValidator


STATIC_LIMITATION = (
    "Static analysis can identify compatibility and packaging problems, but "
    "it does not prove third-party code is safe."
)
TEXT_SUFFIXES = frozenset(
    {".py", ".json", ".md", ".txt", ".toml", ".yaml", ".yml", ".ini", ".cfg"}
)
CLUTTER_PARTS = frozenset(
    {
        ".git", ".hg", ".svn", ".venv", "venv", "__pycache__", ".idea",
        ".vscode", ".pytest_cache", ".mypy_cache", ".ruff_cache", "build",
        "dist", "htmlcov", ".coverage", "logs",
    }
)
CLUTTER_SUFFIXES = frozenset(
    {".pyc", ".pyo", ".log", ".tmp", ".swp", ".bak", ".coverage"}
)
WINDOWS_RESERVED = frozenset(
    {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
     *(f"LPT{i}" for i in range(1, 10))}
)


class FindingSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFORMATION = "information"


class WorkbenchStatus(str, Enum):
    COMPATIBLE = "Compatible"
    NEEDS_REVIEW = "Needs Review"
    BLOCKED = "Blocked"


class SourceKind(str, Enum):
    DIRECTORY = "directory"
    ZIP = "zip"


@dataclass(frozen=True, slots=True)
class PluginWorkbenchSource:
    """Explicit source choice. The absolute path never enters a report."""

    path: Path = field(repr=False, compare=False)
    kind: SourceKind

    @classmethod
    def selected(cls, value: str | Path) -> "PluginWorkbenchSource":
        path = Path(value).expanduser().resolve()
        if path.is_dir():
            return cls(path, SourceKind.DIRECTORY)
        if path.is_file() and path.suffix.casefold() == ".zip":
            return cls(path, SourceKind.ZIP)
        raise ValueError("Select a plugin project directory or ZIP archive.")

    @property
    def display_name(self) -> str:
        return self.path.name


@dataclass(frozen=True, slots=True)
class PluginWorkbenchFile:
    path: str
    digest: str
    size: int
    excluded_reason: str = ""


@dataclass(frozen=True, slots=True)
class PluginWorkbenchFinding:
    rule_id: str
    severity: FindingSeverity
    category: str
    title: str
    explanation: str
    remediation: str
    path: str = ""
    line: int = 0
    column: int = 0


@dataclass(frozen=True, slots=True)
class PluginWorkbenchComparison:
    installed_version: str = ""
    candidate_version: str = ""
    installed_digest: str = ""
    candidate_digest: str = ""
    added_files: tuple[str, ...] = ()
    removed_files: tuple[str, ...] = ()
    modified_files: tuple[str, ...] = ()
    capability_additions: tuple[str, ...] = ()
    capability_removals: tuple[str, ...] = ()
    contribution_additions: tuple[str, ...] = ()
    contribution_removals: tuple[str, ...] = ()
    contribution_changes: tuple[str, ...] = ()
    entry_point_changed: bool = False
    same_version_digest_changed: bool = False


@dataclass(frozen=True, slots=True)
class InstalledPluginSnapshot:
    plugin_id: str
    version: str
    digest: str
    files: tuple[tuple[str, str, int], ...]
    manifest: PluginManifest

    @classmethod
    def from_inspection(cls, inspection: PackageInspection):
        manifest = inspection.manifest
        if not inspection.ok or manifest is None:
            raise ValueError("Installed package inspection must be valid.")
        return cls(
            manifest.plugin_id, manifest.version, inspection.package_digest,
            inspection.files, manifest,
        )


@dataclass(frozen=True, slots=True)
class PluginWorkbenchSnapshot:
    source_name: str
    source_kind: SourceKind
    status: WorkbenchStatus
    package_digest: str
    files: tuple[PluginWorkbenchFile, ...]
    findings: tuple[PluginWorkbenchFinding, ...]
    manifest: PluginManifest | None = None
    raw_manifest: Mapping[str, object] = field(default_factory=dict)
    comparison: PluginWorkbenchComparison | None = None
    observed_api_methods: tuple[str, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "raw_manifest", dict(self.raw_manifest))

    @property
    def counts(self):
        return {
            severity.value: sum(f.severity is severity for f in self.findings)
            for severity in FindingSeverity
        }


@dataclass(frozen=True, slots=True)
class PublicSDKIndex:
    modules: Mapping[str, tuple[str, ...]]
    plugin_api_methods: tuple[str, ...]
    method_capabilities: Mapping[str, str]

    def __post_init__(self):
        object.__setattr__(self, "modules", dict(self.modules))
        object.__setattr__(self, "method_capabilities", dict(self.method_capabilities))

    @classmethod
    def current(cls):
        modules = {
            "app.plugins": tuple(sorted({
                "PLUGIN_API_VERSION","SUPPORTED_PLUGIN_API_VERSIONS",
                "PLUGIN_NAVIGATION_DESTINATIONS","PluginAPI","PluginContext",
                "PluginResult","PluginPanelSpec","PluginView",
                "PluginActionClassification","PluginActionRequest",
                "PluginActionResult","PluginActionSpec","PluginConfirmationSpec",
                "PluginContextBinding","PluginFieldSpec","PluginFieldType",
                "PluginFormSpec","PluginNavigationSpec","PluginOptionSpec",
                "PluginProgressUpdate","PluginRefreshBehavior",
            })),
            "app.plugins.plugin_api": tuple(
                sorted({"PluginAPI", "PluginContext", "PluginResult", "PLUGIN_API_VERSION"})
            ),
            "app.plugins.contribution_registry": ("Contribution",),
            "app.plugins.plugin_ui": tuple(sorted({
                "AddonCardSpec", "AddonCatalogAction", "AddonUIMode",
                "AddonWindowSpec", "PluginPanelSpec", "PluginView",
                "empty_views", "resolve_ui_mode",
            })),
            "app.plugins.plugin_interactive": tuple(sorted({
                "PLUGIN_NAVIGATION_DESTINATIONS","PluginActionClassification",
                "PluginActionRequest","PluginActionResult","PluginActionSpec",
                "PluginConfirmationSpec","PluginContextBinding","PluginFieldSpec",
                "PluginFieldType","PluginFormSpec","PluginNavigationSpec",
                "PluginOptionSpec","PluginProgressUpdate","PluginRefreshBehavior",
            })),
        }
        methods = tuple(
            sorted(
                name for name, value in PluginAPI.__dict__.items()
                if callable(value) and not name.startswith("_")
            )
        )
        method_capabilities = {
            "run_adb_readonly": "run-adb-readonly",
            "append_timeline": "append-timeline",
            "create_evidence": "create-evidence",
            "create_finding": "create-findings",
            "read_state": "read-local-plugin-files",
            "write_state": "write-plugin-state",
        }
        return cls(modules, methods, method_capabilities)


class _DuplicateManifestKey(ValueError):
    pass


def _manifest_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateManifestKey(f"Duplicate manifest field: {key}")
        result[key] = value
    return result


def _finding(rule, severity, category, title, explanation, remediation, path="", node=None):
    return PluginWorkbenchFinding(
        rule, FindingSeverity(severity), category, title, explanation,
        remediation, path, getattr(node, "lineno", 0), getattr(node, "col_offset", 0),
    )


def _safe_relative(name: str) -> str:
    if "\\" in name:
        raise ValueError("Backslash archive paths are not portable and are rejected.")
    path = PurePosixPath(name)
    if not name or path.is_absolute() or ".." in path.parts:
        raise ValueError("Package path traversal or absolute path was rejected.")
    if any(
        part.rstrip(" .").split(".", 1)[0].upper() in WINDOWS_RESERVED
        for part in path.parts
    ):
        raise ValueError("Windows reserved package filename was rejected.")
    return path.as_posix()


class PluginWorkbenchAnalyzer:
    """Reads bytes and AST only; candidate code is never imported or invoked."""

    MAX_FILES = PluginPackage.MAX_FILES
    MAX_TOTAL = PluginPackage.MAX_TOTAL
    MAX_FILE = PluginPackage.MAX_FILE
    MAX_TEXT = 2 * 1024 * 1024
    MAX_RATIO = 100

    def __init__(
        self, *, sdk_index=None, installed: Mapping[str, InstalledPluginSnapshot] = (),
        official_identities: Mapping[str, bool] = (),
        host_version="1.0.0-rc.4", cancelled: Callable[[], bool] = lambda: False,
    ):
        self.sdk = sdk_index or PublicSDKIndex.current()
        self.installed = dict(installed)
        self.official_identities = dict(official_identities)
        self.host_version = host_version
        self.cancelled = cancelled
        self.validator = PluginValidator()

    def analyze(self, source: PluginWorkbenchSource | str | Path):
        source = (
            source if isinstance(source, PluginWorkbenchSource)
            else PluginWorkbenchSource.selected(source)
        )
        findings = []
        try:
            content = self._read_directory(source.path) if source.kind is SourceKind.DIRECTORY else self._read_zip(source.path)
        except RuntimeError:
            raise
        except (OSError, ValueError, zipfile.BadZipFile) as exc:
            findings.append(_finding(
                "PKG001", "error", "Package", "Package structure is blocked",
                str(exc), "Correct the package structure and analyze it again.",
            ))
            return self._snapshot(source, {}, findings)
        findings.extend(self._hygiene(content))
        manifest_data = {}
        manifest = None
        manifest_bytes = content.get("manifest.json")
        if manifest_bytes is None:
            nested = tuple(name for name in content if name.endswith("/manifest.json"))
            findings.append(_finding(
                "MAN001", "error", "Manifest",
                "Root manifest is missing",
                "The package requires one root-level manifest.json."
                + (f" A nested manifest exists at {nested[0]}." if nested else ""),
                "Move manifest.json to the package root.",
            ))
        else:
            try:
                manifest_data = json.loads(
                    manifest_bytes.decode("utf-8"), object_pairs_hook=_manifest_pairs
                )
                if not isinstance(manifest_data, dict):
                    raise ValueError("Manifest root must be a JSON object.")
                findings.extend(self._manifest_findings(manifest_data, content))
                manifest = PluginManifest.from_dict(manifest_data)
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError) as exc:
                findings.append(_finding(
                    "MAN002", "error", "Manifest", "Manifest is invalid",
                    str(exc), "Use valid UTF-8 JSON and the documented manifest schema.",
                    "manifest.json",
                ))
        inspection = None
        if manifest is not None and not any(
            f.severity is FindingSeverity.ERROR and f.category == "Package"
            for f in findings
        ):
            inspection = PluginPackage.inspect(source.path)
            validation = self.validator.validate(
                inspection, root=source.path if source.kind is SourceKind.DIRECTORY else None
            )
            findings.extend(
                _finding("VAL001", "error", "Compatibility", "Production validation failed", value, "Resolve this production validator error.")
                for value in validation.errors
            )
            findings.extend(
                _finding("VAL002", "warning", "Package", "Production validation warning", value, "Review before packaging.")
                for value in validation.warnings
            )
        observed = set()
        factories = set()
        for path, data in sorted(content.items()):
            if self.cancelled():
                raise RuntimeError("Plugin analysis cancelled.")
            if path.casefold().endswith(".py"):
                source_text = self._decode_text(path, data, findings)
                if source_text is not None:
                    ast_findings, names, methods = self._analyze_python(path, source_text)
                    findings.extend(ast_findings)
                    factories.update(names)
                    observed.update(methods)
            if (
                Path(path).suffix.casefold() in TEXT_SUFFIXES
                or PurePosixPath(path).name.casefold()
                in {".env", "credentials", "credentials.json"}
            ):
                source_text = self._decode_text(path, data, findings, report_error=False)
                if source_text is not None:
                    findings.extend(self._privacy_findings(path, source_text))
        if manifest is not None:
            findings.extend(self._official_identity_findings(manifest))
            findings.extend(self._factory_findings(manifest, factories))
            findings.extend(self._capability_findings(manifest, observed))
            findings.extend(self._interactive_manifest_findings(manifest, observed))
        comparison = self._comparison(manifest, inspection, content)
        return self._snapshot(
            source, content, findings, manifest, manifest_data,
            inspection.package_digest if inspection and inspection.ok else "",
            comparison, tuple(sorted(observed)),
        )

    def _check_cancel(self):
        if self.cancelled():
            raise RuntimeError("Plugin analysis cancelled.")

    def _read_directory(self, root: Path):
        content = {}
        folded = set()
        total = 0

        def visit(directory: Path, prefix=PurePosixPath()):
            nonlocal total
            self._check_cancel()
            with __import__("os").scandir(directory) as entries:
                for entry in sorted(entries, key=lambda item: item.name.casefold()):
                    self._check_cancel()
                    rel = _safe_relative((prefix / entry.name).as_posix())
                    key = rel.casefold()
                    if key in folded:
                        raise ValueError(f"Case-colliding directory entry rejected: {rel}")
                    folded.add(key)
                    if entry.is_symlink():
                        raise ValueError(f"Symlinked package entry rejected: {rel}")
                    if entry.is_dir(follow_symlinks=False):
                        visit(Path(entry.path), prefix / entry.name)
                    elif entry.is_file(follow_symlinks=False):
                        size = entry.stat(follow_symlinks=False).st_size
                        if size > self.MAX_FILE:
                            raise ValueError(f"Package file exceeds the size limit: {rel}")
                        total += size
                        if len(content) + 1 > self.MAX_FILES or total > self.MAX_TOTAL:
                            raise ValueError("Plugin package exceeds bounded file or byte limits.")
                        content[rel] = Path(entry.path).read_bytes()
                    else:
                        raise ValueError(f"Unsupported special package entry: {rel}")
            return content

        return visit(root)

    def _read_zip(self, path: Path):
        content = {}
        folded = set()
        total = 0
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist():
                self._check_cancel()
                name = _safe_relative(info.filename)
                if stat.S_IFMT(info.external_attr >> 16) == stat.S_IFLNK:
                    raise ValueError(f"Symlink ZIP entry rejected: {name}")
                if info.is_dir():
                    continue
                key = name.casefold()
                if name in content:
                    raise ValueError(f"Duplicate ZIP entry rejected: {name}")
                if key in folded:
                    raise ValueError(f"Case-colliding ZIP entry rejected: {name}")
                folded.add(key)
                if info.flag_bits & 0x1:
                    raise ValueError(f"Encrypted ZIP entry rejected: {name}")
                if info.file_size > self.MAX_FILE:
                    raise ValueError(f"ZIP entry exceeds the size limit: {name}")
                if info.file_size / max(1, info.compress_size) > self.MAX_RATIO:
                    raise ValueError(f"Suspicious ZIP compression ratio rejected: {name}")
                total += info.file_size
                if len(content) + 1 > self.MAX_FILES or total > self.MAX_TOTAL:
                    raise ValueError("ZIP exceeds bounded file or total byte limits.")
                content[name] = archive.read(info)
        return content

    def _manifest_findings(self, data, content):
        findings = []
        allowed = set(PluginManifest.__dataclass_fields__)
        unknown = sorted(set(data) - allowed)
        if unknown:
            findings.append(_finding(
                "MAN003", "error", "Manifest", "Unsupported manifest fields",
                "Unsupported fields: " + ", ".join(unknown),
                "Remove fields not defined by the Plugin SDK manifest.",
                "manifest.json",
            ))
        capabilities = tuple(data.get("requested_capabilities", ()))
        if len(capabilities) != len(set(capabilities)):
            findings.append(_finding(
                "CAP001", "warning", "Capabilities", "Duplicate capabilities",
                "The requested capability list contains duplicates.",
                "List each requested capability once.", "manifest.json",
            ))
        components = data.get("contributed_components", ())
        identifiers = [
            value.get("contribution_id", "") for value in components
            if isinstance(value, dict)
        ]
        if len(identifiers) != len(set(identifiers)):
            findings.append(_finding(
                "CON001", "error", "Contributions", "Duplicate contribution ID",
                "Contribution IDs must be stable and unique.",
                "Give every contribution a unique ID.", "manifest.json",
            ))
        addon = data.get("addon_ui", {})
        mode = addon.get("ui_mode") if isinstance(addon, dict) else None
        if mode is not None and mode not in {"embedded", "window", "hybrid"}:
            findings.append(_finding(
                "CON002", "error", "Contributions", "Invalid UI mode",
                f"The declared UI mode {mode!r} is not supported.",
                "Use embedded, window, or hybrid.", "manifest.json",
            ))
        for key in ("default_width", "minimum_width"):
            if key in addon and (
                not isinstance(addon[key], int) or not 400 <= addon[key] <= 2400
            ):
                findings.append(_finding(
                    "CON004", "error", "Contributions", "Invalid window width",
                    f"{key} must be an integer from 400 through 2400.",
                    "Use a bounded host-owned window geometry.", "manifest.json",
                ))
        for key in ("default_height", "minimum_height"):
            if key in addon and (
                not isinstance(addon[key], int) or not 300 <= addon[key] <= 1600
            ):
                findings.append(_finding(
                    "CON005", "error", "Contributions", "Invalid window height",
                    f"{key} must be an integer from 300 through 1600.",
                    "Use a bounded host-owned window geometry.", "manifest.json",
                ))
        minimum = data.get("minimum_sus_adb_version", "0.1.0")
        if self._version_tuple(str(minimum)) > self._version_tuple(self.host_version):
            findings.append(_finding(
                "COMP001", "error", "Compatibility", "Host version is too old",
                f"The candidate requires SUS Companion {minimum} or newer.",
                "Use a compatible host or lower the requirement only when accurate.",
                "manifest.json",
            ))
        if not data.get("contributed_components"):
            findings.append(_finding(
                "CON006", "information", "Contributions",
                "No contributions are declared",
                "The package declares no host-visible contribution.",
                "Declare a supported contribution if the addon should appear in the host.",
                "manifest.json",
            ))
        return findings

    @staticmethod
    def _version_tuple(value):
        match = re.match(r"^(\d+)\.(\d+)\.(\d+)", value)
        return tuple(map(int, match.groups())) if match else (10**9, 0, 0)

    def _decode_text(self, path, data, findings, report_error=True):
        if len(data) > self.MAX_TEXT:
            if report_error:
                findings.append(_finding(
                    "FILE001", "warning", "Files", "Text file was not parsed",
                    "The text file exceeds the static parsing limit.",
                    "Reduce or split the file.", path,
                ))
            return None
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            if report_error:
                findings.append(_finding(
                    "FILE002", "error", "Python Syntax", "Python is not UTF-8",
                    "Python source must decode as UTF-8.",
                    "Save the source as UTF-8.", path,
                ))
            return None

    def _analyze_python(self, path, text):
        findings = []
        observed = set()
        try:
            tree = ast.parse(text, filename=path)
            compile(tree, path, "exec", dont_inherit=True)
        except SyntaxError as exc:
            findings.append(PluginWorkbenchFinding(
                "PY001", FindingSeverity.ERROR, "Python Syntax", "Syntax error",
                exc.msg, "Correct the syntax error.", path,
                exc.lineno or 0, exc.offset or 0,
            ))
            return findings, set(), observed
        definitions = {
            node.name for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        }
        function_args = {
            node.name: len(node.args.args)
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        interactive=("PluginFieldSpec","PluginFormSpec","PluginActionSpec","PluginConfirmationSpec","PluginActionRequest","PluginActionResult","PluginNavigationSpec","PluginProgressUpdate")
        calls=[node for node in ast.walk(tree) if isinstance(node,ast.Call)]
        for model in interactive:
            model_calls=[node for node in calls if self._call_name(node.func).split(".")[-1]==model]
            if model_calls:observed.add(f"sdk-symbol:{model}")
            if model in {"PluginFieldSpec","PluginActionSpec"}:
                ids=[node.args[0].value for node in model_calls if node.args and isinstance(node.args[0],ast.Constant) and isinstance(node.args[0].value,str)]
                if len(ids)!=len(set(ids)):
                    findings.append(_finding("SDK111","error","Interactive SDK",f"Duplicate {model.removeprefix('Plugin').removesuffix('Spec').lower()} ID","Interactive IDs must be stable and unique within their container.","Choose unique field and action IDs.",path,model_calls[0]))
        for node in calls:
            name=self._call_name(node.func).split(".")[-1]
            if name=="PluginNavigationSpec" and node.args and isinstance(node.args[0],ast.Constant):
                from app.plugins.plugin_interactive import PLUGIN_NAVIGATION_DESTINATIONS
                if node.args[0].value not in PLUGIN_NAVIGATION_DESTINATIONS:findings.append(_finding("SDK112","error","Interactive SDK","Unknown navigation destination","The navigation destination is not host-owned.","Use a documented safe navigation destination.",path,node))
            if name=="PluginActionSpec":
                keywords={value.arg:value.value for value in node.keywords}
                classification=keywords.get("classification")
                state_changing=isinstance(classification,ast.Constant) and classification.value=="state_changing" or isinstance(classification,ast.Attribute) and classification.attr=="STATE_CHANGING"
                if state_changing and "confirmation" not in keywords:findings.append(_finding("SDK113","error","Interactive SDK","State-changing action has no confirmation","State-changing actions require a host-owned confirmation.","Declare PluginConfirmationSpec on the action.",path,node))
                capabilities=keywords.get("required_capabilities")
                if isinstance(capabilities,(ast.Tuple,ast.List)):
                    from app.plugins.plugin_capabilities import CAPABILITIES
                    unknown=sorted(value.value for value in capabilities.elts if isinstance(value,ast.Constant) and isinstance(value.value,str) and value.value not in CAPABILITIES)
                    if unknown:findings.append(_finding("SDK114","error","Interactive SDK","Unknown action capability","Unknown capabilities: "+", ".join(unknown),"Use only documented capability names.",path,node))
                callback=node.args[2] if len(node.args)>2 else keywords.get("callback")
                if isinstance(callback,ast.Name) and (callback.id not in definitions or function_args.get(callback.id,1)!=1):findings.append(_finding("SDK115","error","Interactive SDK","Action callback is missing or incompatible","Action callbacks must resolve to a function accepting one immutable request.","Define callback(request).",path,node))
            if name=="PluginFieldSpec":
                keywords={value.arg:value.value for value in node.keywords}
                field_type=node.args[2] if len(node.args)>2 else keywords.get("field_type")
                if isinstance(field_type,ast.Constant) and field_type.value not in {"text","password","multiline","checkbox","choice","integer","read_only"}:findings.append(_finding("SDK118","error","Interactive SDK","Unsupported field type",f"{field_type.value!r} is not a host-rendered field type.","Use a documented PluginFieldType.",path,node))
                sensitive=keywords.get("sensitive");default=keywords.get("default")
                if isinstance(sensitive,ast.Constant) and sensitive.value is True and isinstance(default,ast.Constant) and default.value not in (None,""):findings.append(_finding("SDK116","error","Secrets","Sensitive default literal","A sensitive field contains a source-code default literal.","Remove the sensitive default and collect it at runtime.",path,node))
                minimum=keywords.get("minimum");maximum=keywords.get("maximum")
                if isinstance(minimum,ast.Constant) and isinstance(maximum,ast.Constant) and isinstance(minimum.value,int) and isinstance(maximum.value,int) and minimum.value>maximum.value:findings.append(_finding("SDK117","error","Interactive SDK","Invalid field bounds","Field minimum exceeds maximum.","Correct the bounded field range.",path,node))
        imported = {}
        api_names = {"api", "plugin_api"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported[alias.asname or alias.name.split(".")[0]] = alias.name
                    findings.extend(self._import_findings(path, alias.name, (), node))
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                names = tuple(alias.name for alias in node.names)
                findings.extend(self._import_findings(path, module, names, node))
                for alias in node.names:
                    imported[alias.asname or alias.name] = f"{module}.{alias.name}"
            elif isinstance(node, ast.Attribute):
                if node.attr == "success":
                    findings.append(_finding(
                        "SDK003", "error", "Public SDK",
                        "PluginResult has no success property",
                        "The public result property is ok, not success.",
                        "Use result.ok.", path, node,
                    ))
                if isinstance(node.value, ast.Name) and node.value.id in api_names:
                    observed.add(node.attr)
                    if node.attr not in self.sdk.plugin_api_methods:
                        findings.append(_finding(
                            "SDK002", "error", "Public SDK",
                            "Unknown PluginAPI method",
                            f"PluginAPI.{node.attr} is not part of Plugin API v1.",
                            "Use a documented capability-gated PluginAPI method.",
                            path, node,
                        ))
            elif isinstance(node, ast.Call):
                findings.extend(self._call_findings(path, node, imported))
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == "activate" and len(node.args.args) < 2:
                    findings.append(_finding(
                        "SDK004", "error", "Public SDK",
                        "Incompatible activate signature",
                        "activate must accept the plugin instance and PluginAPI façade.",
                        "Use activate(self, api).", path, node,
                    ))
                operational = node.name in {
                    "activate", "deactivate", "load", "start", "register",
                    "panel_spec", "report_section",
                }
                if operational and self._placeholder(node):
                    findings.append(_finding(
                        "DOC002", "warning", "Documentation",
                        "Operational body appears to be a placeholder",
                        "The declared operational function has only placeholder behavior.",
                        "Implement or remove the unfinished declaration.", path, node,
                    ))
                for handler in (
                    child for child in ast.walk(node)
                    if isinstance(child, ast.ExceptHandler)
                    and child.type is None
                    and all(isinstance(statement, ast.Pass) for statement in child.body)
                ):
                    findings.append(_finding(
                        "PY002", "warning", "Python Syntax",
                        "Lifecycle exception is broadly swallowed",
                        "A bare exception handler silently discards failures.",
                        "Catch expected exceptions narrowly and report bounded failures.",
                        path, handler,
                    ))
        for number, line in enumerate(text.splitlines(), 1):
            if re.search(r"\b(TODO|FIXME)\b", line):
                findings.append(PluginWorkbenchFinding(
                    "DOC001", FindingSeverity.INFORMATION, "Documentation",
                    "Unresolved development note",
                    "Operational source contains an unfinished development marker.",
                    "Review TODO/FIXME notes before packaging.", path, number, 0,
                ))
        return findings, definitions, observed

    @staticmethod
    def _interactive_manifest_findings(manifest,observed):
        symbols=sorted(value.split(":",1)[1] for value in observed if value.startswith("sdk-symbol:"))
        if not symbols:return ()
        if manifest.plugin_api_version=="1.0":
            return (_finding("SDK110","error","Interactive SDK","Plugin API 1.1 symbols used under a 1.0 manifest","The candidate uses: "+", ".join(symbols),"Declare Plugin API 1.1 or remove the v1.1 contracts.","manifest.json"),)
        if manifest.plugin_api_version=="1.1":
            return (_finding("SDK100","information","Interactive SDK","Plugin API 1.1 interactive contract detected","The candidate uses host-owned immutable interactive specifications.","Review forms, actions, capabilities, confirmations, and cleanup.","manifest.json"),)
        return ()

    def _import_findings(self, path, module, names, node):
        findings = []
        if module.startswith(("app.core", "app.gui")) or (
            module.startswith("app.plugins.")
            and module not in self.sdk.modules
        ):
            findings.append(_finding(
                "SDK001", "error", "Public SDK", "Private host import",
                f"{module} is outside the public Plugin SDK.",
                "Use documented app.plugins SDK surfaces.", path, node,
            ))
        if module in self.sdk.modules:
            missing = sorted(set(names) - set(self.sdk.modules[module]))
            if missing:
                findings.append(_finding(
                    "SDK005", "error", "Public SDK", "Unknown public SDK symbol",
                    "Unknown symbols: " + ", ".join(missing),
                    "Import only documented public SDK symbols.", path, node,
                ))
        root = module.split(".", 1)[0]
        category = {
            "subprocess": ("POL001", "error", "direct subprocess access"),
            "socket": ("POL004", "error", "direct network access"),
            "requests": ("POL004", "error", "direct network access"),
            "urllib": ("POL004", "error", "direct network access"),
            "http": ("POL004", "error", "direct network access"),
            "ctypes": ("POL005", "error", "native-library access"),
            "cffi": ("POL005", "error", "native-library access"),
            "importlib": ("POL003", "error", "dynamic import loading"),
        }.get(root)
        if category:
            rule, severity, title = category
            findings.append(_finding(
                rule, severity, "Imports", title.title(),
                f"The candidate imports {module}.",
                "Use a capability-gated host façade or remove the import.", path, node,
            ))
        return findings

    def _call_findings(self, path, node, imported):
        findings = []
        name = self._call_name(node.func)
        if name in {"eval", "exec", "__import__"}:
            findings.append(_finding(
                "POL003", "error", "Imports", "Dynamic execution",
                f"{name} can execute or load code dynamically.",
                "Remove dynamic execution.", path, node,
            ))
        if name in {"tkinter.Tk", "tkinter.Toplevel", "customtkinter.CTk", "customtkinter.CTkToplevel", "Tk", "CTk"}:
            findings.append(_finding(
                "GUI001", "error", "Contributions", "Plugin-owned Tk root",
                "The host must own plugin windows and Tk roots.",
                "Return immutable UI specifications instead.", path, node,
            ))
        if name.endswith(("subprocess.run", "subprocess.Popen", "os.system", "os.popen")):
            findings.append(_finding(
                "POL001", "error", "Imports", "Direct process execution",
                "Candidate code directly starts a host process.",
                "Use an approved host façade.", path, node,
            ))
        if any(
            keyword.arg == "shell"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value is True
            for keyword in node.keywords
        ):
            findings.append(_finding(
                "POL002", "error", "Imports", "Shell execution requested",
                "shell=True is prohibited.", "Remove shell execution.", path, node,
            ))
        if name.endswith(("Path.read_text", "Path.read_bytes", "Path.write_text", "Path.write_bytes", "open")):
            findings.append(_finding(
                "POL006", "warning", "Files", "Direct filesystem access",
                "The candidate appears to access files directly.",
                "Use approved plugin state or declared asset façades.", path, node,
            ))
        if name.endswith(("os.getenv", "os.environ.get")):
            findings.append(_finding(
                "SEC006", "warning", "Secrets", "Environment access",
                "Candidate code reads process environment state.",
                "Use explicit host-approved configuration without credential access.",
                path, node,
            ))
        if isinstance(node.func, ast.Name) and node.func.id in {"NotImplementedError"}:
            findings.append(_finding(
                "DOC002", "warning", "Documentation", "Placeholder operation",
                "NotImplementedError indicates unfinished operational code.",
                "Complete or remove the operation.", path, node,
            ))
        return findings

    @staticmethod
    def _call_name(node):
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            prefix = PluginWorkbenchAnalyzer._call_name(node.value)
            return f"{prefix}.{node.attr}" if prefix else node.attr
        return ""

    @staticmethod
    def _placeholder(node):
        body = [
            value for value in node.body
            if not (
                isinstance(value, ast.Expr)
                and isinstance(value.value, ast.Constant)
                and isinstance(value.value.value, str)
            )
        ]
        return bool(body) and all(
            isinstance(value, ast.Pass)
            or isinstance(value, ast.Raise)
            and isinstance(value.exc, ast.Call)
            and isinstance(value.exc.func, ast.Name)
            and value.exc.func.id == "NotImplementedError"
            or isinstance(value, ast.Return)
            and (
                value.value is None
                or isinstance(value.value, ast.Constant)
                and value.value.value in (None, (), "")
            )
            for value in body
        )

    def _factory_findings(self, manifest, factories):
        findings = []
        entry_factory = (
            manifest.entry_point.split(":", 1)[1]
            if ":" in manifest.entry_point else "Plugin"
        )
        if entry_factory not in factories:
            findings.append(_finding(
                "SDK006", "error", "Public SDK", "Entry-point factory is missing",
                f"The declared entry-point object {entry_factory!r} was not found.",
                "Define the declared class or function.",
                manifest.entry_point.split(":", 1)[0],
            ))
        for contribution in manifest.contributed_components:
            if contribution.factory and contribution.factory not in factories:
                findings.append(_finding(
                    "CON003", "error", "Contributions",
                    "Contribution factory is missing",
                    f"{contribution.contribution_id} declares {contribution.factory!r}.",
                    "Define the declared contribution factory.",
                    manifest.entry_point.split(":", 1)[0],
                ))
        return findings

    def _official_identity_findings(self, manifest):
        if manifest.plugin_id not in self.official_identities:
            return ()
        template = self.official_identities[manifest.plugin_id]
        explanation = (
            "Valid educational template structure does not make this candidate "
            "installable unchanged as a third-party derivative because its "
            "official plugin ID is reserved."
            if template else
            "This local third-party candidate uses a plugin ID reserved by the "
            "bundled official addon catalog, so production installation will reject it."
        )
        remediation = "Choose a new stable plugin ID before installation."
        if template:
            remediation += (
                " Change contribution IDs to unique derivative-owned IDs and keep "
                "them synchronized between the manifest and Python registration."
            )
        return (_finding(
            "COMP002", "error", "Compatibility",
            "Official plugin ID is reserved",
            explanation, remediation, "manifest.json",
        ),)

    def _capability_findings(self, manifest, observed):
        findings = []
        requested = set(manifest.requested_capabilities)
        suggested = {
            self.sdk.method_capabilities[method]
            for method in observed if method in self.sdk.method_capabilities
        }
        for capability in sorted(suggested - requested):
            findings.append(_finding(
                "CAP002", "error", "Capabilities", "Capability is undeclared",
                f"Observed API use suggests {capability}, but it is not requested.",
                "Declare and document the capability or remove the API use.",
            ))
        for capability in sorted(requested - suggested):
            findings.append(_finding(
                "CAP003", "information", "Capabilities",
                "Requested capability was not observed",
                f"No direct static use of {capability} was found.",
                "Review whether the capability is needed; this is not proof of misuse.",
            ))
        for capability in sorted(requested & HIGH_IMPACT):
            findings.append(_finding(
                "CAP004", "warning", "Capabilities", "High-impact capability",
                f"{capability} requires explicit digest-bound approval and scope.",
                "Explain the operator-reviewed need in plugin documentation.",
            ))
        return findings

    def _privacy_findings(self, path, text):
        findings = []
        unix_home = "/" + "home" + "/"
        patterns = (
            ("SEC001", r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", "Private-key material"),
            ("SEC002", r"\bgh[pousr]_[A-Za-z0-9]{20,}\b", "GitHub-style token"),
            ("SEC003", r"\bAKIA[0-9A-Z]{16}\b", "Cloud access key"),
            ("SEC004", r"(?i)\b(?:password|api[_-]?key|bearer[_-]?token)\s*[:=]\s*['\"][^'\"]{6,}", "Credential literal"),
            (
                "SEC005",
                r"(?:(?:[A-Za-z]:\\Users\\)|"
                + re.escape(unix_home)
                + r"|/Users/)[^\s'\"]+",
                "Local developer path",
            ),
        )
        if PurePosixPath(path).name.casefold() in {".env", "credentials", "credentials.json"}:
            findings.append(_finding(
                "SEC000", "error", "Secrets", "Credential file",
                "A credential-oriented file is present.",
                "Remove it from the candidate and rotate exposed credentials.", path,
            ))
        for number, line in enumerate(text.splitlines(), 1):
            for rule, pattern, title in patterns:
                if re.search(pattern, line):
                    findings.append(PluginWorkbenchFinding(
                        rule, FindingSeverity.ERROR, "Secrets", title,
                        "A high-confidence private value or local path indicator was detected; its value is redacted.",
                        "Remove the value, rotate it where applicable, and use host-approved configuration.",
                        path, number, 0,
                    ))
        return findings

    def _hygiene(self, content):
        findings = []
        for path in sorted(content):
            parts = PurePosixPath(path).parts
            suffix = Path(path).suffix.casefold()
            reason = ""
            if any(part.casefold() in CLUTTER_PARTS for part in parts):
                reason = "development directory"
            elif suffix in CLUTTER_SUFFIXES or Path(path).name in {".DS_Store", "Thumbs.db"}:
                reason = "generated or local file"
            if reason:
                findings.append(_finding(
                    "PKG002", "warning", "Packaging",
                    "Development clutter will be excluded",
                    f"{path} is classified as {reason}.",
                    "Keep it in the project if useful; it will not enter a built ZIP.",
                    path,
                ))
        return findings

    def _comparison(self, manifest, inspection, content):
        if manifest is None or manifest.plugin_id not in self.installed:
            return None
        installed = self.installed[manifest.plugin_id]
        candidate_files = {
            path: hashlib.sha256(data).hexdigest() for path, data in content.items()
        }
        old_files = {path: digest for path, digest, _size in installed.files}
        old_contrib = {
            item.contribution_id: item.to_dict()
            for item in installed.manifest.contributed_components
        }
        new_contrib = {
            item.contribution_id: item.to_dict()
            for item in manifest.contributed_components
        }
        shared = set(old_contrib) & set(new_contrib)
        candidate_digest = inspection.package_digest if inspection and inspection.ok else ""
        return PluginWorkbenchComparison(
            installed.version, manifest.version, installed.digest, candidate_digest,
            tuple(sorted(set(candidate_files) - set(old_files))),
            tuple(sorted(set(old_files) - set(candidate_files))),
            tuple(sorted(
                path for path in set(old_files) & set(candidate_files)
                if old_files[path] != candidate_files[path]
            )),
            tuple(sorted(set(manifest.requested_capabilities) - set(installed.manifest.requested_capabilities))),
            tuple(sorted(set(installed.manifest.requested_capabilities) - set(manifest.requested_capabilities))),
            tuple(sorted(set(new_contrib) - set(old_contrib))),
            tuple(sorted(set(old_contrib) - set(new_contrib))),
            tuple(sorted(key for key in shared if old_contrib[key] != new_contrib[key])),
            installed.manifest.entry_point != manifest.entry_point,
            installed.version == manifest.version and installed.digest != candidate_digest,
        )

    def _snapshot(
        self, source, content, findings, manifest=None, raw_manifest=(),
        digest="", comparison=None, observed=(),
    ):
        ordered = tuple(sorted(
            dict.fromkeys(findings),
            key=lambda item: (
                {FindingSeverity.ERROR: 0, FindingSeverity.WARNING: 1, FindingSeverity.INFORMATION: 2}[item.severity],
                item.category.casefold(), item.rule_id, item.path, item.line, item.column,
            ),
        ))
        status = (
            WorkbenchStatus.BLOCKED
            if any(item.severity is FindingSeverity.ERROR for item in ordered)
            else WorkbenchStatus.NEEDS_REVIEW
            if any(item.severity is FindingSeverity.WARNING for item in ordered)
            else WorkbenchStatus.COMPATIBLE
        )
        files = tuple(
            PluginWorkbenchFile(
                path, hashlib.sha256(data).hexdigest(), len(data),
                self._excluded_reason(path),
            )
            for path, data in sorted(content.items())
        )
        return PluginWorkbenchSnapshot(
            source.display_name, source.kind, status, digest, files, ordered,
            manifest, raw_manifest, comparison, observed,
        )

    @staticmethod
    def _excluded_reason(path):
        parts = tuple(part.casefold() for part in PurePosixPath(path).parts)
        if any(part in CLUTTER_PARTS for part in parts):
            return "development clutter"
        if Path(path).suffix.casefold() in CLUTTER_SUFFIXES:
            return "generated or local file"
        return ""
