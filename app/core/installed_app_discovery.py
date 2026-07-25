"""ADB-only installed application discovery independent of Frida readiness."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class InstalledApplication:
    package_id: str
    label: str = ""
    system: bool = False
    enabled: bool | None = None
    launchable: bool | None = None
    version: str = ""
    debuggable: bool | None = None
    running: bool = False
    pid: int | None = None
    apk_path: str = ""
    uid: str = ""

    @property
    def display_label(self) -> str:
        return f"{self.label} — {self.package_id}" if self.label else self.package_id


@dataclass(frozen=True, slots=True)
class InstalledAppResult:
    serial: str
    applications: tuple[InstalledApplication, ...] = ()
    errors: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.errors


class ADBInstalledAppDiscovery:
    def __init__(self, adb):
        self.adb = adb

    def scan(self, serial: str | None) -> InstalledAppResult:
        if not serial:
            return InstalledAppResult("", errors=("No device is selected.",))
        packages = self.adb.run(
            "shell", "pm", "list", "packages", "-f", "-U",
            "--show-versioncode", serial=serial, timeout=45,
        )
        if not packages.ok:
            return InstalledAppResult(
                serial, errors=(packages.output or "ADB package scan failed.",)
            )
        disabled_result = self.adb.run(
            "shell", "pm", "list", "packages", "-d",
            serial=serial, timeout=30,
        )
        launchable_result = self.adb.run(
            "shell", "cmd", "package", "query-activities", "--brief",
            "-a", "android.intent.action.MAIN",
            "-c", "android.intent.category.LAUNCHER",
            serial=serial, timeout=45,
        )
        processes_result = self.adb.run(
            "shell", "ps", "-A", "-o", "PID,NAME",
            serial=serial, timeout=30,
        )
        disabled = self._package_lines(
            disabled_result.stdout if disabled_result.ok else ""
        )
        launchable = self._activity_packages(
            launchable_result.stdout if launchable_result.ok else ""
        )
        running = self._processes(
            processes_result.stdout if processes_result.ok else ""
        )
        apps = []
        for line in packages.stdout.splitlines():
            parsed = self.parse_package_line(line)
            if parsed is None:
                continue
            path, package, uid, version = parsed
            pid = running.get(package)
            apps.append(
                InstalledApplication(
                    package,
                    system=self._is_system_path(path),
                    enabled=package not in disabled,
                    launchable=package in launchable,
                    version=version,
                    running=pid is not None,
                    pid=pid,
                    apk_path=path,
                    uid=uid,
                )
            )
        return InstalledAppResult(
            serial,
            tuple(sorted(apps, key=lambda item: item.package_id.casefold())),
        )

    @classmethod
    def parse_package_line(
        cls, line: str
    ) -> tuple[str, str, str, str] | None:
        value = line.strip()
        if not value.startswith("package:"):
            return None
        body = value[len("package:"):]
        metadata_start = min(
            (index for marker in (" uid:", " versionCode:")
             if (index := body.find(marker)) >= 0),
            default=len(body),
        )
        path_and_package = body[:metadata_start].strip()
        if "=" not in path_and_package:
            return None
        path, package = path_and_package.rsplit("=", 1)
        if not path or not package:
            return None
        fields = body[metadata_start:].split()
        metadata = {
            key: content
            for field in fields[1:]
            if ":" in field
            for key, content in (field.split(":", 1),)
        }
        return path, package, metadata.get("uid", ""), metadata.get("versionCode", "")

    @staticmethod
    def _package_lines(output: str) -> set[str]:
        return {
            line.split("package:", 1)[1].strip().split()[0]
            for line in output.splitlines()
            if line.strip().startswith("package:")
        }

    @staticmethod
    def _activity_packages(output: str) -> set[str]:
        packages = set()
        for line in output.splitlines():
            value = line.strip()
            if "/" in value and not value.startswith("No activities"):
                packages.add(value.split("/", 1)[0])
        return packages

    @staticmethod
    def _processes(output: str) -> dict[str, int]:
        result = {}
        for line in output.splitlines():
            parts = line.strip().split(maxsplit=1)
            if len(parts) != 2 or not parts[0].isdigit():
                continue
            name = parts[1].split(":", 1)[0]
            if "." in name:
                result.setdefault(name, int(parts[0]))
        return result

    @staticmethod
    def _is_system_path(path: str) -> bool:
        return path.startswith(
            ("/system/", "/product/", "/vendor/", "/odm/", "/apex/")
        )


def filter_installed_apps(
    applications,
    query="",
    *,
    user_only=False,
    system_only=False,
    launchable_only=False,
    running_only=False,
):
    value = query.strip().casefold()
    return tuple(
        app for app in applications
        if (not user_only or not app.system)
        and (not system_only or app.system)
        and (not launchable_only or app.launchable)
        and (not running_only or app.running)
        and (
            not value
            or value in f"{app.label} {app.package_id}".casefold()
        )
    )
