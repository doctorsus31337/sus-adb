"""Local-only GUI acceptance smoke for Plugin Developer Workbench."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


MANIFEST = {
    "plugin_id": "example.workbench-smoke",
    "name": "Workbench Smoke",
    "version": "1.0.0",
    "entry_point": "plugin.py:Plugin",
    "plugin_api_version": "1.0",
    "requested_capabilities": [],
    "contributed_components": [],
}
PLUGIN = """\
class Plugin:
    def activate(self, api):
        return ()
    def deactivate(self):
        self.api = None
"""


def bounds(widget):
    return (
        widget.winfo_rootx(), widget.winfo_rooty(),
        widget.winfo_width(), widget.winfo_height(),
    )


def wait(app, condition, seconds=4):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        app.update()
        if condition():
            return True
        time.sleep(0.01)
    return False


def main():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        os.environ["XDG_CONFIG_HOME"] = str(root / "config")
        candidate = root / "candidate with spaces"
        candidate.mkdir()
        (candidate / "manifest.json").write_text(
            json.dumps(MANIFEST), encoding="utf-8"
        )
        (candidate / "plugin.py").write_text(PLUGIN, encoding="utf-8")
        from app.gui.main_window import SusADBWindow

        app = SusADBWindow()
        app._deferred_started = True
        assert app.plugin_workbench_window is None
        window = app.open_plugin_workbench()
        assert app.open_plugin_workbench() is window
        assert window.snapshot is None and window.source is None
        assert window.select_candidate(candidate)
        assert wait(app, lambda: window.snapshot is not None)
        assert window.snapshot.manifest.plugin_id == MANIFEST["plugin_id"]
        measurements = []
        for width, height in ((980, 680), (1180, 780), (1400, 860), (1600, 900)):
            window.geometry(f"{width}x{height}+0+0")
            app.update_idletasks()
            assert window.winfo_width() == width and window.winfo_height() == height
            assert window.footer.winfo_rooty() + window.footer.winfo_height() <= (
                window.winfo_rooty() + window.winfo_height()
            )
            measurements.append((
                f"{width}x{height}", bounds(window.title_label),
                bounds(window.status), bounds(window.tabs),
                window.footer.winfo_rooty(),
            ))
        for scale in (1.0, 1.25, 1.5):
            __import__("customtkinter").set_widget_scaling(scale)
            window.geometry("1180x780+0+0")
            app.update_idletasks()
            assert window.tabs.winfo_width() > 800
        __import__("customtkinter").set_widget_scaling(1.0)
        app.set_interface_mode("advanced")
        assert window.snapshot is not None
        app.set_interface_mode("guided")
        assert window.snapshot is not None
        catalog = app.plugin_manager.catalog
        skeleton = next(
            item for item in catalog.list()
            if any(
                action.get("kind") == "export-template"
                for action in item.manifest.addon_ui.get("catalog_actions", ())
            )
        )
        exported = catalog.export_template(
            skeleton.manifest.plugin_id, "export-template", root,
            skeleton.package_digest,
        )
        assert exported.ok, exported.error
        assert window.select_candidate(exported.path)
        assert wait(
            app,
            lambda: (
                window.snapshot is not None
                and window.snapshot.manifest is not None
                and window.snapshot.manifest.plugin_id
                == skeleton.manifest.plugin_id
            ),
        )
        assert any(
            finding.rule_id == "COMP002"
            for finding in window.snapshot.findings
        )
        window.tabs.set("Findings")
        app.update_idletasks()
        finding_text = window.views["Findings"].get("1.0", "end")
        package_text = window.views["Package"].get("1.0", "end")
        assert "Valid educational template structure" in finding_text
        assert "Choose a new stable plugin ID before installation" in finding_text
        assert window.markdown_button.cget("state") == "normal"
        assert window.json_button.cget("state") == "normal"
        assert window.install_button.cget("state") == "disabled"
        assert "Plugin Manager review: Unavailable" in package_text
        exported_root = Path(exported.path)
        manifest_path = exported_root / "manifest.json"
        derivative = json.loads(manifest_path.read_text(encoding="utf-8"))
        derivative["plugin_id"] = "example.workbench-skeleton"
        derivative["contributed_components"][0][
            "contribution_id"
        ] = "example.workbench-skeleton.documentation"
        manifest_path.write_text(json.dumps(derivative), encoding="utf-8")
        plugin_path = exported_root / "plugin.py"
        plugin_path.write_text(
            plugin_path.read_text(encoding="utf-8").replace(
                "skeleton.documentation",
                "example.workbench-skeleton.documentation",
            ),
            encoding="utf-8",
        )
        assert window.refresh_analysis()
        assert wait(
            app,
            lambda: (
                window.snapshot is not None
                and window.snapshot.manifest is not None
                and window.snapshot.manifest.plugin_id
                == "example.workbench-skeleton"
            ),
        )
        assert not any(
            finding.rule_id == "COMP002"
            for finding in window.snapshot.findings
        )
        assert window.install_button.cget("state") == "normal"
        window.close()
        assert app.plugin_workbench_window is None
        reopened = app.open_plugin_workbench()
        assert reopened is not window and reopened.snapshot is None
        reopened.close()
        assert not app._background_workers
        app.shutdown()
        print(
            "plugin-workbench-smoke=PASS "
            f"sizes={measurements} scaling=100%,125%,150% "
            "reserved-id-readable-report-enabled-handoff-blocked=PASS "
            "renamed-derivative-handoff-eligible=PASS "
            "lazy-singleton-static-analysis-filters-package-cleanup=PASS"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
