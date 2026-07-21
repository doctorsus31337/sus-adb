import contextlib
import importlib.util
import io
import runpy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).parents[1]


def load_audit():
    path = ROOT / "scripts/audit_release.py"
    spec = importlib.util.spec_from_file_location("audit_release", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


AUDIT = load_audit()


class ReleaseAuditTests(unittest.TestCase):
    def audit_files(self, files):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative, content in files.items():
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
            return AUDIT.audit_tree(root)

    def test_compiled_runtime_binaries_ignore_toolchain_paths(self):
        binary = b"\x7fELF\0compiled\0/home/runner/work/project\0"
        files = {
            "_internal/libpython3.11.so.1.0": binary,
            "_internal/runtime.dll": b"MZ\0C:\\hostedtoolcache\\windows\0",
            "_internal/extension.pyd": binary,
            "sus-adb.exe": b"MZ\0/home/runner/work/project\0",
        }
        self.assertEqual(self.audit_files(files), ())

    def test_private_paths_and_private_key_in_text_still_block(self):
        findings = self.audit_files({
            "settings.conf": b"root=/home/doctorsus/.Projects/sus-adb\n",
            "metadata.json": b'{"source":"C:\\Users\\developer\\project"}',
            "notes.txt": b"-----BEGIN OPENSSH PRIVATE KEY-----\nfixture",
        })
        self.assertEqual(findings, (
            ("metadata.json", "developer-home"),
            ("notes.txt", "private-key"),
            ("settings.conf", "developer-home"),
        ))

    def test_forbidden_binary_artifacts_block_by_path(self):
        names = ("signing.keystore", "release.apk", "traffic.pcap", "case.sqlite3")
        findings = self.audit_files({name: b"\0binary" for name in names})
        self.assertEqual({path for path, _ in findings}, set(names))
        self.assertTrue(all(rule == "generated-artifact" for _, rule in findings))

    def test_caches_bytecode_and_private_drafts_block_by_path(self):
        findings = self.audit_files({
            "pkg/__pycache__/module.pyc": b"",
            "pkg/module.pyo": b"",
            "docs/private-release-draft.md": b"",
        })
        self.assertEqual({rule for _, rule in findings}, {"generated-artifact", "private-draft"})

    def test_malformed_utf8_text_is_safe_and_blocks(self):
        self.assertEqual(self.audit_files({"metadata.json": b'{"bad":"\xff"}'}),
                         (("metadata.json", "malformed-text"),))

    def test_large_binary_reads_are_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "large.so"
            target.write_bytes(b"\x7fELF" + b"x" * (AUDIT.READ_SIZE * 3))
            original_open = Path.open
            read_sizes = []

            class Reader:
                def __init__(self, stream):
                    self.stream = stream

                def __enter__(self):
                    return self

                def __exit__(self, *args):
                    self.stream.close()

                def read(self, size=-1):
                    read_sizes.append(size)
                    self.assert_bounded(size)
                    return self.stream.read(size)

                @staticmethod
                def assert_bounded(size):
                    if size < 0 or size > AUDIT.READ_SIZE:
                        raise AssertionError(f"unbounded read: {size}")

            def bounded_open(path, *args, **kwargs):
                return Reader(original_open(path, *args, **kwargs))

            with mock.patch.object(Path, "open", bounded_open):
                self.assertEqual(AUDIT.audit_tree(directory), ())
            self.assertEqual(read_sizes, [AUDIT.SNIFF_SIZE])

    def test_cli_output_contains_only_rule_and_relative_path(self):
        secret = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "settings.txt").write_text(secret, encoding="utf-8")
            output = io.StringIO()
            argv = ["audit_release.py", "--tree", directory]
            with mock.patch.object(sys, "argv", argv), contextlib.redirect_stdout(output):
                with self.assertRaisesRegex(SystemExit, "1"):
                    runpy.run_path(str(ROOT / "scripts/audit_release.py"), run_name="__main__")
            self.assertEqual(output.getvalue(), "BLOCK token: settings.txt\n")
            self.assertNotIn(secret, output.getvalue())

    def test_mixed_fixture_only_genuine_prohibited_files_block(self):
        findings = self.audit_files({
            "_internal/libpython3.11.so.1.0": b"\x7fELF\0/home/runner/work/project\0",
            "_internal/module.so": b"\x7fELF\0/home/runner/.cache/tool\0",
            "config/settings.ini": b"path=/home/doctorsus/.Projects/sus-adb\n",
            "captures/session.pcapng": b"\0capture",
            "build/app.aab": b"PK\x03\x04archive",
        })
        self.assertEqual(findings, (
            ("build/app.aab", "generated-artifact"),
            ("captures/session.pcapng", "generated-artifact"),
            ("config/settings.ini", "developer-home"),
        ))

    def test_official_source_allowed_but_installed_plugin_state_blocks(self):
        findings = self.audit_files({"plugins/official/demo/manifest.json": b"{}", "plugins/installed/demo/plugin.py": b"safe"})
        self.assertEqual(findings, (("plugins/installed/demo/plugin.py", "installed-plugin"),))


if __name__ == "__main__":
    unittest.main()
