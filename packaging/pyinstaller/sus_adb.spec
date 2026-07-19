import os,platform
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files
root=Path(SPEC).resolve().parents[2]
datas=collect_data_files('customtkinter')+[(str(root/'app/themes/gothic.json'),'app/themes'),(str(root/'docs'),'docs'),(str(root/'plugins/examples'),'plugins/examples'),(str(root/'VERSION'),'.')]
for library_root,excluded in ((root/'scripts/frida',{'custom/flutter_popup_bypass.js'}),(root/'scripts/metadata',{'flutter_popup_bypass.meta.json'})):
    for source in sorted(library_root.rglob('*')):
        relative=source.relative_to(library_root)
        if source.is_file() and relative.as_posix() not in excluded:
            datas.append((str(source),str(Path('scripts')/library_root.name/relative.parent)))
a=Analysis([str(root/'main.py')],pathex=[str(root)],binaries=[],datas=datas,hiddenimports=[],hookspath=[str(root/'packaging/pyinstaller/hooks')],excludes=[],noarchive=False)
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='sus-adb',console=False)
package_name=os.environ.get('SUS_ADB_PACKAGE_NAME',f"sus-adb-1.0.0-rc.1-{platform.system().lower()}-{platform.machine().lower()}")
coll=COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name=package_name)
