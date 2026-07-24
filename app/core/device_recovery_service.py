"""Bounded, host-owned selected-file recovery over an injected ADB backend."""

from __future__ import annotations

import hashlib
import json
import math
import os
import shlex
import shutil
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Callable, Iterable, Mapping


PUBLIC_PRESETS = (
    "DCIM",
    "Pictures",
    "Music",
    "Movies",
    "Download",
    "Documents",
    "Recordings",
    "Podcasts",
    "Audiobooks",
    "Android/media",
)
SHARED_STORAGE_CANDIDATES = ("/storage/emulated/0", "/sdcard")
USABLE_STATES = frozenset(("device", "recovery", "sideload"))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def public_paths(base: str = "/sdcard") -> tuple[str, ...]:
    return tuple(f"{base.rstrip('/')}/{name}" for name in PUBLIC_PRESETS)


@dataclass(frozen=True, slots=True)
class RecoveryLimits:
    file_count: int = 10000
    byte_count: int = 128 * 1024 * 1024 * 1024
    recursion_depth: int = 12
    workers: int = 1

    def validate(self) -> str:
        if not 1 <= self.file_count <= 100000:
            return "File-count limit must be between 1 and 100000."
        if not 1 <= self.byte_count <= 1024 * 1024 * 1024 * 1024:
            return "Byte limit must be between 1 byte and 1 TiB."
        if not 1 <= self.recursion_depth <= 32:
            return "Recursion limit must be between 1 and 32."
        if not 1 <= self.workers <= 4:
            return "Worker limit must be between 1 and 4."
        return ""


@dataclass(frozen=True, slots=True)
class RemoteRecoveryEntry:
    source: str
    kind: str
    size: int | None = None
    source_timestamp: str = ""
    error: str = ""


@dataclass(frozen=True, slots=True)
class StorageScan:
    ok: bool
    serial: str
    requested_path: str
    resolved_path: str = ""
    entries: tuple[RemoteRecoveryEntry, ...] = ()
    top_level_entries: tuple[RemoteRecoveryEntry, ...] = ()
    folder_count: int = 0
    file_count: int = 0
    loose_file_count: int = 0
    estimated_bytes: int | None = None
    identity: str = ""
    errors: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DestinationPreflight:
    ok: bool
    base_path: str
    recovery_path: str
    drive: str
    free_bytes: int
    required_bytes: int | None
    safety_headroom: float
    safety_bytes: int | None
    writable: bool
    error: str = ""


@dataclass(frozen=True, slots=True)
class RecoveryPlan:
    ok: bool
    serial: str
    sources: tuple[str, ...]
    entries: tuple[RemoteRecoveryEntry, ...]
    destination: DestinationPreflight
    limits: RecoveryLimits
    duplicate_policy: str = "skip"
    replace_confirmed: bool = False
    estimate_acknowledged: bool = False
    priorities: tuple[tuple[str, int], ...] = ()
    error: str = ""


@dataclass(frozen=True, slots=True)
class RecoveryItem:
    source: str
    destination: str
    size: int
    source_timestamp: str
    recovered_timestamp: str
    sha256: str
    state: str
    error: str = ""


@dataclass(frozen=True, slots=True)
class RecoveryProgress:
    serial: str
    current_path: str
    files_completed: int
    files_total: int
    bytes_completed: int
    bytes_total: int | None
    started_at: str
    elapsed_seconds: float
    state: str


@dataclass(frozen=True, slots=True)
class RecoveryResult:
    ok: bool
    items: tuple[RecoveryItem, ...] = ()
    error: str | None = None
    cancelled: bool = False
    interrupted: bool = False
    manifest_path: str = ""

    @property
    def partial_success(self) -> bool:
        recovered = any(item.state == "recovered" for item in self.items)
        failed = any(item.state == "failed" for item in self.items)
        return recovered and (failed or self.cancelled or self.interrupted)


class RecoveryCancellation:
    def __init__(self):
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    def cancelled(self) -> bool:
        return self._event.is_set()


class ADBRecoveryBackend:
    """Narrow adapter around ADBManager; every command carries an explicit serial."""

    def __init__(self, adb):
        self.adb = adb

    def state(self, serial: str) -> str:
        result = self.adb.run("get-state", serial=serial, timeout=8)
        return result.stdout.strip() if result.ok else "disconnected"

    def resolve_path(self, serial: str, path: str) -> str:
        for tool in ("readlink", "realpath"):
            args = ("shell", tool, "-f", "--", path) if tool == "readlink" else ("shell", tool, path)
            result = self.adb.run(*args, serial=serial, timeout=10)
            value = result.stdout.strip().splitlines()[0] if result.ok and result.stdout.strip() else ""
            if value.startswith("/"):
                return value
        return path

    def identity(self, serial: str) -> str:
        result = self.adb.run("shell", "id", serial=serial, timeout=8)
        return result.stdout.strip() if result.ok else ""

    def inventory(
        self, serial: str, path: str, *, depth: int, limit: int
    ) -> tuple[RemoteRecoveryEntry, ...]:
        quoted = shlex.quote(path)
        command = (
            f"find {quoted} -mindepth 1 -maxdepth {int(depth)} "
            f"-printf '%y\\t%s\\t%T@\\t%p\\n'"
        )
        result = self.adb.run("shell", "sh", "-c", command, serial=serial, timeout=90)
        entries = self.parse_inventory(result.stdout, limit)
        if entries or result.ok:
            return entries
        fallback = self.adb.run(
            "shell", "find", path, "-mindepth", "1", "-maxdepth", str(int(depth)),
            serial=serial, timeout=90,
        )
        values = []
        for raw in fallback.stdout.splitlines()[:limit]:
            source = raw.strip()
            if source.startswith("/"):
                metadata = self.adb.run(
                    "shell", "stat", "-c", "%F\t%s\t%Y", "--", source,
                    serial=serial, timeout=10,
                )
                kind, size, stamp = "unknown", None, ""
                if metadata.ok:
                    parts = metadata.stdout.split("\t", 2)
                    if len(parts) == 3:
                        label = parts[0].casefold()
                        kind = "file" if "file" in label else "directory" if "director" in label else "symlink" if "link" in label else "unknown"
                        try:
                            size = int(parts[1]) if kind == "file" else 0
                        except ValueError:
                            size = None
                        stamp = parts[2]
                values.append(RemoteRecoveryEntry(source, kind, size, stamp))
        return tuple(values)

    @staticmethod
    def parse_inventory(text: str, limit: int) -> tuple[RemoteRecoveryEntry, ...]:
        entries = []
        kinds = {"f": "file", "d": "directory", "l": "symlink"}
        for raw in text.splitlines():
            if len(entries) >= limit:
                break
            parts = raw.split("\t", 3)
            if len(parts) != 4 or not parts[3].startswith("/"):
                continue
            try:
                size = int(parts[1]) if parts[0] == "f" else 0
            except ValueError:
                size = None
            entries.append(
                RemoteRecoveryEntry(parts[3], kinds.get(parts[0], "unknown"), size, parts[2])
            )
        return tuple(entries)

    def pull(self, serial: str, source: str, destination: str):
        return self.adb.run("pull", source, destination, serial=serial, timeout=300)


class DeviceRecoveryService:
    def __init__(
        self,
        backend,
        *,
        selected_serial_provider: Callable[[], str | None] = lambda: None,
        clock: Callable[[], str] = utc_now,
        monotonic: Callable[[], float] = time.monotonic,
        disk_usage: Callable[[str], object] = shutil.disk_usage,
    ):
        self.backend = backend
        self.selected_serial_provider = selected_serial_provider
        self.clock = clock
        self.monotonic = monotonic
        self.disk_usage = disk_usage

    @staticmethod
    def _valid_remote(path: str) -> bool:
        value = PurePosixPath(str(path))
        return bool(str(path).startswith("/") and "\0" not in str(path) and ".." not in value.parts)

    @staticmethod
    def _within(path: str, parent: str) -> bool:
        child = PurePosixPath(path)
        root = PurePosixPath(parent)
        return child == root or root in child.parents

    @staticmethod
    def _shared_path(path: str) -> bool:
        return path == "/sdcard" or path.startswith("/sdcard/") or path == "/storage/emulated" or path.startswith("/storage/emulated/")

    def scan_shared_storage(
        self,
        serial: str,
        requested_path: str = "/sdcard",
        *,
        custom_paths: Iterable[str] = (),
        limits: RecoveryLimits = RecoveryLimits(),
        allow_private: bool = False,
    ) -> StorageScan:
        if not serial:
            return StorageScan(False, "", requested_path, errors=("Select a device explicitly.",))
        if limits.validate():
            return StorageScan(False, serial, requested_path, errors=(limits.validate(),))
        requested = tuple(dict.fromkeys((requested_path, *custom_paths)))
        if any(not self._valid_remote(path) for path in requested):
            return StorageScan(False, serial, requested_path, errors=("Only explicit absolute device paths are accepted.",))
        if any(not self._shared_path(path) for path in requested) and not allow_private:
            return StorageScan(False, serial, requested_path, errors=("Private paths require observable existing root and explicit active-scope permission.",))
        try:
            state = self.backend.state(serial)
        except Exception as exc:
            return StorageScan(False, serial, requested_path, errors=(f"Device state check failed: {exc}",))
        if state not in USABLE_STATES:
            return StorageScan(False, serial, requested_path, errors=(f"Device is {state}.",))

        try:
            resolved = self.backend.resolve_path(serial, requested_path)
        except Exception:
            resolved = requested_path
        candidates = tuple(dict.fromkeys((resolved, *SHARED_STORAGE_CANDIDATES))) if self._shared_path(requested_path) else (resolved,)
        entries: tuple[RemoteRecoveryEntry, ...] = ()
        errors = []
        chosen = resolved
        for candidate in candidates:
            if not self._valid_remote(candidate):
                continue
            try:
                values = self.backend.inventory(
                    serial, candidate, depth=limits.recursion_depth, limit=limits.file_count
                )
            except Exception as exc:
                errors.append(f"Inventory failed for {candidate}: {exc}")
                continue
            if values:
                chosen, entries = candidate, values
                break
            errors.append(f"No inventory returned for {candidate}.")
        extra = []
        for path in requested[1:]:
            if any(self._within(path, root) for root in candidates):
                try:
                    extra.extend(
                        self.backend.inventory(
                            serial, path, depth=limits.recursion_depth, limit=limits.file_count
                        )
                    )
                except Exception as exc:
                    errors.append(f"Inventory failed for {path}: {exc}")
        entries = tuple(
            sorted(
                {entry.source: entry for entry in (*entries, *extra)}.values(),
                key=lambda item: item.source,
            )
        )
        files = tuple(entry for entry in entries if entry.kind in {"file", "unknown"})
        folders = tuple(entry for entry in entries if entry.kind == "directory")
        top_level = tuple(
            entry for entry in entries
            if PurePosixPath(entry.source).parent == PurePosixPath(chosen)
        )
        loose = sum(PurePosixPath(entry.source).parent == PurePosixPath(chosen) for entry in files)
        unknown = any(entry.size is None for entry in files)
        estimate = None if unknown else sum(entry.size or 0 for entry in files)
        try:
            identity = self.backend.identity(serial) if hasattr(self.backend, "identity") else ""
        except Exception:
            identity = ""
        return StorageScan(
            bool(entries),
            serial,
            requested_path,
            chosen,
            entries,
            top_level,
            len(folders),
            len(files),
            loose,
            estimate,
            identity,
            tuple(errors if not entries else ()),
        )

    def preflight_destination(
        self,
        destination: str,
        required_bytes: int | None,
        *,
        safety_headroom: float = 0.10,
    ) -> DestinationPreflight:
        if not 0 <= safety_headroom <= 1:
            return DestinationPreflight(False, destination, "", "", 0, required_bytes, safety_headroom, None, False, "Safety headroom must be between 0% and 100%.")
        base = Path(destination).expanduser().resolve()
        writable = base.is_dir() and os.access(base, os.W_OK)
        if not writable:
            return DestinationPreflight(False, str(base), "", base.anchor, 0, required_bytes, safety_headroom, None, False, "Select an existing writable host destination.")
        try:
            usage = self.disk_usage(str(base))
        except OSError as exc:
            return DestinationPreflight(False, str(base), "", base.anchor, 0, required_bytes, safety_headroom, None, writable, f"Could not inspect destination capacity: {exc}")
        free = int(usage.free)
        safety = math.ceil(required_bytes * safety_headroom) if required_bytes is not None else None
        name = "SUS-Recovery-" + self.clock().replace(":", "").replace("+", "_").replace("-", "")
        target = base / name
        suffix = 1
        while target.exists():
            target = base / f"{name}-{suffix}"
            suffix += 1
        ok = required_bytes is None or required_bytes + (safety or 0) <= free
        return DestinationPreflight(
            ok,
            str(base),
            str(target),
            base.anchor,
            free,
            required_bytes,
            safety_headroom,
            safety,
            writable,
            "" if ok else "Known recovery size plus safety headroom exceeds free destination space.",
        )

    def build_plan(
        self,
        scan: StorageScan,
        sources: Iterable[str],
        destination: str,
        *,
        limits: RecoveryLimits = RecoveryLimits(),
        safety_headroom: float = 0.10,
        duplicate_policy: str = "skip",
        replace_confirmed: bool = False,
        acknowledge_unknown: bool = False,
        bounded_selected_files: bool = False,
        priorities: Mapping[str, int] | None = None,
    ) -> RecoveryPlan:
        selected = tuple(dict.fromkeys(str(path) for path in sources if str(path)))
        empty_destination = DestinationPreflight(False, destination, "", "", 0, None, safety_headroom, None, False)
        if not scan.ok or not selected:
            return RecoveryPlan(False, scan.serial, selected, (), empty_destination, limits, error="Run a successful scan and select at least one source.")
        if duplicate_policy not in {"skip", "rename", "replace"}:
            return RecoveryPlan(False, scan.serial, selected, (), empty_destination, limits, error="Choose skip, rename, or replace.")
        if duplicate_policy == "replace" and not replace_confirmed:
            return RecoveryPlan(False, scan.serial, selected, (), empty_destination, limits, error="Replace requires explicit confirmation.")
        entries = tuple(
            entry for entry in scan.entries
            if entry.kind in {"file", "unknown"} and any(self._within(entry.source, source) for source in selected)
        )
        if len(entries) > limits.file_count:
            return RecoveryPlan(False, scan.serial, selected, entries, empty_destination, limits, error="Selected files exceed the configured file-count limit.")
        estimate = None if any(entry.size is None for entry in entries) else sum(entry.size or 0 for entry in entries)
        if estimate is not None and estimate > limits.byte_count:
            return RecoveryPlan(False, scan.serial, selected, entries, empty_destination, limits, error="Selected files exceed the configured byte limit.")
        if (estimate is None or estimate == 0) and not (acknowledge_unknown and bounded_selected_files):
            return RecoveryPlan(False, scan.serial, selected, entries, empty_destination, limits, error="Source size is zero or unknown. Select bounded files and acknowledge the unavailable estimate.")
        preflight = self.preflight_destination(destination, estimate, safety_headroom=safety_headroom)
        if not preflight.ok:
            return RecoveryPlan(False, scan.serial, selected, entries, preflight, limits, error=preflight.error)
        priority_values = tuple(sorted((str(path), int(value)) for path, value in (priorities or {}).items()))
        return RecoveryPlan(True, scan.serial, selected, entries, preflight, limits, duplicate_policy, replace_confirmed, acknowledge_unknown, priority_values)

    @staticmethod
    def _relative(source: str) -> PurePosixPath | None:
        value = PurePosixPath(source.lstrip("/"))
        if value.is_absolute() or not value.parts or ".." in value.parts:
            return None
        return value

    @staticmethod
    def _rename_duplicate(target: Path) -> Path:
        index = 1
        candidate = target
        while candidate.exists():
            candidate = target.with_name(f"{target.stem}-copy-{index}{target.suffix}")
            index += 1
        return candidate

    @staticmethod
    def _priority(source: str, values: tuple[tuple[str, int], ...]) -> int:
        matches = [priority for path, priority in values if DeviceRecoveryService._within(source, path)]
        return min(matches) if matches else 100

    def execute(
        self,
        plan: RecoveryPlan,
        *,
        cancellation: RecoveryCancellation | None = None,
        progress: Callable[[RecoveryProgress], None] | None = None,
        resume_items: Iterable[RecoveryItem] = (),
    ) -> RecoveryResult:
        if not plan.ok:
            return RecoveryResult(False, error=plan.error)
        current = self.selected_serial_provider()
        if current != plan.serial:
            return RecoveryResult(False, error="The selected device serial changed; recovery was not started.", interrupted=True)
        try:
            state = self.backend.state(plan.serial)
        except Exception as exc:
            return RecoveryResult(False, error=f"Could not verify selected device: {exc}", interrupted=True)
        if state not in USABLE_STATES:
            return RecoveryResult(False, error=f"The selected device is {state}.", interrupted=True)
        token = cancellation or RecoveryCancellation()
        target_root = Path(plan.destination.recovery_path).resolve()
        base = Path(plan.destination.base_path).resolve()
        if base not in target_root.parents or target_root == base:
            return RecoveryResult(False, error="Recovery destination escaped the selected host directory.")
        resume_items = tuple(resume_items)
        if target_root.exists() and not resume_items:
            return RecoveryResult(False, error="Recovery destination already exists; it will not be overwritten.")
        if not target_root.exists():
            try:
                target_root.mkdir(parents=False, exist_ok=False)
            except OSError as exc:
                return RecoveryResult(False, error=f"Could not create recovery destination: {exc}")
        manifest_path = target_root / "recovery-manifest.json"
        resumed = {item.source: item for item in resume_items if item.state == "recovered"}
        items = []
        total_bytes = None if any(entry.size is None for entry in plan.entries) else sum(entry.size or 0 for entry in plan.entries)
        completed_bytes = 0
        started = self.clock()
        started_monotonic = self.monotonic()
        entries = sorted(plan.entries, key=lambda item: (self._priority(item.source, plan.priorities), item.source))

        def emit(path: str, state_name: str) -> None:
            if progress:
                progress(RecoveryProgress(plan.serial, path, len(items), len(entries), completed_bytes, total_bytes, started, max(0.0, self.monotonic() - started_monotonic), state_name))

        for entry in entries:
            if token.cancelled():
                saved=self._write_manifest(manifest_path, plan, items, "cancelled", started)
                return RecoveryResult(False, tuple(items), "Recovery cancelled.", True, manifest_path=str(manifest_path) if saved else "")
            try:
                disconnected = self.selected_serial_provider() != plan.serial or self.backend.state(plan.serial) not in USABLE_STATES
            except Exception:
                disconnected = True
            if disconnected:
                saved=self._write_manifest(manifest_path, plan, items, "interrupted", started)
                return RecoveryResult(False, tuple(items), "Selected device disconnected or changed.", interrupted=True, manifest_path=str(manifest_path) if saved else "")
            if entry.source in resumed:
                previous = resumed[entry.source]
                items.append(RecoveryItem(entry.source, previous.destination, previous.size, previous.source_timestamp, previous.recovered_timestamp, previous.sha256, "resumed"))
                completed_bytes += max(0, previous.size)
                emit(entry.source, "resumed")
                continue
            relative = self._relative(entry.source)
            if relative is None:
                items.append(RecoveryItem(entry.source, "", entry.size or 0, entry.source_timestamp, self.clock(), "", "failed", "Unsafe source path was rejected."))
                continue
            try:
                target = (target_root / relative).resolve()
            except OSError as exc:
                items.append(RecoveryItem(entry.source, "", entry.size or 0, entry.source_timestamp, self.clock(), "", "failed", str(exc)))
                continue
            if target_root not in target.parents:
                items.append(RecoveryItem(entry.source, "", entry.size or 0, entry.source_timestamp, self.clock(), "", "failed", "Destination escaped recovery boundary."))
                continue
            if target.exists():
                if plan.duplicate_policy == "skip":
                    items.append(RecoveryItem(entry.source, str(target), entry.size or 0, entry.source_timestamp, self.clock(), "", "skipped"))
                    emit(entry.source, "skipped")
                    continue
                if plan.duplicate_policy == "rename":
                    target = self._rename_duplicate(target)
                elif not plan.replace_confirmed:
                    items.append(RecoveryItem(entry.source, str(target), entry.size or 0, entry.source_timestamp, self.clock(), "", "failed", "Replace was not confirmed."))
                    continue
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                emit(entry.source, "copying")
                result = self.backend.pull(plan.serial, entry.source, str(target))
            except Exception as exc:
                items.append(RecoveryItem(entry.source, str(target), entry.size or 0, entry.source_timestamp, self.clock(), "", "failed", str(exc)))
                self._write_manifest(manifest_path, plan, items, "partial", started)
                continue
            if not getattr(result, "ok", False) or not target.is_file():
                error = getattr(result, "output", "") or "ADB pull did not produce a host file."
                items.append(RecoveryItem(entry.source, str(target), entry.size or 0, entry.source_timestamp, self.clock(), "", "failed", error))
                self._write_manifest(manifest_path, plan, items, "partial", started)
                continue
            try:
                size = target.stat().st_size
                hasher = hashlib.sha256()
                with target.open("rb") as recovered_file:
                    for chunk in iter(lambda: recovered_file.read(1024 * 1024), b""):
                        hasher.update(chunk)
                digest = hasher.hexdigest()
            except OSError as exc:
                items.append(RecoveryItem(entry.source, str(target), entry.size or 0, entry.source_timestamp, self.clock(), "", "failed", str(exc)))
                self._write_manifest(manifest_path, plan, items, "partial", started)
                continue
            items.append(RecoveryItem(entry.source, str(target), size, entry.source_timestamp, self.clock(), digest, "recovered"))
            completed_bytes += size
            self._write_manifest(manifest_path, plan, items, "running", started)
            emit(entry.source, "recovered")
        failed = any(item.state == "failed" for item in items)
        status = "partial-success" if failed and any(item.state == "recovered" for item in items) else "failed" if failed else "complete"
        saved=self._write_manifest(manifest_path, plan, items, status, started)
        error="Some selected items could not be recovered." if failed else None
        if not saved:error=(error+" " if error else "")+"Recovery manifest could not be written."
        return RecoveryResult(not failed and saved, tuple(items), error, manifest_path=str(manifest_path) if saved else "")

    def resume(self, plan: RecoveryPlan, manifest_path: str, **kwargs) -> RecoveryResult:
        try:
            manifest_file = Path(manifest_path).resolve()
            data = json.loads(manifest_file.read_text(encoding="utf-8"))
            if data.get("serial") != plan.serial:
                return RecoveryResult(False, error="Recovery manifest belongs to a different device serial.", interrupted=True)
            if Path(data.get("destination", "")).resolve() != manifest_file.parent:
                return RecoveryResult(False, error="Recovery manifest destination does not match its directory.")
            items = tuple(RecoveryItem(**item) for item in data.get("items", ()))
            destination = DestinationPreflight(
                True,
                plan.destination.base_path,
                str(manifest_file.parent),
                plan.destination.drive,
                plan.destination.free_bytes,
                plan.destination.required_bytes,
                plan.destination.safety_headroom,
                plan.destination.safety_bytes,
                plan.destination.writable,
            )
            plan = RecoveryPlan(
                plan.ok, plan.serial, plan.sources, plan.entries, destination, plan.limits,
                plan.duplicate_policy, plan.replace_confirmed, plan.estimate_acknowledged,
                plan.priorities, plan.error,
            )
        except (OSError, ValueError, TypeError) as exc:
            return RecoveryResult(False, error=f"Could not load recovery manifest: {exc}")
        return self.execute(plan, resume_items=items, **kwargs)

    def _write_manifest(
        self,
        path: Path,
        plan: RecoveryPlan,
        items: Iterable[RecoveryItem],
        status: str,
        started_at: str,
    ) -> bool:
        payload = {
            "format": 1,
            "serial": plan.serial,
            "sources": list(plan.sources),
            "destination": plan.destination.recovery_path,
            "started_at": started_at,
            "status": status,
            "items": [asdict(item) for item in sorted(items, key=lambda value: (value.source, value.destination))],
        }
        temporary = path.with_suffix(".tmp")
        try:
            temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            temporary.replace(path)
            return True
        except OSError:
            return False


class RecoveryEngine:
    """Compatibility wrapper for injected byte readers used by plugin SDK tests."""

    def __init__(self, reader, clock=lambda: "1970-01-01T00:00:00+00:00"):
        self.reader = reader
        self.clock = clock

    def recover(
        self,
        serial,
        sources,
        destination,
        limits=RecoveryLimits(),
        duplicate="skip",
        cancelled=lambda: False,
        resume=(),
    ):
        if not serial:
            return RecoveryResult(False, error="An explicit selected serial is required.")
        if duplicate not in {"skip", "rename", "replace"}:
            return RecoveryResult(False, error="Choose skip, rename, or replace explicitly.")
        root = Path(destination).expanduser().resolve()
        if not root.is_dir():
            return RecoveryResult(False, error="Select an existing writable destination directory.")
        completed = {item.source for item in resume if item.state == "recovered"}
        items = []
        count = total = 0
        for selected in sources:
            try:
                records = self.reader(serial, selected, limits.recursion_depth)
                for source, data, stamp in records:
                    if cancelled():
                        return RecoveryResult(False, tuple(items), "Recovery cancelled.", True)
                    relative = DeviceRecoveryService._relative(source)
                    if relative is None:
                        return RecoveryResult(False, tuple(items), "Unsafe source path was rejected.")
                    if source in completed:
                        items.append(RecoveryItem(source, "", len(data), stamp, self.clock(), hashlib.sha256(data).hexdigest(), "resumed-skip"))
                        continue
                    count += 1
                    total += len(data)
                    if count > limits.file_count or total > limits.byte_count:
                        return RecoveryResult(False, tuple(items), "Configured recovery limits were reached.")
                    target = (root / relative).resolve()
                    if root not in target.parents:
                        return RecoveryResult(False, tuple(items), "Destination escaped the selected boundary.")
                    if target.exists():
                        if duplicate == "skip":
                            items.append(RecoveryItem(source, str(target), len(data), stamp, self.clock(), hashlib.sha256(data).hexdigest(), "skipped"))
                            continue
                        if duplicate == "rename":
                            target = DeviceRecoveryService._rename_duplicate(target)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(data)
                    items.append(RecoveryItem(source, str(target), len(data), stamp, self.clock(), hashlib.sha256(data).hexdigest(), "recovered"))
            except (OSError, ValueError) as exc:
                items.append(RecoveryItem(str(selected), "", 0, "", self.clock(), "", "failed", str(exc)))
        return RecoveryResult(not any(item.state == "failed" for item in items), tuple(items))


def manifest(items: Iterable[RecoveryItem]) -> str:
    return json.dumps(
        [asdict(item) for item in sorted(items, key=lambda value: (value.source, value.destination))],
        indent=2,
        sort_keys=True,
    ) + "\n"
