#!/bin/sh
set -eu
package_name="sus-adb-1.0.0-rc.1-linux-$(uname -m)"
SUS_ADB_PACKAGE_NAME="$package_name" python -m PyInstaller --clean --noconfirm packaging/pyinstaller/sus_adb.spec
python packaging/common/generate_checksums.py "dist/$package_name"
python packaging/common/verify_dist.py "dist/$package_name"
python scripts/audit_release.py --tree "dist/$package_name"
