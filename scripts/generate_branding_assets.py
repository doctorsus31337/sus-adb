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
    "app_icon": "f72293471a93768ab7fd779e4775b1fc7a629b84119a6dd6f74cd9a114fda0bd",
    "header": "99d81e6a14db5ecbb4fd20cd4935383a2b322c1266d42d0d9962f338c5c67d4b",
    "about": "001f0babc99edb477790af06c58df5779305419532f7c95dd22faf42b6b41c27",
}
ICON_SIZES = (1024, 512, 256, 128, 64, 48, 32, 16)
ICO_SIZES = (16, 32, 48, 64, 128, 256)
HEADER_CROP = (220, 140, 564, 484)
HEADER_SIZE = (256, 256)
ABOUT_SIZE = (392, 584)
_STANDALONE_MARKERS = frozenset((0x01, *range(0xD0, 0xD8), 0xD8, 0xD9))


def _keep_application_segment(marker: int, payload: bytes) -> bool:
    if marker == 0xE0:
        return payload.startswith((b"JFIF\x00", b"JFXX\x00"))
    if marker == 0xE2:
        return payload.startswith(b"ICC_PROFILE\x00")
    if marker == 0xEE:
        return payload.startswith(b"Adobe")
    return not (0xE0 <= marker <= 0xEF or marker == 0xFE)


def sanitize_jpeg_metadata(data: bytes) -> bytes:
    """Remove JPEG metadata markers without recompressing entropy-coded scans."""
    if len(data) < 4 or data[:2] != b"\xff\xd8":
        raise ValueError("Branding source is not a JPEG stream")
    output = bytearray(data[:2])
    position = 2
    saw_eoi = False
    while position < len(data):
        marker_start = position
        if data[position] != 0xFF:
            raise ValueError("Expected a JPEG marker boundary")
        while position < len(data) and data[position] == 0xFF:
            position += 1
        if position >= len(data):
            raise ValueError("Truncated JPEG marker")
        marker = data[position]
        position += 1
        if marker == 0x00:
            raise ValueError("Unexpected stuffed byte outside a JPEG scan")
        if marker in _STANDALONE_MARKERS:
            output.extend(data[marker_start:position])
            if marker == 0xD9:
                saw_eoi = True
                if position != len(data):
                    raise ValueError("Unexpected data after JPEG end marker")
                break
            if marker == 0xD8:
                raise ValueError("Unexpected nested JPEG start marker")
            continue
        if position + 2 > len(data):
            raise ValueError("Truncated JPEG segment length")
        segment_length = int.from_bytes(data[position:position + 2], "big")
        if segment_length < 2:
            raise ValueError("Invalid JPEG segment length")
        segment_end = position + segment_length
        if segment_end > len(data):
            raise ValueError("JPEG segment exceeds input")
        payload = data[position + 2:segment_end]
        if _keep_application_segment(marker, payload):
            output.extend(data[marker_start:segment_end])
        position = segment_end
        if marker != 0xDA:
            continue
        scan_start = position
        while position < len(data):
            marker_prefix = data.find(b"\xff", position)
            if marker_prefix < 0:
                raise ValueError("JPEG scan has no terminating marker")
            candidate = marker_prefix + 1
            while candidate < len(data) and data[candidate] == 0xFF:
                candidate += 1
            if candidate >= len(data):
                raise ValueError("Truncated marker after JPEG scan")
            scan_marker = data[candidate]
            if scan_marker == 0x00 or 0xD0 <= scan_marker <= 0xD7:
                position = candidate + 1
                continue
            output.extend(data[scan_start:marker_prefix])
            position = marker_prefix
            break
    if not saw_eoi:
        raise ValueError("JPEG stream has no end marker")
    return bytes(output)


def _pixel_digest(path: Path) -> tuple[tuple[int, int], str, str]:
    with Image.open(path) as image:
        image.load()
        rgb = image.convert("RGB")
        return rgb.size, rgb.mode, hashlib.sha256(rgb.tobytes()).hexdigest()


def sanitize_source(path: Path) -> bool:
    """Atomically sanitize one source after proving decoded pixels are unchanged."""
    before = _pixel_digest(path)
    original = path.read_bytes()
    sanitized = sanitize_jpeg_metadata(original)
    if sanitized == original:
        return False
    temporary = path.with_suffix(path.suffix + ".sanitizing")
    try:
        temporary.write_bytes(sanitized)
        if _pixel_digest(temporary) != before:
            raise RuntimeError("Sanitized branding source changed decoded pixels")
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return True


def sanitize_sources(repository_root: Path) -> tuple[str, ...]:
    source_directory = Path(repository_root).resolve() / "assets/branding/source"
    return tuple(
        filename
        for filename in SOURCE_FILES.values()
        if sanitize_source(source_directory / filename)
    )


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
    parser.add_argument(
        "--sanitize-sources",
        action="store_true",
        help="Remove metadata markers from the reviewed tracked JPEG sources.",
    )
    args = parser.parse_args()
    if args.sanitize_sources:
        sanitize_sources(args.root)
    generate(args.root, output_directory=args.output_directory)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
