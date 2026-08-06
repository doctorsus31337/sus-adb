import ast
import unittest
from pathlib import Path
from unittest.mock import patch

from app.gui.menu_bar import MenuBar


ROOT = Path(__file__).parents[1]


def method_from_source(relative_path, class_name, method_name):
    tree = ast.parse((ROOT / relative_path).read_text(encoding="utf-8"))
    class_node = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    )
    method_node = next(
        node for node in class_node.body
        if isinstance(node, ast.FunctionDef) and node.name == method_name
    )
    namespace = {}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[method_node], type_ignores=[])), relative_path, "exec"), namespace)
    return namespace[method_name]


OPEN_PLUGIN_MANAGER = method_from_source(
    "app/gui/main_window.py", "SusADBWindow", "open_plugin_manager"
)
OPEN_OFFICIAL_CATALOG = method_from_source(
    "app/gui/main_window.py", "SusADBWindow", "open_official_addon_catalog"
)
OPEN_INSTALLED_ADDONS = method_from_source(
    "app/gui/main_window.py", "SusADBWindow", "open_installed_addons"
)
OPEN_ADDON_DIAGNOSTICS = method_from_source(
    "app/gui/main_window.py", "SusADBWindow", "open_addon_diagnostics"
)
OPEN_ADDONS_CENTER = method_from_source(
    "app/gui/main_window.py", "SusADBWindow", "open_addons_center"
)
OPEN_GUIDE_DESTINATION = method_from_source(
    "app/gui/main_window.py", "SusADBWindow", "open_guide_destination"
)
OPEN_DEVICE_RECOVERY = method_from_source(
    "app/gui/main_window.py", "SusADBWindow", "open_device_recovery"
)
SHOW_PLUGIN_SECTION = method_from_source(
    "app/gui/plugin_manager_panel.py", "PluginManagerPanel", "show_section"
)


class FakeMenu:
    def __init__(self, parent, **_kwargs):
        self.parent = parent
        self.entries = []

    def add_command(self, **kwargs):
        self.entries.append(("command", kwargs))

    def add_separator(self):
        self.entries.append(("separator", {}))

    def add_cascade(self, **kwargs):
        self.entries.append(("cascade", kwargs))

    def index(self, index):
        if index == "end":
            return len(self.entries) - 1 if self.entries else None
        return index

    def delete(self, first, last=None):
        if not self.entries:
            return
        start = int(first)
        stop = len(self.entries) - 1 if last == "end" else int(last or first)
        del self.entries[start : stop + 1]


class FakeWindow:
    def __init__(self):
        self.plugin_registry = None
        self.plugin_manager = None
        self.calls = []
        self.menu = None

    def config(self, **kwargs):
        self.menu = kwargs.get("menu")

    def __getattr__(self, name):
        def callback(*args):
            self.calls.append((name, args))
        return callback


class AddonRoutingTests(unittest.TestCase):
    def test_addons_menu_exposes_distinct_destination_callbacks(self):
        window = FakeWindow()
        with patch("app.gui.menu_bar.tk.Menu", FakeMenu):
            menu_bar = MenuBar(window)

        commands = {
            entry[1]["label"]: entry[1]["command"]
            for entry in menu_bar.addons_menu.entries
            if entry[0] == "command"
        }
        expected = {
            "Open Add-ons Center…": "open_addons_center",
            "Official Add-on Catalog…": "open_official_addon_catalog",
            "Manage Installed Add-ons…": "open_installed_addons",
            "Add-on Diagnostics…": "open_addon_diagnostics",
        }
        self.assertEqual(
            [entry[1]["label"] for entry in window.menu.entries if entry[0] == "cascade"],
            ["File", "Settings", "View", "Tools", "Add-ons", "Help", "About"],
        )
        self.assertEqual(set(expected), set(commands) & set(expected))
        self.assertEqual(len({id(commands[label]) for label in expected}), len(expected))
        for label, callback_name in expected.items():
            commands[label]()
            self.assertEqual(window.calls[-1], (callback_name, ()))

    def test_plugin_manager_routes_select_explicit_sections(self):
        class Pentest:
            def __init__(self):
                self.panel = object()
                self.sections = []

            def open_plugins(self, section=None):
                self.sections.append(section)
                return self.panel

        class Window:
            open_plugin_manager = OPEN_PLUGIN_MANAGER

            def __init__(self):
                self.pentest = Pentest()
                self.addons_center = object()

            def enter_pentest_workspace(self):
                return self.pentest

        window = Window()
        center = window.addons_center
        self.assertIs(OPEN_OFFICIAL_CATALOG(window), window.pentest.panel)
        self.assertIs(OPEN_OFFICIAL_CATALOG(window), window.pentest.panel)
        self.assertIs(OPEN_INSTALLED_ADDONS(window), window.pentest.panel)
        self.assertIs(OPEN_ADDON_DIAGNOSTICS(window), window.pentest.panel)
        self.assertEqual(
            window.pentest.sections,
            ["Official Catalog", "Official Catalog", "Installed", "Diagnostics"],
        )
        self.assertIs(window.addons_center, center)

    def test_addons_center_is_tracked_independently_and_refocused(self):
        class Center:
            def __init__(self, *_args, **_kwargs):
                self.focused = []
                self.deiconified = 0
                self.lifted = 0

            def winfo_exists(self):
                return True

            def deiconify(self):
                self.deiconified += 1

            def lift(self):
                self.lifted += 1

            def focus_force(self):
                return None

            def focus_addon(self, query):
                self.focused.append(query)
                return self

        class Window:
            addons_center = None
            theme = manager = host = object()
            plugin_manager = manager
            addon_window_host = host

            def open_context_help(self, _topic):
                return None

        window = Window()
        OPEN_ADDONS_CENTER.__globals__["AddonsCenter"] = Center
        first = OPEN_ADDONS_CENTER(window)
        second = OPEN_ADDONS_CENTER(window, "Device Rescue & Recovery")
        self.assertIs(first, second)
        self.assertEqual(first.focused, ["Device Rescue & Recovery"])
        self.assertEqual((first.deiconified, first.lifted), (1, 1))

    def test_guide_addon_destinations_preserve_destination_identity(self):
        class Window:
            def __init__(self):
                self.queries = []

            def open_addons_center(self, query=None):
                self.queries.append(query)
                return query

        window = Window()
        expected = {
            "device-rescue": "Device Rescue & Recovery",
            "readiness-advisor": "Instrumentation & Root Readiness Advisor",
            "webview-inspector": "WebView Security Inspector",
        }
        for destination, query in expected.items():
            self.assertEqual(OPEN_GUIDE_DESTINATION(window, destination), query)
        self.assertEqual(window.queries, list(expected.values()))

    def test_device_recovery_fallback_focuses_its_catalog_card(self):
        class Registry:
            def list(self, _contribution_type):
                return ()

        class Window:
            plugin_registry = Registry()

            def __init__(self):
                self.queries = []

            def open_addons_center(self, query=None):
                self.queries.append(query)
                return query

        window = Window()
        self.assertEqual(
            OPEN_DEVICE_RECOVERY(window), "Device Rescue & Recovery"
        )
        self.assertEqual(window.queries, ["Device Rescue & Recovery"])

    def test_plugin_manager_section_rejects_fallbacks(self):
        class Tabs:
            selected = None

            def set(self, name):
                self.selected = name

        panel = type("Panel", (), {})()
        panel.views = {
            name: object()
            for name in ("Official Catalog", "Installed", "Diagnostics")
        }
        panel.tabs = Tabs()
        self.assertIs(SHOW_PLUGIN_SECTION(panel, "Official Catalog"), panel)
        self.assertEqual(panel.tabs.selected, "Official Catalog")
        with self.assertRaisesRegex(ValueError, "Unknown Plugin Manager section"):
            SHOW_PLUGIN_SECTION(panel, "Add-ons Center")
        self.assertEqual(panel.tabs.selected, "Official Catalog")

    def test_script_trust_action_uses_clear_revocation_copy(self):
        source = (ROOT / "app/gui/script_studio_panel.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('("Trust / Revoke Trust", self.toggle_trust)', source)
        self.assertNotIn("Trust / Untrust", source)


if __name__ == "__main__":
    unittest.main()
