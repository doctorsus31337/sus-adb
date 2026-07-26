# SUS Companion branding assets

These are user-selected SUS Companion branding assets.

- `source/sus-companion-app-icon-source.jpg` is the source for application,
  executable, launcher, and window icons.
- `source/sus-companion-header-source.jpg` is the source for the compact main
  header emblem.
- `source/sus-companion-about-source.jpg` is the source for About-window
  artwork.

The source files preserve the selected artwork pixels while omitting ancillary
metadata. Their original `.png` filenames did not match their actual JPEG
format, so the repository uses accurate `.jpg` extensions. The generator's
marker-level sanitizer can verify and remove metadata without JPEG
recompression.

Run `python scripts/generate_branding_assets.py` to reproduce the packaged
runtime assets. Use `--sanitize-sources` only when reviewing tracked source
assets. Tracked source and generated runtime files contain no EXIF, XMP,
comments, or private metadata. The generator verifies the reviewed source
hashes before writing derivatives.
