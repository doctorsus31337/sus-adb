from __future__ import annotations
import re,zipfile
from pathlib import Path,PurePosixPath
from app.core.apk_lab_models import ApkManifestSummary,ApkSigningRecord
class ApkInspectionService:
 def inspect(self,path,package=""):
  p=Path(path).resolve();warnings=[]
  try:
   with zipfile.ZipFile(p) as z:
    names=sorted(i.filename for i in z.infolist())
    if any(PurePosixPath(n).is_absolute() or ".." in PurePosixPath(n).parts for n in names):raise ValueError("Archive traversal was rejected.")
    libs=tuple(n for n in names if n.startswith("lib/") and n.endswith(".so"));arch=tuple(sorted({n.split('/')[1] for n in libs if len(n.split('/'))>2}));signed=any(n.upper().startswith("META-INF/") and n.upper().endswith((".RSA",".DSA",".EC")) for n in names);summary=ApkManifestSummary(package,native_libraries=libs,architectures=arch);signing=ApkSigningRecord(("v1",) if signed else (),verified=signed,signer_count=1 if signed else 0);warnings.append("Binary AndroidManifest.xml requires aapt/apkanalyzer for full interpretation.");return {"summary":summary,"signing":signing,"inventory":tuple(names),"warnings":tuple(warnings)}
  except (OSError,zipfile.BadZipFile,ValueError) as exc:return {"error":str(exc),"warnings":("APK was not executed.",)}
