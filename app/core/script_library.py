"""Safe local Script Studio library persistence and search."""

from __future__ import annotations

import hashlib
import json
import shutil
import uuid
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from app.core.script_descriptor import ScriptDescriptor, ScriptKind, TrustState, utc_now


@dataclass(frozen=True, slots=True)
class LibraryResult:
    ok: bool
    descriptor: ScriptDescriptor | None = None
    descriptors: tuple[ScriptDescriptor, ...] = ()
    text: str | None = None
    error: str | None = None


class ScriptLibrary:
    DIRECTORIES = (
        "frida/inspection", "frida/networking", "frida/resilience-testing",
        "frida/custom", "frida/generated", "objection", "profiles", "metadata",
    )
    EXTENSIONS = {".js", ".ts", ".txt", ".objection", ".json"}

    def __init__(self, root: str | Path = "scripts"):
        self.root = Path(root).expanduser().resolve()
        self._cache: tuple[ScriptDescriptor, ...] = ()

    def ensure_directories(self) -> LibraryResult:
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            for directory in self.DIRECTORIES:
                (self.root / directory).mkdir(parents=True, exist_ok=True)
            return LibraryResult(True)
        except OSError as exc:
            return LibraryResult(False, error=f"Could not create the script library: {exc}")

    def _safe(self, path: str | Path) -> Path:
        candidate = Path(path).expanduser()
        if not candidate.is_absolute():
            candidate = self.root / candidate
        resolved = candidate.resolve()
        if resolved != self.root and self.root not in resolved.parents:
            raise ValueError("The path escapes the configured script library.")
        return resolved

    @staticmethod
    def digest_bytes(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    def scan(self) -> LibraryResult:
        ensured = self.ensure_directories()
        if not ensured.ok:
            return ensured
        descriptors = []
        try:
            for path in sorted(self.root.rglob("*")):
                if not path.is_file() or path.suffix.casefold() not in self.EXTENSIONS:
                    continue
                if path.parent == self.root / "metadata" or path.name.endswith(".meta.json"):
                    continue
                descriptor = self._descriptor_for(path)
                if descriptor:
                    descriptors.append(descriptor)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            return LibraryResult(False, error=f"Could not scan the script library: {exc}")
        self._cache = tuple(sorted(descriptors, key=lambda item: (item.kind.value, item.name.casefold())))
        return LibraryResult(True, descriptors=self._cache)

    def _descriptor_for(self, path: Path) -> ScriptDescriptor:
        metadata_path = self.root / "metadata" / f"{path.stem}.meta.json"
        data: dict[str, Any] = {}
        if metadata_path.exists():
            data = json.loads(metadata_path.read_text(encoding="utf-8"))
        kind = self._kind(path)
        stat = path.stat()
        defaults = {
            "script_id": data.get("script_id", path.relative_to(self.root).as_posix()),
            "name": data.get("name", path.stem), "kind": data.get("kind", kind.value),
            "path": str(path), "sha256": self.digest_bytes(path.read_bytes()),
            "created_at": data.get("created_at", utc_now()),
            "modified_at": data.get("modified_at", utc_now()),
            "metadata_path": str(metadata_path),
        }
        defaults.update({key: value for key, value in data.items() if key not in {"path", "sha256", "metadata_path"}})
        return ScriptDescriptor(**defaults)

    @staticmethod
    def _kind(path: Path) -> ScriptKind:
        if path.suffix.casefold() == ".json" or "profiles" in path.parts:
            return ScriptKind.PROFILE
        if path.suffix.casefold() in {".txt", ".objection"} or "objection" in path.parts:
            return ScriptKind.OBJECTION_RECIPE
        return ScriptKind.FRIDA

    def create(self, name: str, source: str = "", *, suffix: str = ".js", kind: ScriptKind = ScriptKind.FRIDA) -> LibraryResult:
        if not name.strip() or suffix.casefold() not in self.EXTENSIONS:
            return LibraryResult(False, error="A valid name and supported extension are required.")
        folder = {ScriptKind.FRIDA: "frida/custom", ScriptKind.OBJECTION_RECIPE: "objection", ScriptKind.PROFILE: "profiles"}[ScriptKind(kind)]
        try:
            path = self._safe(Path(folder) / f"{Path(name).stem}{suffix}")
            if path.exists():
                return LibraryResult(False, error="A library item with that name already exists.")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(source, encoding="utf-8")
            descriptor = ScriptDescriptor(str(uuid.uuid4()), Path(name).stem, kind, str(path), trust=TrustState.TRUSTED_LOCAL, sha256=self.digest_bytes(source.encode()), metadata_path=str(self.root / "metadata" / f"{path.stem}.meta.json"))
            self.save_metadata(descriptor)
            self.scan()
            return LibraryResult(True, descriptor=descriptor)
        except (OSError, ValueError) as exc:
            return LibraryResult(False, error=str(exc))

    def import_file(self, source_path: str | Path) -> LibraryResult:
        source = Path(source_path).expanduser().resolve()
        if not source.is_file() or source.suffix.casefold() not in self.EXTENSIONS:
            return LibraryResult(False, error="Select a supported local script or recipe file.")
        content = source.read_bytes()
        digest = self.digest_bytes(content)
        scanned = self.scan()
        if scanned.ok and any(item.sha256 == digest for item in scanned.descriptors):
            return LibraryResult(False, error="Duplicate script content already exists in the library.")
        try:
            kind = self._kind(source)
            folder = {ScriptKind.FRIDA: "frida/custom", ScriptKind.OBJECTION_RECIPE: "objection", ScriptKind.PROFILE: "profiles"}[kind]
            destination = self._safe(Path(folder) / source.name)
            if destination.exists():
                destination = destination.with_name(f"{destination.stem}-{digest[:8]}{destination.suffix}")
            shutil.copy2(source, destination)
            descriptor = ScriptDescriptor(str(uuid.uuid4()), source.stem, kind, str(destination), source=f"Imported from {source}", trust=TrustState.UNTRUSTED, sha256=digest, metadata_path=str(self.root / "metadata" / f"{destination.stem}.meta.json"))
            self.save_metadata(descriptor)
            self.scan()
            return LibraryResult(True, descriptor=descriptor)
        except (OSError, ValueError) as exc:
            return LibraryResult(False, error=f"Import failed: {exc}")

    def load_source(self, descriptor: ScriptDescriptor) -> LibraryResult:
        try:
            return LibraryResult(True, descriptor=descriptor, text=self._safe(descriptor.path).read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError) as exc:
            return LibraryResult(False, error=f"Could not read the script: {exc}")

    def save_source(self, descriptor: ScriptDescriptor, text: str) -> LibraryResult:
        try:
            path = self._safe(descriptor.path)
            path.write_text(text, encoding="utf-8")
            updated = replace(descriptor, sha256=self.digest_bytes(text.encode()), modified_at=utc_now())
            self.save_metadata(updated)
            self.scan()
            return LibraryResult(True, descriptor=updated)
        except (OSError, ValueError) as exc:
            return LibraryResult(False, error=f"Could not save the script: {exc}")

    def save_metadata(self, descriptor: ScriptDescriptor) -> LibraryResult:
        try:
            path = self._safe(descriptor.metadata_path or f"metadata/{Path(descriptor.path).stem}.meta.json")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(descriptor.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
            return LibraryResult(True, descriptor=descriptor)
        except (OSError, ValueError, TypeError) as exc:
            return LibraryResult(False, error=f"Could not save metadata: {exc}")

    def rename(self, descriptor: ScriptDescriptor, new_name: str) -> LibraryResult:
        if not new_name.strip():
            return LibraryResult(False, error="A new name is required.")
        try:
            old = self._safe(descriptor.path)
            new = self._safe(old.with_name(f"{Path(new_name).stem}{old.suffix}"))
            if new.exists():
                return LibraryResult(False, error="The destination already exists.")
            old.rename(new)
            old_metadata = self._safe(descriptor.metadata_path) if descriptor.metadata_path else None
            new_metadata = self._safe(Path("metadata") / f"{new.stem}.meta.json")
            if old_metadata and old_metadata.exists() and old_metadata != new_metadata:
                old_metadata.rename(new_metadata)
            updated = replace(descriptor, name=Path(new_name).stem, path=str(new), metadata_path=str(new_metadata), modified_at=utc_now())
            self.save_metadata(updated)
            self.scan()
            return LibraryResult(True, descriptor=updated)
        except (OSError, ValueError) as exc:
            return LibraryResult(False, error=f"Rename failed: {exc}")

    def delete(self, descriptor: ScriptDescriptor, *, confirmed: bool = False) -> LibraryResult:
        if not confirmed:
            return LibraryResult(False, error="Explicit deletion confirmation is required.")
        try:
            self._safe(descriptor.path).unlink(missing_ok=True)
            if descriptor.metadata_path:
                self._safe(descriptor.metadata_path).unlink(missing_ok=True)
            self.scan()
            return LibraryResult(True)
        except (OSError, ValueError) as exc:
            return LibraryResult(False, error=f"Delete failed: {exc}")

    def search(self, query: str = "", *, kind: str = "All", tag: str = "", trust: str = "All", classification: str = "All") -> tuple[ScriptDescriptor, ...]:
        q = query.strip().casefold()
        return tuple(item for item in self._cache if (
            (kind.casefold() == "all" or item.kind.value == kind.casefold())
            and (trust.casefold() == "all" or item.trust.value == trust.casefold())
            and (classification.casefold() == "all" or item.classification == classification.casefold())
            and (not tag.strip() or tag.strip().casefold() in {value.casefold() for value in item.tags})
            and (not q or q in " ".join((item.name, item.description, item.path, " ".join(item.tags))).casefold())
        ))
