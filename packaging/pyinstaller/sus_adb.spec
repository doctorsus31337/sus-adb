from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files
root=Path(SPEC).resolve().parents[2]
datas=collect_data_files('customtkinter')+[(str(root/'app/themes'),'app/themes'),(str(root/'docs'),'docs'),(str(root/'plugins/examples'),'plugins/examples'),(str(root/'VERSION'),'.')]
for library_root,excluded in ((root/'scripts/frida',{'custom/flutter_popup_bypass.js'}),(root/'scripts/metadata',{'flutter_popup_bypass.meta.json'})):
    for source in sorted(library_root.rglob('*')):
        relative=source.relative_to(library_root)
        if source.is_file() and relative.as_posix() not in excluded:
            datas.append((str(source),str(Path('scripts')/library_root.name/relative.parent)))
a=Analysis([str(root/'main.py')],pathex=[str(root)],binaries=[],datas=datas,hiddenimports=[],hookspath=[str(root/'packaging/pyinstaller/hooks')],excludes=[],noarchive=False)
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='sus-adb',console=False)
coll=COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name='sus-adb-1.0.0-rc.1')
