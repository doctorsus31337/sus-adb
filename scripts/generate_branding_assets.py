"""Generate deterministic, metadata-free SUS Companion runtime branding assets."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image


SOURCE_FILES = {
    "app_icon": "sus-companion-app-icon-source.jpg",
    "header": "sus-companion-header-source.jpg",
    "about": "sus-companion-about-source.jpg",
}
EXPECTED_SOURCE_HASHES = {
    "app_icon": "30dd1ab014c265c9be882e542ca936c7df9598c390e76f52e4fae27381d43b34",
    "header": "297c150aff6f92d080626dd0d67a2e75522a64294720737b408ff196ab8c5ebd",
    "about": "ac2c8919574fd0d8a184ec004a691c6df9226543483b4f59a3b58530bb2f3d89",
}
ICON_SIZES = (1024, 512, 256, 128, 64, 48, 32, 16)
ICO_SIZES = (16, 32, 48, 64, 128, 256)
HEADER_CROP = (220, 140, 564, 484)
HEADER_SIZE = (256, 256)
ABOUT_SIZE = (392, 584)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _save_png(image: Image.Image, path: Path) -> None:
    image.convert("RGBA").save(
        path,
        format="PNG",
        optimize=False,
        compress_level=9,
    )


def _open_rgb(path: Path) -> Image.Image:
    with Image.open(path) as source:
        source.load()
        return source.convert("RGB")


def generate(
    repository_root: Path,
    *,
    output_directory: Path | None = None,
) -> dict:
    repository_root = Path(repository_root).resolve()
    source_directory = repository_root / "assets/branding/source"
    output_directory = (
        Path(output_directory).resolve()
        if output_directory is not None
        else repository_root / "assets/branding/runtime"
    )
    output_directory.mkdir(parents=True, exist_ok=True)

    source_paths = {
        key: source_directory / filename for key, filename in SOURCE_FILES.items()
    }
    source_hashes = {key: _digest(path) for key, path in source_paths.items()}
    if source_hashes != EXPECTED_SOURCE_HASHES:
        raise RuntimeError("Branding source assets differ from the reviewed source hashes")

    icon_source = _open_rgb(source_paths["app_icon"])
    crop_side = min(icon_source.size)
    icon_top = (icon_source.height - crop_side) // 2
    icon_master = icon_source.crop((0, icon_top, crop_side, icon_top + crop_side))
    icon_master = icon_master.resize((1024, 1024), Image.Resampling.LANCZOS)
    output_records = {}
    for size in ICON_SIZES:
        filename = f"sus-companion-icon-{size}.png"
        target = output_directory / filename
        derivative = icon_master.resize((size, size), Image.Resampling.LANCZOS)
        _save_png(derivative, target)
        output_records[filename] = {
            "format": "PNG",
            "size": [size, size],
            "sha256": _digest(target),
        }

    ico_name = "sus-companion.ico"
    ico_path = output_directory / ico_name
    icon_master.save(
        ico_path,
        format="ICO",
        sizes=[(size, size) for size in ICO_SIZES],
    )
    output_records[ico_name] = {
        "format": "ICO",
        "sizes": list(ICO_SIZES),
        "sha256": _digest(ico_path),
    }

    header_source = _open_rgb(source_paths["header"])
    header = header_source.crop(HEADER_CROP).resize(
        HEADER_SIZE, Image.Resampling.LANCZOS
    )
    header_name = "sus-companion-header.png"
    header_path = output_directory / header_name
    _save_png(header, header_path)
    output_records[header_name] = {
        "format": "PNG",
        "size": list(HEADER_SIZE),
        "source_crop": list(HEADER_CROP),
        "sha256": _digest(header_path),
    }

    about_source = _open_rgb(source_paths["about"])
    about = about_source.resize(ABOUT_SIZE, Image.Resampling.LANCZOS)
    about_name = "sus-companion-about.png"
    about_path = output_directory / about_name
    _save_png(about, about_path)
    output_records[about_name] = {
        "format": "PNG",
        "size": list(ABOUT_SIZE),
        "sha256": _digest(about_path),
    }

    manifest = {
        "format": 1,
        "generator": "scripts/generate_branding_assets.py",
        "sources": {
            SOURCE_FILES[key]: {
                "format": "JPEG",
                "size": [784, 1168],
                "sha256": source_hashes[key],
            }
            for key in ("app_icon", "header", "about")
        },
        "outputs": dict(sorted(output_records.items())),
    }
    manifest_path = output_directory / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument("--output-directory", type=Path)
    args = parser.parse_args()
    generate(args.root, output_directory=args.output_directory)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
