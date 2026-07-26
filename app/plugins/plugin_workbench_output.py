"""Deterministic reports and package output for static workbench snapshots."""
from __future__ import annotations

import json
import os
import tempfile
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path

from app.core.app_metadata import METADATA
from app.plugins.plugin_package import PluginPackage
from app.plugins.plugin_validator import PluginValidator
from app.plugins.plugin_workbench import (
    FindingSeverity,
    PluginWorkbenchAnalyzer,
    PluginWorkbenchSnapshot,
    PluginWorkbenchSource,
    SourceKind,
    STATIC_LIMITATION,
)


@dataclass(frozen=True, slots=True)
class PluginWorkbenchPackagePlan:
    allowed: bool
    included: tuple[str, ...]
    excluded: tuple[tuple[str, str], ...]
    total_bytes: int
    plugin_id: str = ""
    version: str = ""
    reason: str = ""


@dataclass(frozen=True, slots=True)
class WorkbenchWriteResult:
    ok: bool
    path: str = ""
    digest: str = ""
    error: str = ""


def report_data(snapshot: PluginWorkbenchSnapshot):
    manifest = snapshot.manifest
    comparison = asdict(snapshot.comparison) if snapshot.comparison else None
    return {
        "candidate": {
            "name": snapshot.source_name,
            "source_type": snapshot.source_kind.value,
            "digest": snapshot.package_digest,
            "status": snapshot.status.value,
            "file_count": len(snapshot.files),
            "total_bytes": sum(item.size for item in snapshot.files),
        },
        "host": {
            "application": METADATA.application_name,
            "version": METADATA.version,
            "plugin_api": "1.0",
        },
        "manifest": (
            {
                "plugin_id": manifest.plugin_id,
                "name": manifest.name,
                "version": manifest.version,
                "plugin_api_version": manifest.plugin_api_version,
                "entry_point": manifest.entry_point,
            } if manifest else None
        ),
        "capabilities": list(manifest.requested_capabilities) if manifest else [],
        "contributions": [
            {
                "id": item.contribution_id,
                "type": item.contribution_type,
                "title": item.title,
                "factory": item.factory,
            }
            for item in (manifest.contributed_components if manifest else ())
        ],
        "findings": [
            {
                "rule_id": item.rule_id,
                "severity": item.severity.value,
                "category": item.category,
                "title": item.title,
                "explanation": item.explanation,
                "remediation": item.remediation,
                "path": item.path,
                "line": item.line,
                "column": item.column,
            }
            for item in snapshot.findings
        ],
        "comparison": comparison,
        "package_plan": {
            "included": [item.path for item in snapshot.files if not item.excluded_reason],
            "excluded": [
                {"path": item.path, "reason": item.excluded_reason}
                for item in snapshot.files if item.excluded_reason
            ],
        },
        "limitation": STATIC_LIMITATION,
    }


def render_json_report(snapshot):
    return json.dumps(report_data(snapshot), indent=2, sort_keys=True) + "\n"


def render_markdown_report(snapshot):
    data = report_data(snapshot)
    candidate = data["candidate"]
    manifest = data["manifest"]
    lines = [
        "# SUS Companion Plugin Workbench Report",
        "",
        f"- Candidate: {candidate['name']}",
        f"- Source type: {candidate['source_type']}",
        f"- Static status: {candidate['status']}",
        f"- Package digest: `{candidate['digest'] or 'unavailable'}`",
        f"- Files: {candidate['file_count']}",
        f"- Bytes: {candidate['total_bytes']}",
        f"- Host: {data['host']['application']} {data['host']['version']}",
        f"- Plugin API: {data['host']['plugin_api']}",
        "",
        "## Manifest",
        "",
    ]
    if manifest:
        lines.extend(
            f"- {key.replace('_', ' ').title()}: {value}"
            for key, value in manifest.items()
        )
    else:
        lines.append("- No valid manifest")
    lines.extend(("", "## Findings", ""))
    if data["findings"]:
        for finding in data["findings"]:
            location = finding["path"]
            if location and finding["line"]:
                location += f":{finding['line']}"
            lines.extend((
                f"### {finding['severity'].upper()} · {finding['title']}",
                "",
                f"`{finding['rule_id']}` · {finding['category']}"
                + (f" · `{location}`" if location else ""),
                "",
                finding["explanation"],
                "",
                f"Remediation: {finding['remediation']}",
                "",
            ))
    else:
        lines.extend(("No static findings.", ""))
    lines.extend(("## Limitation", "", STATIC_LIMITATION, ""))
    return "\n".join(lines)


def atomic_write_report(path, content, *, overwrite=False):
    destination = Path(path).expanduser().resolve()
    if destination.exists() and not overwrite:
        return WorkbenchWriteResult(False, error="Overwrite confirmation is required.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(destination)
        return WorkbenchWriteResult(True, str(destination))
    except OSError as exc:
        try:
            os.close(descriptor)
        except OSError:
            pass
        return WorkbenchWriteResult(False, error=str(exc))
    finally:
        temporary.unlink(missing_ok=True)


class PluginWorkbenchPackageBuilder:
    def __init__(self):
        self.validator = PluginValidator()

    def plan(self, source: PluginWorkbenchSource, snapshot: PluginWorkbenchSnapshot):
        if source.kind is not SourceKind.DIRECTORY:
            return PluginWorkbenchPackagePlan(
                False, (), (), 0, reason="ZIP building requires a directory candidate."
            )
        blocking = tuple(
            item for item in snapshot.findings
            if item.severity is FindingSeverity.ERROR
            and item.category in {"Package", "Manifest", "Secrets"}
        )
        if blocking or snapshot.manifest is None:
            return PluginWorkbenchPackagePlan(
                False, (), (), 0,
                reason="Resolve blocking package, manifest, path, or secret findings.",
            )
        included = tuple(item.path for item in snapshot.files if not item.excluded_reason)
        excluded = tuple(
            (item.path, item.excluded_reason)
            for item in snapshot.files if item.excluded_reason
        )
        sizes = {item.path: item.size for item in snapshot.files}
        return PluginWorkbenchPackagePlan(
            True, included, excluded, sum(sizes[path] for path in included),
            snapshot.manifest.plugin_id, snapshot.manifest.version,
        )

    def build(self, source, snapshot, destination, *, overwrite=False):
        plan = self.plan(source, snapshot)
        if not plan.allowed:
            return WorkbenchWriteResult(False, error=plan.reason)
        destination = Path(destination).expanduser().resolve()
        if destination.exists() and not overwrite:
            return WorkbenchWriteResult(False, error="Overwrite confirmation is required.")
        destination.parent.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(
            prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
        )
        os.close(descriptor)
        temporary = Path(name)
        try:
            with zipfile.ZipFile(
                temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
            ) as archive:
                for relative in plan.included:
                    data = (source.path / relative).read_bytes()
                    info = zipfile.ZipInfo(relative, (1980, 1, 1, 0, 0, 0))
                    info.compress_type = zipfile.ZIP_DEFLATED
                    info.create_system = 3
                    info.external_attr = 0o100644 << 16
                    archive.writestr(info, data, compresslevel=9)
            inspection = PluginPackage.inspect(temporary)
            validation = self.validator.validate(inspection)
            if not inspection.ok or not validation.valid:
                error = inspection.error or "; ".join(validation.errors)
                return WorkbenchWriteResult(
                    False, error=f"Completed ZIP failed production validation: {error}"
                )
            temporary.replace(destination)
            return WorkbenchWriteResult(
                True, str(destination), inspection.package_digest
            )
        except (OSError, ValueError, zipfile.BadZipFile) as exc:
            return WorkbenchWriteResult(False, error=str(exc))
        finally:
            temporary.unlink(missing_ok=True)
