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
        from app.core.host_state import (
            DeviceState, HostStateSnapshot, HostStateStore, TargetState,
        )
        from app.core.interactive_sessions import InteractiveSessionManager
        from app.core.objection_session_recovery import ObjectionSessionRecovery
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

            def build_attach_command(self, target, transport, serial, *, host, port):
                if transport == "usb":
                    return (self.objection_path, "-S", serial, "-n", target, "start")
                return (
                    self.objection_path, "-N", "-h", host, "-P", str(port),
                    "-n", target, "start",
                )

            def build_spawn_command(self, target, transport, serial, *, host, port):
                command = list(self.build_attach_command(
                    target, transport, serial, host=host, port=port
                ))
                command.insert(-1, "-s")
                return tuple(command)

        class Frida:
            frida_path = "/opt/fake tools/frida"
            frida_trace_path = "/opt/fake tools/frida-trace"

            def build_attach_command(self, target, *, endpoint):
                return (
                    self.frida_path, "-H", endpoint, "-N",
                    target.application_identifier,
                )

            def build_spawn_command(self, target, *, endpoint):
                return (
                    self.frida_path, "-H", endpoint, "-f",
                    target.application_identifier,
                )

            def build_pid_command(self, target, *, endpoint):
                return (self.frida_path, "-H", endpoint, "-p", str(target.pid))

            def build_trace_command(self, target, _pattern, *, mode, endpoint):
                flag = "-p" if mode == "pid" else "-f" if mode == "spawn" else "-N"
                value = str(target.pid) if mode == "pid" else target.application_identifier
                return (self.frida_trace_path, "-H", endpoint, flag, value)

        class RecoveryFrida:
            def managed_forwarding_ports(self, _serial):
                return ("tcp:27042", "tcp:27043")

        selected = {"value": "fixture-serial"}
        recovery = ObjectionSessionRecovery(
            RecoveryFrida(),
            selected_serial_provider=lambda: selected["value"],
            adb_state_provider=lambda _serial: "device",
        )
        manager = InteractiveSessionManager(
            terminal, Resolver(),
            selected_serial_provider=lambda: selected["value"],
            adb_path_provider=lambda: "/opt/fake tools/adb",
            objection_manager=Objection(), frida_sessions=Frida(),
            objection_recovery=recovery,
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
                TargetState(
                    "Fixture App", "org.example.fixture", 42, "application"
                ),
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
        network = center._objection_plan()
        assert network.command[1:6] == (
            "-N", "-h", "127.0.0.1", "-P", "27042"
        )
        center.objection_transport.set("usb")
        center._objection_transport_changed("usb")
        usb = center._objection_plan()
        assert usb.command[1:3] == ("-S", "fixture-serial")
        assert "usb" not in usb.command and "socket" not in usb.command
        center.launch_plan(usb)
        settle()
        assert manager.list()[-1].command == usb.command
        assert manager.list()[-1].descriptor.usb_serial == "fixture-serial"
        manager.terminate(manager.list()[-1].session_id)
        center.objection_transport.set("network")
        center._objection_transport_changed("network")
        assert center.objection_host.get() == "127.0.0.1"
        assert center.objection_port.get() == "27042"
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
        routed_record = next(
            record for record in manager.list()
            if record.session_type.value == "adb-shell"
            and record.state.value == "connected"
        )
        assert "fixture-serial" in center.sessions_text.get("1.0", "end")
        manager.terminate(routed_record.session_id)
        objection = manager.launch(
            manager.build_objection(
                "fixture-serial", "org.example.fixture"
            )
        )
        assert objection.ok
        report = manager.report_objection_failure(
            objection.record.session_id,
            "frida.InvalidOperationError: device is gone\n"
            "Unable to run cleanups: script is destroyed",
            command_history=("help", "help android sslpinning"),
        )
        assert report.kind.value == "device-gone"
        center.render_sessions()
        assert "lost its connection" in center.sessions_text.get("1.0", "end")
        assert "help android sslpinning" in manager.diagnostics(
            objection.record.session_id
        )
        manager.terminate(objection.record.session_id)
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
