"""Evidence-based instrumentation routes and explicit rooted server setup."""

from __future__ import annotations

import hashlib
import shlex
import struct
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from app.core.command_result import CommandResult


class ReadinessRoute(str, Enum):
    ROOTED_SERVER_READY = "ROOTED_SERVER_READY"
    ROOTED_SERVER_SETUP_AVAILABLE = "ROOTED_SERVER_SETUP_AVAILABLE"
    GADGET_READY = "GADGET_READY"
    GADGET_PREPARATION_AVAILABLE = "GADGET_PREPARATION_AVAILABLE"
    DEBUGGABLE_DEVELOPMENT_ROUTE = "DEBUGGABLE_DEVELOPMENT_ROUTE"
    EMULATOR_ROUTE = "EMULATOR_ROUTE"
    ADB_ONLY = "ADB_ONLY"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class RouteAssessment:
    route: ReadinessRoute
    evidence: tuple[str, ...]
    prerequisites: tuple[str, ...]
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    next_action: str
    root_required: bool
    device_modification_required: bool
    apk_modification_required: bool
    data_loss_risk: str
    serial: str = ""
    architecture: str = ""
    host_version: str = ""
    server_version: str = ""


@dataclass(frozen=True, slots=True)
class ServerBinaryValidation:
    path: str
    size: int
    sha256: str
    architecture: str
    device_architecture: str
    valid: bool
    errors: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class FirmwareInputSummary:
    path: str
    size: int
    sha256: str
    classification: str
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ReadinessActionResult:
    ok: bool
    action: str
    serial: str = ""
    preview: tuple[str, ...] = ()
    results: tuple[CommandResult, ...] = ()
    error: str | None = None


class InstrumentationReadinessService:
    MAX_BINARY_BYTES = 256 * 1024 * 1024
    MAX_FIRMWARE_BYTES = 8 * 1024 * 1024 * 1024
    DEFAULT_DESTINATION = "/data/local/tmp/frida-server-sus-companion"
    ALLOWED_DESTINATIONS = frozenset((DEFAULT_DESTINATION,))
    _MACHINES = {
        3: "x86",
        40: "arm",
        62: "x86_64",
        183: "arm64",
    }

    def __init__(
        self,
        adb,
        frida,
        *,
        selected_serial_provider=lambda: None,
        session_provider=lambda: None,
    ):
        self.adb = adb
        self.frida = frida
        self.selected_serial_provider = selected_serial_provider
        self.session_provider = session_provider
        self._managed_servers: set[tuple[str, str]] = set()

    @staticmethod
    def normalize_architecture(value: str) -> str:
        normalized = value.strip().casefold().replace("-", "_")
        return {
            "arm64_v8a": "arm64",
            "aarch64": "arm64",
            "armeabi_v7a": "arm",
            "armeabi": "arm",
            "amd64": "x86_64",
            "x64": "x86_64",
            "i686": "x86",
        }.get(normalized, normalized)

    @classmethod
    def classify(
        cls,
        *,
        serial="",
        adb_state="unavailable",
        architecture="",
        root_available=False,
        server_available=False,
        endpoint_reachable=False,
        gadget_available=False,
        gadget_preparation_available=False,
        debuggable=False,
        emulator=False,
        host_frida_available=False,
        host_version="",
        server_version="",
    ) -> RouteAssessment:
        evidence = [
            f"Selected serial: {serial or 'none'}",
            f"ADB state: {adb_state}",
            f"Architecture: {architecture or 'unknown'}",
            f"Existing root: {'yes' if root_available else 'no'}",
            f"Frida Server present: {'yes' if server_available else 'no'}",
            f"Endpoint reachable: {'yes' if endpoint_reachable else 'no'}",
        ]
        prerequisites = []
        blockers = []
        warnings = []
        if not serial:
            route = ReadinessRoute.UNKNOWN
            blockers.append("Select a device explicitly.")
            next_action = "Refresh devices and explicitly select the intended serial."
        elif adb_state not in {"device", "recovery", "sideload"}:
            route = ReadinessRoute.BLOCKED
            blockers.append(f"ADB state {adb_state} is not usable for this route.")
            next_action = "Resolve authorization or connectivity for the same serial."
        elif root_available and server_available and endpoint_reachable:
            route = ReadinessRoute.ROOTED_SERVER_READY
            next_action = "Review an explicit attach, spawn, or script session."
        elif root_available:
            route = ReadinessRoute.ROOTED_SERVER_SETUP_AVAILABLE
            prerequisites.extend((
                "An operator-selected local Frida Server binary.",
                "An architecture match and explicit state-changing assessment scope.",
            ))
            next_action = "Select and validate a local Frida Server binary."
        elif gadget_available and endpoint_reachable:
            route = ReadinessRoute.GADGET_READY
            next_action = "Review the Gadget endpoint and a dedicated session."
        elif gadget_available or gadget_preparation_available:
            route = ReadinessRoute.GADGET_PREPARATION_AVAILABLE
            prerequisites.append("Use APK Laboratory and confirm every APK step separately.")
            next_action = "Open APK Laboratory with the explicitly selected app."
        elif debuggable:
            route = ReadinessRoute.DEBUGGABLE_DEVELOPMENT_ROUTE
            next_action = "Review the development/debuggable observation route."
        elif emulator:
            route = ReadinessRoute.EMULATOR_ROUTE
            next_action = "Review emulator capabilities and an explicit observation plan."
        else:
            route = ReadinessRoute.ADB_ONLY
            next_action = "Continue with ADB-only installed-app and static inspection."
        if not host_frida_available:
            warnings.append("Host Frida tools are unavailable.")
        if host_version and server_version and host_version != server_version:
            warnings.append("Host and server Frida versions do not match.")
        return RouteAssessment(
            route,
            tuple(evidence),
            tuple(prerequisites),
            tuple(blockers),
            tuple(warnings),
            next_action,
            route in {
                ReadinessRoute.ROOTED_SERVER_READY,
                ReadinessRoute.ROOTED_SERVER_SETUP_AVAILABLE,
            },
            route is ReadinessRoute.ROOTED_SERVER_SETUP_AVAILABLE,
            route is ReadinessRoute.GADGET_PREPARATION_AVAILABLE,
            "Bootloader unlocking commonly wipes user data; this advisor never uses it as a recovery technique.",
            serial,
            architecture,
            host_version,
            server_version,
        )

    def assess_device(
        self,
        serial: str | None,
        adb_state: str,
        *,
        gadget_available=False,
        gadget_preparation_available=False,
        debuggable=False,
        emulator=False,
    ) -> RouteAssessment:
        if not serial or adb_state not in {"device", "recovery", "sideload"}:
            return self.classify(serial=serial or "", adb_state=adb_state)
        abi_result = self.adb.run(
            "shell", "getprop", "ro.product.cpu.abi",
            serial=serial, timeout=10,
        )
        architecture = (
            self.normalize_architecture(abi_result.stdout)
            if abi_result.ok else ""
        )
        diagnosis = self.frida.diagnose(serial)
        root_available = diagnosis.root_available
        if not root_available:
            adb_root = self.adb.run(
                "shell", "id", serial=serial, timeout=8
            )
            root_available = adb_root.ok and "uid=0" in adb_root.stdout
        return self.classify(
            serial=serial,
            adb_state=adb_state,
            architecture=architecture,
            root_available=root_available,
            server_available=bool(diagnosis.server_path),
            endpoint_reachable=diagnosis.reachable,
            gadget_available=gadget_available,
            gadget_preparation_available=gadget_preparation_available,
            debuggable=debuggable,
            emulator=emulator,
            host_frida_available=bool(diagnosis.host_version),
            host_version=diagnosis.host_version or "",
            server_version=diagnosis.server_version or "",
        )

    @classmethod
    def validate_binary(
        cls, path: str | Path, device_architecture: str
    ) -> ServerBinaryValidation:
        source = Path(path).expanduser()
        errors = []
        if source.is_symlink():
            errors.append("Symbolic-link binaries are not accepted.")
        try:
            resolved = source.resolve(strict=True)
            stat = resolved.stat()
            if not resolved.is_file():
                errors.append("Select a regular Frida Server file.")
            if stat.st_size <= 0 or stat.st_size > cls.MAX_BINARY_BYTES:
                errors.append("The selected binary is empty or exceeds the bounded size limit.")
            digest = hashlib.sha256()
            with resolved.open("rb") as stream:
                head = stream.read(64)
                digest.update(head)
                while chunk := stream.read(1024 * 1024):
                    digest.update(chunk)
            architecture = cls._elf_architecture(head)
            wanted = cls.normalize_architecture(device_architecture)
            if not architecture:
                errors.append("The selected file is not a recognized ELF executable.")
            elif wanted and architecture != wanted:
                errors.append(
                    f"Binary architecture {architecture} does not match device {wanted}."
                )
            return ServerBinaryValidation(
                str(resolved), stat.st_size, digest.hexdigest(),
                architecture, wanted, not errors, tuple(errors),
            )
        except OSError as exc:
            errors.append(f"Could not inspect the selected binary: {exc}")
            return ServerBinaryValidation(
                str(source), 0, "", "", cls.normalize_architecture(
                    device_architecture
                ), False, tuple(errors),
            )

    @classmethod
    def inspect_firmware_input(cls, path: str | Path) -> FirmwareInputSummary:
        source = Path(path).expanduser()
        if source.is_symlink():
            return FirmwareInputSummary(
                str(source), 0, "", "rejected",
                ("Symbolic-link firmware inputs are not accepted.",),
            )
        try:
            resolved = source.resolve(strict=True)
            stat = resolved.stat()
            if not resolved.is_file():
                return FirmwareInputSummary(
                    str(resolved), 0, "", "rejected",
                    ("Select a regular local firmware input.",),
                )
            if stat.st_size <= 0 or stat.st_size > cls.MAX_FIRMWARE_BYTES:
                return FirmwareInputSummary(
                    str(resolved), stat.st_size, "", "rejected",
                    ("Firmware input is empty or exceeds the bounded size limit.",),
                )
            digest = hashlib.sha256()
            head = b""
            with resolved.open("rb") as stream:
                while chunk := stream.read(1024 * 1024):
                    if not head:
                        head = chunk[:4096]
                    digest.update(chunk)
            classification = (
                "android-boot-image" if head.startswith(b"ANDROID!")
                else "android-vbmeta-image" if head.startswith(b"AVB0")
                else "operator-supplied-firmware-input"
            )
            return FirmwareInputSummary(
                str(resolved), stat.st_size, digest.hexdigest(), classification
            )
        except OSError as exc:
            return FirmwareInputSummary(
                str(source), 0, "", "unavailable",
                (f"Could not inspect firmware input: {exc}",),
            )

    @classmethod
    def _elf_architecture(cls, head: bytes) -> str:
        if len(head) < 20 or head[:4] != b"\x7fELF":
            return ""
        endian = "<" if head[5] == 1 else ">" if head[5] == 2 else ""
        if not endian:
            return ""
        machine = struct.unpack(f"{endian}H", head[18:20])[0]
        return cls._MACHINES.get(machine, "")

    @classmethod
    def preview_upload(
        cls, validation: ServerBinaryValidation, destination: str
    ) -> ReadinessActionResult:
        error = cls._validate_destination(destination)
        if not validation.valid:
            error = "; ".join(validation.errors)
        return ReadinessActionResult(
            not error, "Preview Upload", preview=(
                f"Local: {validation.path}",
                f"SHA-256: {validation.sha256}",
                f"Size: {validation.size}",
                f"Architecture: {validation.architecture}",
                f"Destination: {destination}",
                "No action has been executed.",
            ), error=error,
        )

    @classmethod
    def _validate_destination(cls, destination: str) -> str | None:
        if destination not in cls.ALLOWED_DESTINATIONS:
            return "Select the explicit SUS Companion-managed server destination."
        return None

    def upload(
        self,
        serial: str,
        validation: ServerBinaryValidation,
        destination: str,
        *,
        confirmed=False,
        replace_confirmed=False,
    ) -> ReadinessActionResult:
        denied = self._changing_guard(serial, confirmed)
        if denied:
            return ReadinessActionResult(False, "Upload", serial, error=denied)
        preview = self.preview_upload(validation, destination)
        if not preview.ok:
            return ReadinessActionResult(
                False, "Upload", serial, preview.preview, error=preview.error
            )
        current = self.validate_binary(
            validation.path, validation.device_architecture
        )
        if current.sha256 != validation.sha256 or not current.valid:
            return ReadinessActionResult(
                False, "Upload", serial, error="The selected binary changed after validation."
            )
        exists = self.adb.run(
            "shell", "su", "-c",
            f"test -e {shlex.quote(destination)}",
            serial=serial, timeout=10,
        )
        if exists.ok and not replace_confirmed:
            return ReadinessActionResult(
                False, "Upload", serial,
                error="The destination already exists; explicit replacement confirmation is required.",
            )
        result = self.adb.run(
            "push", current.path, destination, serial=serial, timeout=120
        )
        if result.ok:
            self._managed_servers.add((serial, destination))
        return self._result("Upload", serial, (result,), preview.preview)

    def set_executable(
        self, serial: str, destination: str, *, confirmed=False
    ) -> ReadinessActionResult:
        return self._root_command(
            "Set Executable", serial, destination,
            f"chmod 755 {shlex.quote(destination)}", confirmed,
        )

    def start(
        self, serial: str, destination: str, *, confirmed=False
    ) -> ReadinessActionResult:
        command = f"{shlex.quote(destination)} >/dev/null 2>&1 &"
        return self._root_command(
            "Start", serial, destination, command, confirmed
        )

    def configure_forwarding(
        self, serial: str, *, confirmed=False
    ) -> ReadinessActionResult:
        denied = self._changing_guard(serial, confirmed)
        if denied:
            return ReadinessActionResult(
                False, "Configure Managed Forwarding", serial, error=denied
            )
        results = tuple(self.frida.repair_forwarding(serial))
        return self._result("Configure Managed Forwarding", serial, results)

    def verify_version(
        self, serial: str, destination: str
    ) -> ReadinessActionResult:
        denied = self._readonly_guard(serial)
        if denied:
            return ReadinessActionResult(
                False, "Verify Version", serial, error=denied
            )
        result = self.adb.run(
            "shell", "su", "-c",
            f"{shlex.quote(destination)} --version",
            serial=serial, timeout=15,
        )
        return self._result("Verify Version", serial, (result,))

    def verify_reachability(self, serial: str) -> ReadinessActionResult:
        denied = self._readonly_guard(serial)
        if denied:
            return ReadinessActionResult(
                False, "Verify Reachability", serial, error=denied
            )
        return self._result(
            "Verify Reachability", serial, (self.frida.list_processes(serial),)
        )

    def stop(self, serial: str, *, confirmed=False) -> ReadinessActionResult:
        denied = self._changing_guard(serial, confirmed)
        if denied:
            return ReadinessActionResult(False, "Stop", serial, error=denied)
        return self._result(
            "Stop", serial, (self.frida.stop_server(serial),)
        )

    def remove_managed(
        self, serial: str, destination: str, *, confirmed=False
    ) -> ReadinessActionResult:
        denied = self._changing_guard(serial, confirmed)
        if denied:
            return ReadinessActionResult(
                False, "Remove SUS Companion-managed Server", serial, error=denied
            )
        if (serial, destination) not in self._managed_servers:
            return ReadinessActionResult(
                False, "Remove SUS Companion-managed Server", serial,
                error="This server was not uploaded by the current SUS Companion session.",
            )
        result = self.adb.run(
            "shell", "su", "-c",
            f"rm -f {shlex.quote(destination)}",
            serial=serial, timeout=15,
        )
        if result.ok:
            self._managed_servers.discard((serial, destination))
        return self._result(
            "Remove SUS Companion-managed Server", serial, (result,)
        )

    def _root_command(
        self, action, serial, destination, command, confirmed
    ) -> ReadinessActionResult:
        denied = self._changing_guard(serial, confirmed)
        if denied:
            return ReadinessActionResult(False, action, serial, error=denied)
        destination_error = self._validate_destination(destination)
        if destination_error:
            return ReadinessActionResult(
                False, action, serial, error=destination_error
            )
        result = self.adb.run(
            "shell", "su", "-c", command, serial=serial, timeout=20
        )
        return self._result(action, serial, (result,), (command,))

    def _readonly_guard(self, serial):
        if not serial or serial != self.selected_serial_provider():
            return "The action is not bound to the currently selected serial."
        return None

    def _changing_guard(self, serial, confirmed):
        denied = self._readonly_guard(serial)
        if denied:
            return denied
        if not confirmed:
            return "Explicit confirmation is required for this separate action."
        session = self.session_provider()
        if not session or not session.permits("state-changing-testing"):
            return "An active authorized scope permitting state-changing-testing is required."
        if not self._existing_root(serial):
            return "Verified existing root or authorized adb root is required."
        return None

    def _existing_root(self, serial):
        if self.frida.root_available(serial):
            return True
        result = self.adb.run("shell", "id", serial=serial, timeout=8)
        return result.ok and "uid=0" in result.stdout

    @staticmethod
    def _result(action, serial, results, preview=()):
        error = "; ".join(
            result.output or "Command failed." for result in results
            if not result.ok
        ) or None
        return ReadinessActionResult(
            not error, action, serial, tuple(preview), tuple(results), error
        )
