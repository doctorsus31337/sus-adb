$ErrorActionPreference = "Stop"
$packageName = "sus-companion-1.0.0-rc.1-windows-$env:PROCESSOR_ARCHITECTURE".ToLowerInvariant()
python packaging/common/generate_build_info.py build/packaging/build-info.json
$env:SUS_ADB_PACKAGE_NAME = $packageName
python -m PyInstaller --clean --noconfirm packaging/pyinstaller/sus_adb.spec
Set-Content -Path "dist/$packageName/sus-adb.cmd" -Encoding Ascii -Value '@echo off', '"%~dp0sus-companion.exe" %*'
python packaging/common/generate_checksums.py "dist/$packageName"
python packaging/common/verify_dist.py "dist/$packageName" --output "dist/$packageName-verification-report.json"
Copy-Item build/packaging/build-info.json "dist/$packageName-build-info.json"
python scripts/audit_release.py --tree "dist/$packageName"
