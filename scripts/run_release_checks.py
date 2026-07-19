from __future__ import annotations
import compileall,subprocess,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
def main():
 ok=unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.discover(str(ROOT/"tests"))).wasSuccessful();ok=compileall.compile_dir(str(ROOT/"app"),quiet=1) and compileall.compile_file(str(ROOT/"main.py"),quiet=1) and ok
 for cmd in ((sys.executable,"main.py","--self-test"),(sys.executable,"scripts/audit_release.py")):
  ok=subprocess.run(cmd,check=False,cwd=ROOT).returncode==0 and ok
 required=("VERSION","packaging/pyinstaller/sus_adb.spec",".github/workflows/test.yml","release/RC1_CHECKLIST.md");ok=all((ROOT/p).exists() for p in required) and ok
 print("release-checks=PASS" if ok else "release-checks=FAIL");return 0 if ok else 1
if __name__=="__main__":raise SystemExit(main())
