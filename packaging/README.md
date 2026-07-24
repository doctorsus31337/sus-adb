# SUS Companion Packaging

One-directory packages use `sus-companion` as the preferred executable. Linux adds a small `sus-adb` launcher and Windows adds `sus-adb.cmd`; neither duplicates the application resource bundle. The established storage directories remain unchanged.

The packaged startup tip catalog is local data, and the release verifier requires it alongside centralized build metadata, themes, documentation, official addons, Python Frida runtime resources, manifests, checksums, and a verification report.

RC1 uses a PyInstaller one-folder build. Run the platform script from a clean checkout or `git archive` source after installing `requirements-build.txt`. `generate_build_info.py` records the product version, exact commit, selected ref when supplied, UTC build timestamp, and build channel before PyInstaller collects resources. Builds include required application resources, the disabled hello example plugin, and disabled official educational addons. RC1 currently has zero reviewed core curated Script Studio assets; when reviewed assets are tracked, packaging includes and verifies only those release-approved files. Mutable user-local Script Studio libraries are never package inputs.

Verification reports core curated, example-plugin, official-addon, and user-local asset counts separately. Packages exclude cases, evidence, logs, installed plugins, plugin state, local configuration, local scripts, recovered data, private drafts, caches, bytecode, generated input artifacts, APK/PCAP/database files, credentials, keys, tokens, and secrets. The manual current-testing workflow uploads artifacts only; binary signing, installers, tags, and GitHub Releases are intentionally separate later operations.
