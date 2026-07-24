"""Headless fake-only Sessions Center smoke; launches no real terminal or tool."""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    with tempfile.TemporaryDirectory(prefix="sessions center ") as directory:
        os.environ["XDG_CONFIG_HOME"] = directory
        import customtkinter as ctk

        from app.core.command_router import CommandRouter
        from app.core.external_terminal import ExternalTerminal
        from app.core.frida_target import FridaTarget, TargetType
        from app.core.host_state import DeviceState, HostStateSnapshot, HostStateStore
        from app.core.interactive_sessions import InteractiveSessionManager
        from app.core.script_descriptor import ScriptKind
        from app.core.script_library import ScriptLibrary
        from app.gui.sessions_center import SessionsCenter
        from app.gui.theme import get_theme

        class Resolver:
            paths = {
                "adb": "/opt/fake tools/adb",
                "objection": "/opt/fake tools/objection",
                "frida": "/opt/fake tools/frida",
                "frida-trace": "/opt/fake tools/frida-trace",
            }

            def resolve(self, name):
                return self.paths.get(name)

            def missing_message(self, name, *_args):
                return f"{name} missing"

        class Process:
            def __init__(self):
                self.returncode = None
                self.terminated = False

            def poll(self):
                return self.returncode

            def send_signal(self, _signal):
                self.returncode = 0

            def terminate(self):
                self.terminated = True
                self.returncode = 0

        processes = []
        terminal = ExternalTerminal(
            which=lambda name: "/usr/bin/konsole" if name == "konsole" else None,
            launcher=lambda _command, **_kwargs: processes.append(Process()) or processes[-1],
            platform_name="posix",
            realpath=lambda value: value,
        )

        class Objection:
            objection_path = "/opt/fake tools/objection"

            def build_attach_command(self, target, transport, serial):
                return (self.objection_path, "-S", transport, "-n", target, "start")

            def build_spawn_command(self, target, transport, serial):
                return (self.objection_path, "-S", transport, "-n", target, "-s", "start")

        class Frida:
            frida_path = "/opt/fake tools/frida"
            frida_trace_path = "/opt/fake tools/frida-trace"

        selected = {"value": "fixture-serial"}
        manager = InteractiveSessionManager(
            terminal, Resolver(),
            selected_serial_provider=lambda: selected["value"],
            adb_path_provider=lambda: "/opt/fake tools/adb",
            objection_manager=Objection(), frida_sessions=Frida(),
            id_factory=lambda: f"fixture-{len(processes)+1}",
        )
        target = FridaTarget(
            "Fixture App", "org.example.fixture", 42, TargetType.APPLICATION, True
        )
        state = HostStateStore()
        state.publish(
            HostStateSnapshot(
                DeviceState(
                    "fixture-serial", "Fixture", "SUS", "device",
                    "SUS Fixture", False,
                ),
                (
                    DeviceState(
                        "fixture-serial", "Fixture", "SUS", "device",
                        "SUS Fixture", False,
                    ),
                ),
                "device",
            )
        )
        library = ScriptLibrary(Path(directory) / "script library")
        created = library.create(
            "my observation script", "send('ok');", kind=ScriptKind.FRIDA
        )
        assert created.ok
        root = ctk.CTk()
        center = SessionsCenter(
            root, get_theme(), manager, state,
            target_provider=lambda: target, script_library=library,
        )

        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)

        def settle():
            deadline = time.monotonic() + 5
            while center._workers and time.monotonic() < deadline:
                root.update()
                time.sleep(0.005)
            root.update()
            assert not center._workers

        assert center._serial() == "fixture-serial"
        assert center._adb_plan().ready
        assert center._objection_plan().target == "org.example.fixture"
        center.script_combo.set("my observation script")
        frida = center._frida_plan()
        assert frida.ready and frida.command[-2] == "-l"
        assert "script library" in frida.command[-1]

        for width, height in ((900, 650), (980, 650), (1180, 780), (1400, 860)):
            center.geometry(f"{width}x{height}+0+0")
            for section in center.SECTIONS:
                center.tabs.set(section)
                root.update_idletasks()
                buttons = [
                    widget for widget in descendants(center)
                    if isinstance(widget, ctk.CTkButton) and widget.winfo_ismapped()
                ]
                assert all(
                    widget.winfo_rootx() + widget.winfo_width()
                    <= center.winfo_rootx() + center.winfo_width() + 2
                    and widget.winfo_rooty() + widget.winfo_height()
                    <= center.winfo_rooty() + center.winfo_height() + 2
                    for widget in buttons
                )
                assert all(
                    not str(widget.cget("fg_color")).casefold().startswith("blue")
                    for widget in buttons
                )

        route = CommandRouter(Resolver()).classify("adb shell")
        center.open_route(route)
        assert center.routed_plan.ready
        assert center.routed_plan.command == (
            "/opt/fake tools/adb", "-s", "fixture-serial", "shell"
        )
        center.launch_routed()
        settle()
        assert manager.list()[0].state.value == "connected"
        assert "fixture-serial" in center.sessions_text.get("1.0", "end")
        manager.terminate(manager.list()[0].session_id)
        center.close()
        manager.shutdown()
        assert all(process.terminated for process in processes)
        root.destroy()
    print(
        "sessions-center-smoke=PASS sizes=900x650,980x650,1180x780,1400x860 "
        "route-preview-lifecycle-cleanup=PASS fake-only=PASS"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
