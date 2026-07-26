# SUS Companion branding assets

These are user-selected SUS Companion branding assets.

- `source/sus-companion-app-icon-source.jpg` is the source for application,
  executable, launcher, and window icons.
- `source/sus-companion-header-source.jpg` is the source for the compact main
  header emblem.
- `source/sus-companion-about-source.jpg` is the source for About-window
  artwork.

The source files are faithful copies of the selected artwork. Their original
`.png` filenames did not match their actual JPEG format, so the repository
uses accurate `.jpg` extensions.

Run `python scripts/generate_branding_assets.py` to reproduce the packaged
runtime assets. Generated PNG and ICO files contain no source EXIF metadata.
The generator verifies the reviewed source hashes before writing derivatives.
