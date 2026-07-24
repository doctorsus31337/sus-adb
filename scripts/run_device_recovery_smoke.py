"""Headless fake-only Device Rescue interaction smoke; never contacts ADB."""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    with tempfile.TemporaryDirectory() as directory:
        os.environ["XDG_CONFIG_HOME"] = directory
        import customtkinter as ctk

        from app.core.device_recovery_service import (
            DeviceRecoveryService,
            RemoteRecoveryEntry,
        )
        from app.gui.device_recovery_panel import DeviceRecoveryPanel
        from app.gui.theme import get_theme

        class Backend:
            entries = (
                RemoteRecoveryEntry("/storage/emulated/0/DCIM", "directory", 0, "1"),
                RemoteRecoveryEntry("/storage/emulated/0/DCIM/denied.jpg", "file", 3, "2"),
                RemoteRecoveryEntry("/storage/emulated/0/DCIM/ok.jpg", "file", 4, "3"),
            )

            def state(self, serial):
                return "device"

            def resolve_path(self, serial, path):
                return "/storage/emulated/0"

            def identity(self, serial):
                return "uid=1023(media_rw) user=0"

            def inventory(self, serial, path, *, depth, limit):
                return self.entries if path == "/storage/emulated/0" else ()

            def pull(self, serial, source, destination):
                if source.endswith("denied.jpg"):
                    return SimpleNamespace(ok=False, output="Permission denied")
                Path(destination).write_bytes(b"data")
                return SimpleNamespace(ok=True, output="")

        root = ctk.CTk()
        root.title("Device Rescue Smoke")
        theme = get_theme()
        selected = {"value": "fixture-serial"}
        service = DeviceRecoveryService(
            Backend(),
            selected_serial_provider=lambda: selected["value"],
            disk_usage=lambda _path: SimpleNamespace(total=10_000, used=1_000, free=9_000),
        )
        panel = DeviceRecoveryPanel(root, theme, service)
        panel.pack(fill="both", expand=True)
        context = SimpleNamespace(
            selected_device={
                "serial": "fixture-serial",
                "display_name": "Fixture Device",
                "state": "device",
                "authorized": True,
                "root_available": False,
            },
            adb_state="device",
            assessment_scope={},
            session_state="none",
        )
        panel.apply_context(context)

        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)

        def settle():
            deadline = time.monotonic() + 5
            while panel.worker is not None and time.monotonic() < deadline:
                root.update()
                time.sleep(0.005)
            root.update_idletasks()
            assert panel.worker is None

        for width, height in ((900, 650), (980, 650), (1180, 780), (1400, 860)):
            root.geometry(f"{width}x{height}+0+0")
            for section in panel.SECTIONS:
                panel.tabs.set(section)
                root.update_idletasks()
                assert panel.winfo_width() <= width and panel.winfo_height() <= height
                assert tuple(panel.pages) == panel.SECTIONS
                mapped_buttons = [
                    widget for widget in descendants(panel)
                    if isinstance(widget, ctk.CTkButton) and widget.winfo_ismapped()
                ]
                assert all(
                    widget.winfo_rootx() >= panel.winfo_rootx()
                    and widget.winfo_rootx() + widget.winfo_width()
                    <= panel.winfo_rootx() + panel.winfo_width() + 2
                    and widget.winfo_rooty() + widget.winfo_height()
                    <= panel.winfo_rooty() + panel.winfo_height() + 2
                    for widget in mapped_buttons
                )
                assert all(
                    not str(widget.cget("fg_color")).casefold().startswith("blue")
                    for widget in mapped_buttons
                )

        panel.start_scan()
        settle()
        assert panel.scan.ok and panel.scan.estimated_bytes == 7
        assert panel.scan.resolved_path == "/storage/emulated/0"
        for name, variable in panel.preset_vars.items():
            variable.set(name == "DCIM")
        panel.destination_entry.insert(0, directory)
        panel.build_plan()
        assert panel.plan.ok and len(panel.plan.entries) == 2
        panel.start_recovery()
        settle()
        assert panel.result.partial_success
        assert [item.state for item in panel.result.items] == ["failed", "recovered"]
        assert Path(panel.result.manifest_path).is_file()
        assert "Partial Success" in panel.results_text.get("1.0", "end")
        assert panel.start_button.cget("state") == "normal"
        panel.cleanup()
        root.destroy()
    print(
        "device-recovery-smoke=PASS sizes=900x650,980x650,1180x780,1400x860 "
        "scan-plan-partial-results=PASS fake-only=PASS"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
