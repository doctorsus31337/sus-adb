import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CHECKSUMS = load("checksums", "packaging/common/generate_checksums.py")
VERIFY = load("verify_dist", "packaging/common/verify_dist.py")
ASSETS = load("release_assets", "packaging/common/release_assets.py")


class ReleaseManifestTests(unittest.TestCase):
    def make_package(self, directory, selected=None):
        package = Path(directory) / "sus-companion-1.0.0-rc.1-linux-x86_64"
        resources = package / "_internal"
        for relative in ("app/themes", "app/resources", "docs", "plugins/examples/hello_plugin/assets", "packaging"):
            (resources / relative).mkdir(parents=True, exist_ok=True)
        (package / "sus-companion").write_text("executable", encoding="utf-8")
        (package / "sus-adb").write_text("compatibility launcher", encoding="utf-8")
        (resources / "VERSION").write_text("1.0.0-rc.1\n", encoding="utf-8")
        (resources / "frida").mkdir()
        (resources / "frida/_frida.abi3.so").write_bytes(b"\x7fELF fixture")
        (resources / "frida-17.15.5.dist-info").mkdir()
        (resources / "frida-17.15.5.dist-info/METADATA").write_text("Name: frida\nVersion: 17.15.5\n", encoding="utf-8")
        official_names=("device_rescue_recovery","rootability_advisor","webview_security_inspector","skeleton_module","frida_tutorial","objection_tutorial")
        for folder,plugin_id in zip(official_names,VERIFY.OFFICIAL_IDS):
            target=resources/"plugins/official"/folder;target.mkdir(parents=True,exist_ok=True);(target/"manifest.json").write_text(json.dumps({"plugin_id":plugin_id,"enabled":False,"requested_capabilities":VERIFY.OFFICIAL_CAPABILITIES[plugin_id]}),encoding="utf-8");(target/"plugin.py").write_text("class Plugin: pass",encoding="utf-8")
        (resources / "app/themes/gothic.json").write_text("{}", encoding="utf-8")
        (resources / "app/resources/startup_tips.json").write_text('{"format":1,"tips":["A local packaged startup tip long enough for validation."]}', encoding="utf-8")
        (resources / "docs/README.md").write_text("docs", encoding="utf-8")
        manifest = {"enabled": False, "contributed_components": [{"contribution_type": "script-asset"}]}
        (resources / "plugins/examples/hello_plugin/manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        for relative in VERIFY.EXAMPLE_ASSETS:
            (resources / relative).write_text("harmless example", encoding="utf-8")
        selected = selected or {name: () for name in ASSETS.CATEGORIES}
        report = ASSETS.asset_report(selected)
        (resources / "packaging/curated-script-assets.json").write_text(json.dumps(report), encoding="utf-8")
        for paths in selected.values():
            for relative in paths:
                target = resources / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("reviewed fixture", encoding="utf-8")
        CHECKSUMS.generate(package)
        return package

    def test_required_resources_and_spec_are_portable(self):
        required = (
            "VERSION", "packaging/pyinstaller/sus_adb.spec",
            "packaging/common/release_assets.py", "packaging/linux/build_linux.sh",
            "packaging/windows/build_windows.ps1", "release/RC1_CHECKLIST.md",
        )
        self.assertTrue(all((ROOT / item).exists() for item in required))
        text = (ROOT / "packaging/pyinstaller/sus_adb.spec").read_text()
        self.assertNotIn("/home/", text)
        self.assertNotIn("C:\\Users\\", text)
        self.assertIn("collect_all('frida')", text)
        self.assertIn("copy_metadata('frida')", text)

    def test_frida_runtime_metadata_native_component_and_manifest_are_required(self):
        with tempfile.TemporaryDirectory() as directory:
            package = self.make_package(directory)
            manifest = json.loads((package / "release-manifest.json").read_text(encoding="utf-8"))
            listed = {entry["path"] for entry in manifest["files"]}
            self.assertIn("_internal/frida/_frida.abi3.so", listed)
            self.assertIn("_internal/frida-17.15.5.dist-info/METADATA", listed)
            self.assertTrue(VERIFY.verify(package)["ok"])
            (package / "_internal/frida/_frida.abi3.so").unlink()
            CHECKSUMS.generate(package)
            self.assertIn("frida native runtime (*.so)", VERIFY.verify(package)["missing"])

    def test_windows_frida_native_component_is_platform_appropriate(self):
        with tempfile.TemporaryDirectory() as directory:
            package = self.make_package(directory)
            windows = package.with_name("sus-companion-1.0.0-rc.1-windows-amd64")
            package.rename(windows)
            (windows / "sus-companion").rename(windows / "sus-companion.exe")
            (windows / "sus-adb").rename(windows / "sus-adb.cmd")
            native = windows / "_internal/frida/_frida.abi3.so"
            native.rename(native.with_suffix(".pyd"))
            CHECKSUMS.generate(windows)
            self.assertTrue(VERIFY.verify(windows)["ok"], VERIFY.verify(windows))

    def test_checksum_helper(self):
        with tempfile.TemporaryDirectory() as directory:
            artifact = Path(directory) / "artifact"
            artifact.write_bytes(b"abc")
            manifest = CHECKSUMS.generate(Path(directory))
            CHECKSUMS.generate(Path(directory))
            self.assertEqual(manifest["files"][0]["path"], "artifact")
            self.assertEqual(len(manifest["files"]), 1)
            self.assertTrue((Path(directory) / "SHA256SUMS").exists())

    def test_zero_curated_assets_passes_and_reports_categories(self):
        with tempfile.TemporaryDirectory() as directory:
            result = VERIFY.verify(self.make_package(directory))
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["assets"]["core_curated_script_studio_assets"]["count"], 0)
            self.assertEqual(result["assets"]["example_plugin_assets"]["count"], 2)
            self.assertEqual(result["assets"]["user_local_script_studio_assets"], {"count": 0, "packaged": False})
            self.assertEqual(result["assets"]["official_bundled_plugins"]["count"], 6)
            self.assertEqual(result["assets"]["installed_third_party_plugins"], {"count": 0, "packaged": False})

    def test_fixture_curated_assets_are_required_and_counted(self):
        selected = {name: () for name in ASSETS.CATEGORIES}
        selected["frida"] = ("scripts/frida/reviewed.js",)
        selected["profiles"] = ("scripts/profiles/reviewed.json",)
        with tempfile.TemporaryDirectory() as directory:
            package = self.make_package(directory, selected)
            result = VERIFY.verify(package)
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["assets"]["core_curated_script_studio_assets"]["count"], 2)
            (package / "_internal/scripts/frida/reviewed.js").unlink()
            CHECKSUMS.generate(package)
            self.assertFalse(VERIFY.verify(package)["ok"])

    def test_selection_uses_only_tracked_safe_assets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reviewed = root / "scripts/frida/reviewed.js"
            local = root / "scripts/frida/local-only.js"
            cached = root / "scripts/frida/__pycache__/cached.pyc"
            private = root / "scripts/frida/custom/flutter_popup_bypass.js"
            for item in (reviewed, local, cached, private):
                item.parent.mkdir(parents=True, exist_ok=True)
                item.write_text("fixture", encoding="utf-8")
            tracked = (
                "scripts/frida/reviewed.js", "scripts/frida/__pycache__/cached.pyc",
                "scripts/frida/custom/flutter_popup_bypass.js",
            )
            selected = ASSETS.select_curated_assets(root, tracked)
            self.assertEqual(selected["frida"], ("scripts/frida/reviewed.js",))
            self.assertNotIn("scripts/frida/local-only.js", selected["frida"])
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);tracked=root/"plugins/official/demo/manifest.json";local=root/"plugins/official/demo/local.log";tracked.parent.mkdir(parents=True);tracked.write_text("{}");local.write_text("private")
            self.assertEqual(ASSETS.select_official_plugins(root,("plugins/official/demo/manifest.json",)),("plugins/official/demo/manifest.json",))

    def test_example_assets_private_drafts_caches_and_required_resources(self):
        with tempfile.TemporaryDirectory() as directory:
            package = self.make_package(directory)
            resources = package / "_internal"
            (resources / VERIFY.EXAMPLE_ASSETS[0]).unlink()
            CHECKSUMS.generate(package)
            self.assertIn(VERIFY.EXAMPLE_ASSETS[0], VERIFY.verify(package)["missing"])
        for relative in ("scripts/frida/custom/flutter_popup_bypass.js", "cache/__pycache__/item.pyc"):
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as directory:
                package = self.make_package(directory)
                suspect = package / "_internal" / relative
                suspect.parent.mkdir(parents=True, exist_ok=True)
                suspect.write_text("fixture", encoding="utf-8")
                CHECKSUMS.generate(package)
                self.assertFalse(VERIFY.verify(package)["ok"])
        with tempfile.TemporaryDirectory() as directory:
            package = self.make_package(directory)
            (package / "_internal/VERSION").unlink()
            CHECKSUMS.generate(package)
            self.assertIn("VERSION", VERIFY.verify(package)["missing"])


if __name__ == "__main__":
    unittest.main()
