#!/bin/sh
set -eu
package_name="sus-companion-1.0.0-rc.4-linux-$(uname -m)"
python packaging/common/generate_build_info.py build/packaging/build-info.json
SUS_ADB_PACKAGE_NAME="$package_name" python -m PyInstaller --clean --noconfirm packaging/pyinstaller/sus_adb.spec
printf '%s\n' '#!/bin/sh' 'exec "$(dirname "$0")/sus-companion" "$@"' > "dist/$package_name/sus-adb"
chmod 755 "dist/$package_name/sus-adb"
cp assets/branding/runtime/sus-companion-icon-256.png "dist/$package_name/sus-companion.png"
python packaging/common/generate_checksums.py "dist/$package_name"
python packaging/common/verify_dist.py "dist/$package_name" --output "dist/$package_name-verification-report.json"
cp build/packaging/build-info.json "dist/$package_name-build-info.json"
python scripts/audit_release.py --tree "dist/$package_name"
cp "dist/$package_name/release-manifest.json" "dist/$package_name-release-manifest.json"
cp "dist/$package_name/SHA256SUMS" "dist/$package_name-SHA256SUMS"
tar -czf "dist/$package_name.tar.gz" -C dist "$package_name"
archive_hash=$(sha256sum "dist/$package_name.tar.gz" | cut -d ' ' -f 1)
printf '%s  %s\n' "$archive_hash" "$package_name.tar.gz" > "dist/$package_name.tar.gz.sha256"
