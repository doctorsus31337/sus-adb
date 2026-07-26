import builtins
import importlib.util
import io
import tempfile
import tkinter as tk
import sys
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock

from app.core.branding_assets import (
    ABOUT_ARTWORK,
    APP_ICON_PNG,
    HEADER_ARTWORK,
    BrandingAssetResolver,
    application_resource_root,
)
from app.gui.branding_images import BrandingImages
from app.core import branding_dependencies


ROOT = Path(__file__).parents[1]
UPDATE_COMMAND = "python -m pip install -r requirements.txt -c constraints.txt"


def missing_pillow_import(name, globals=None, locals=None, fromlist=(), level=0):
    if name == "PIL" or name.startswith("PIL."):
        raise ModuleNotFoundError("No module named 'PIL'", name="PIL")
    return _REAL_IMPORT(name, globals, locals, fromlist, level)


_REAL_IMPORT = builtins.__import__


class FakeWindow:
    def __init__(self):
        self.calls = []

    def iconphoto(self, default, image):
        self.calls.append((default, image))


class BrandingIntegrationTests(unittest.TestCase):
    def setUp(self):
        branding_dependencies._reset_notice_for_tests()

    def test_branding_module_imports_when_pillow_is_unavailable(self):
        spec = importlib.util.spec_from_file_location(
            "branding_images_without_pillow",
            ROOT / "app/gui/branding_images.py",
        )
        module = importlib.util.module_from_spec(spec)
        with mock.patch("builtins.__import__", side_effect=missing_pillow_import):
            spec.loader.exec_module(module)
        self.assertTrue(hasattr(module, "BrandingImages"))

    def test_missing_pillow_is_once_only_actionable_safe_noop(self):
        stderr = io.StringIO()
        window = FakeWindow()
        images = BrandingImages(BrandingAssetResolver(ROOT))
        with (
            mock.patch("builtins.__import__", side_effect=missing_pillow_import),
            mock.patch("app.gui.branding_images.tk.PhotoImage") as photo_image,
            redirect_stderr(stderr),
        ):
            self.assertIsNone(images.pil_image(HEADER_ARTWORK))
            self.assertIsNone(images.ctk_image(ABOUT_ARTWORK, (230, 343)))
            self.assertFalse(images.apply_window_icon(window))
            self.assertFalse(images.apply_window_icon(window))
        message = stderr.getvalue()
        self.assertIn(UPDATE_COMMAND, message)
        self.assertEqual(message.count("Optional visual branding"), 1)
        photo_image.assert_not_called()
        self.assertEqual(window.calls, [])

    def test_unrelated_pillow_import_failure_propagates(self):
        def unrelated(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "PIL":
                raise ModuleNotFoundError(
                    "No module named 'unrelated'",
                    name="unrelated",
                )
            return _REAL_IMPORT(name, globals, locals, fromlist, level)
        images = BrandingImages(BrandingAssetResolver(ROOT))
        with (
            mock.patch("builtins.__import__", side_effect=unrelated),
            self.assertRaises(ModuleNotFoundError),
        ):
            images.pil_image(HEADER_ARTWORK)
    def test_resolver_works_in_checkout_bundle_and_paths_with_spaces(self):
        checkout = BrandingAssetResolver(ROOT)
        self.assertTrue(checkout.resolve(APP_ICON_PNG).is_file())
        with tempfile.TemporaryDirectory(prefix="SUS Companion bundle ") as directory:
            root = Path(directory)
            runtime = root / "assets/branding/runtime"
            runtime.mkdir(parents=True)
            for filename in (APP_ICON_PNG, HEADER_ARTWORK, ABOUT_ARTWORK):
                (runtime / filename).write_bytes(
                    (ROOT / "assets/branding/runtime" / filename).read_bytes()
                )
            resolver = BrandingAssetResolver(root)
            self.assertTrue(resolver.resolve(APP_ICON_PNG).is_file())
            self.assertIn("SUS Companion bundle ", str(resolver.resolve(HEADER_ARTWORK)))
            self.assertIsNone(resolver.resolve("../source.jpg"))
            with mock.patch.object(sys, "_MEIPASS", str(root), create=True):
                self.assertEqual(application_resource_root(), root)

    def test_missing_and_corrupt_images_fail_to_text_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = root / "assets/branding/runtime"
            runtime.mkdir(parents=True)
            images = BrandingImages(BrandingAssetResolver(root))
            self.assertIsNone(images.pil_image(ABOUT_ARTWORK))
            (runtime / ABOUT_ARTWORK).write_bytes(b"not an image")
            fresh = BrandingImages(BrandingAssetResolver(root))
            self.assertIsNone(fresh.pil_image(ABOUT_ARTWORK))

    def test_image_cache_loads_each_runtime_artwork_once(self):
        images = BrandingImages(BrandingAssetResolver(ROOT))
        first = images.pil_image(HEADER_ARTWORK)
        second = images.pil_image(HEADER_ARTWORK)
        self.assertIs(first, second)
        self.assertEqual(first.size, (256, 256))

    @mock.patch("app.gui.branding_images.tk.PhotoImage")
    def test_window_icon_is_loaded_once_retained_and_reused(self, photo_image):
        icon = object()
        photo_image.return_value = icon
        images = BrandingImages(BrandingAssetResolver(ROOT))
        first, second = FakeWindow(), FakeWindow()
        self.assertTrue(images.apply_window_icon(first, default=True))
        self.assertTrue(images.apply_window_icon(second))
        photo_image.assert_called_once()
        self.assertIs(first._sus_companion_icon_image, icon)
        self.assertIs(second._sus_companion_icon_image, icon)
        self.assertEqual(first.calls, [(True, icon)])
        self.assertEqual(second.calls, [(False, icon)])

    @mock.patch("app.gui.branding_images.tk.PhotoImage", side_effect=Exception)
    def test_unrelated_icon_errors_are_not_broadly_suppressed(self, _photo_image):
        images = BrandingImages(BrandingAssetResolver(ROOT))
        with self.assertRaises(Exception):
            images.apply_window_icon(FakeWindow())

    @mock.patch(
        "app.gui.branding_images.tk.PhotoImage",
        side_effect=tk.TclError("corrupt PNG fixture"),
    )
    def test_corrupt_window_icon_falls_back_without_startup_failure(self, _photo_image):
        images = BrandingImages(BrandingAssetResolver(ROOT))
        self.assertFalse(images.apply_window_icon(FakeWindow()))

    def test_packaging_and_docs_use_portable_runtime_assets(self):
        spec = (ROOT / "packaging/pyinstaller/sus_adb.spec").read_text()
        linux = (ROOT / "packaging/linux/build_linux.sh").read_text()
        desktop = (ROOT / "packaging/linux/sus-adb.desktop").read_text()
        verifier = (ROOT / "packaging/common/verify_dist.py").read_text()
        requirements = (ROOT / "requirements.txt").read_text()
        constraints = (ROOT / "constraints.txt").read_text()
        installation = (ROOT / "docs/installation.md").read_text()
        readme = (ROOT / "README.md").read_text()
        for value in (spec, linux, desktop, verifier):
            self.assertNotIn("/" + "ho" + "me/", value)
        self.assertIn("assets/branding/runtime", spec)
        self.assertIn("sus-companion.ico", spec)
        self.assertIn("sus-companion-icon-256.png", linux)
        self.assertIn("Icon=sus-companion", desktop)
        self.assertIn("BRANDING_REQUIRED", verifier)
        self.assertIn("copy_metadata('pillow')", spec)
        self.assertIn("pillow>=10,<13", requirements)
        self.assertIn("pillow<13", constraints)
        self.assertIn(UPDATE_COMMAND, installation)
        self.assertIn(UPDATE_COMMAND, readme)


if __name__ == "__main__":
    unittest.main()
