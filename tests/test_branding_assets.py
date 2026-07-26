import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "generate_branding_assets",
    ROOT / "scripts/generate_branding_assets.py",
)
GENERATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GENERATOR)


class BrandingAssetTests(unittest.TestCase):
    def test_exact_reviewed_sources_are_present_and_unchanged(self):
        source = ROOT / "assets/branding/source"
        self.assertEqual(
            {path.name for path in source.iterdir() if path.is_file()},
            set(GENERATOR.SOURCE_FILES.values()),
        )
        for key, filename in GENERATOR.SOURCE_FILES.items():
            path = source / filename
            self.assertEqual(
                hashlib.sha256(path.read_bytes()).hexdigest(),
                GENERATOR.EXPECTED_SOURCE_HASHES[key],
            )
            with Image.open(path) as image:
                self.assertEqual(image.format, "JPEG")
                self.assertEqual(image.size, (784, 1168))
                self.assertEqual(image.mode, "RGB")
                self.assertFalse(image.getexif())
                self.assertFalse(
                    {"exif", "xmp", "comment", "photoshop"}
                    & set(image.info)
                )
            self.assertEqual(
                GENERATOR.sanitize_jpeg_metadata(path.read_bytes()),
                path.read_bytes(),
            )

    def test_marker_sanitizer_preserves_scan_and_decoded_pixels(self):
        source = (
            ROOT
            / "assets/branding/source/sus-companion-app-icon-source.jpg"
        ).read_bytes()
        metadata = (
            b"\xff\xe1\x00\x16Exif\x00\x00synthetic-only"
            b"\xff\xfe\x00\x0bcomment!!"
        )
        decorated = source[:2] + metadata + source[2:]
        sanitized = GENERATOR.sanitize_jpeg_metadata(decorated)
        self.assertEqual(sanitized, source)
        with tempfile.TemporaryDirectory() as directory:
            decorated_path = Path(directory) / "decorated.jpg"
            sanitized_path = Path(directory) / "sanitized.jpg"
            decorated_path.write_bytes(decorated)
            sanitized_path.write_bytes(sanitized)
            self.assertEqual(
                GENERATOR._pixel_digest(decorated_path),
                GENERATOR._pixel_digest(sanitized_path),
            )
        self.assertEqual(GENERATOR.sanitize_jpeg_metadata(sanitized), sanitized)

    def test_marker_sanitizer_rejects_malformed_jpeg(self):
        for value in (
            b"not-jpeg",
            b"\xff\xd8\xff\xe1\x00\x01\xff\xd9",
            b"\xff\xd8\xff\xda\x00\x08truncated",
        ):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    GENERATOR.sanitize_jpeg_metadata(value)

    def test_runtime_formats_dimensions_metadata_and_ico_frames(self):
        runtime = ROOT / "assets/branding/runtime"
        for size in GENERATOR.ICON_SIZES:
            with Image.open(runtime / f"sus-companion-icon-{size}.png") as image:
                self.assertEqual(image.format, "PNG")
                self.assertEqual(image.size, (size, size))
                self.assertFalse(image.getexif())
        with Image.open(runtime / "sus-companion-header.png") as image:
            self.assertEqual(image.format, "PNG")
            self.assertEqual(image.size, GENERATOR.HEADER_SIZE)
            self.assertFalse(image.getexif())
        with Image.open(runtime / "sus-companion-about.png") as image:
            self.assertEqual(image.format, "PNG")
            self.assertEqual(image.size, GENERATOR.ABOUT_SIZE)
            self.assertAlmostEqual(
                image.width / image.height,
                784 / 1168,
                places=3,
            )
            self.assertFalse(image.getexif())
        with Image.open(runtime / "sus-companion.ico") as image:
            self.assertEqual(image.format, "ICO")
            self.assertEqual(set(image.info["sizes"]), {
                (size, size) for size in GENERATOR.ICO_SIZES
            })

    def test_generation_is_deterministic_and_never_writes_sources(self):
        source = ROOT / "assets/branding/source"
        before = {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in source.iterdir() if path.is_file()
        }
        committed = ROOT / "assets/branding/runtime"
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            first = GENERATOR.generate(ROOT, output_directory=output)
            first_bytes = {
                path.name: path.read_bytes() for path in output.iterdir()
            }
            second = GENERATOR.generate(ROOT, output_directory=output)
            self.assertEqual(first, second)
            self.assertEqual(
                first_bytes,
                {path.name: path.read_bytes() for path in output.iterdir()},
            )
            for path in output.iterdir():
                self.assertEqual(path.read_bytes(), (committed / path.name).read_bytes())
        after = {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in source.iterdir() if path.is_file()
        }
        self.assertEqual(before, after)

    def test_runtime_manifest_has_no_local_paths_or_timestamps(self):
        manifest = json.loads(
            (ROOT / "assets/branding/runtime/manifest.json").read_text(
                encoding="utf-8"
            )
        )
        rendered = json.dumps(manifest, sort_keys=True)
        self.assertNotIn("/" + "ho" + "me/", rendered)
        self.assertNotIn("timestamp", rendered.casefold())
        self.assertEqual(manifest["format"], 1)


if __name__ == "__main__":
    unittest.main()
