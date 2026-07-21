# SUS Companion Packaging

One-directory packages use `sus-companion` as the preferred executable. Linux adds a small `sus-adb` launcher and Windows adds `sus-adb.cmd`; neither duplicates the application resource bundle. The established storage directories remain unchanged.

The packaged startup tip catalog is local data, and the release verifier requires it alongside centralized metadata, themes, documentation, official addons, Python Frida runtime resources, manifests, and checksums.

RC1 uses a PyInstaller one-folder build. Run the platform script from a clean checkout or `git archive` source after installing `requirements-build.txt`. Builds include required application resources and the disabled hello example plugin. RC1 currently has zero reviewed core curated Script Studio assets; when reviewed assets are tracked, packaging includes and verifies only those release-approved files. Mutable user-local Script Studio libraries are never package inputs.

Verification reports core curated, example-plugin, and user-local asset counts separately. Packages exclude cases, evidence, logs, installed plugins, private drafts, caches, bytecode, generated artifacts, APK/PCAP/database files, and secrets. Binary signing and installers are intentionally separate future release operations.
