$ErrorActionPreference = "Stop"
python -m PyInstaller --clean --noconfirm packaging/pyinstaller/sus_adb.spec
python packaging/common/verify_dist.py dist/sus-adb-1.0.0-rc.1
python packaging/common/generate_checksums.py dist/sus-adb-1.0.0-rc.1
