# Packaging

RC1 uses a PyInstaller one-folder build. Run the platform script from the repository root after installing `requirements-build.txt`. Builds include curated source resources and exclude cases, evidence, logs, installed plugins, private drafts, APK/PCAP/database artifacts, and secrets. Binary signing and installers are intentionally separate future release operations.
