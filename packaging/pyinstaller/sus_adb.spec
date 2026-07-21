import importlib.util,os,platform
from pathlib import Path
from PyInstaller.utils.hooks import collect_all,collect_data_files,copy_metadata
root=Path(SPEC).resolve().parents[2]
datas=collect_data_files('customtkinter')+[(str(root/'app/themes/gothic.json'),'app/themes'),(str(root/'docs'),'docs'),(str(root/'plugins/examples'),'plugins/examples'),(str(root/'VERSION'),'.')]
frida_datas,frida_binaries,frida_hiddenimports=collect_all('frida')
datas+=frida_datas+copy_metadata('frida')
policy_spec=importlib.util.spec_from_file_location('sus_adb_release_assets',root/'packaging/common/release_assets.py')
policy=importlib.util.module_from_spec(policy_spec);policy_spec.loader.exec_module(policy)
selected=policy.select_curated_assets(root)
for category,paths in selected.items():
    for relative_text in paths:
        relative=Path(relative_text);datas.append((str(root/relative),str(relative.parent)))
for relative_text in policy.select_official_plugins(root):
    relative=Path(relative_text);datas.append((str(root/relative),str(relative.parent)))
report=policy.write_asset_report(root/'build/packaging/curated-script-assets.json',selected)
datas.append((str(report),'packaging'))
a=Analysis([str(root/'main.py')],pathex=[str(root)],binaries=frida_binaries,datas=datas,hiddenimports=frida_hiddenimports,hookspath=[str(root/'packaging/pyinstaller/hooks')],excludes=[],noarchive=False)
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='sus-adb',console=False)
package_name=os.environ.get('SUS_ADB_PACKAGE_NAME',f"sus-adb-1.0.0-rc.1-{platform.system().lower()}-{platform.machine().lower()}")
coll=COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name=package_name)
