from __future__ import annotations
import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
if __name__=="__main__":raise SystemExit(0 if unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.discover(str(ROOT/"tests"))).wasSuccessful() else 1)
