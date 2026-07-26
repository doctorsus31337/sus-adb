import tempfile
import tkinter as tk
import sys
import unittest
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


ROOT = Path(__file__).parents[1]


class FakeWindow:
    def __init__(self):
        self.calls = []

    def iconphoto(self, default, image):
        self.calls.append((default, image))


class BrandingIntegrationTests(unittest.TestCase):
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
        for value in (spec, linux, desktop, verifier):
            self.assertNotIn("/home/" + "doctorsus", value)
        self.assertIn("assets/branding/runtime", spec)
        self.assertIn("sus-companion.ico", spec)
        self.assertIn("sus-companion-icon-256.png", linux)
        self.assertIn("Icon=sus-companion", desktop)
        self.assertIn("BRANDING_REQUIRED", verifier)


if __name__ == "__main__":
    unittest.main()
