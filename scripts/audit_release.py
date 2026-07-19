from __future__ import annotations
import re,subprocess,sys
from pathlib import Path
BLOCKED_SUFFIXES=(".pcap",".pcapng",".apk",".apks",".xapk",".keystore",".jks",".db",".sqlite",".log",".pyc")
PATTERNS=(("developer-home",re.compile(rb"(?:/home/[^/\s]+|C:\\Users\\[^\\\s]+)")),("private-key",re.compile(rb"-----BEGIN [A-Z ]+PRIVATE KEY-----")),("token",re.compile(rb"(?:ghp_|github_pat_|AKIA)[A-Za-z0-9_]{12,}")))
ALLOW=("docs/privacy-security.md","scripts/audit_release.py","app/core/logging_manager.py","app/core/crash_report.py","tests/test_crash_report.py","tests/test_logging_manager.py","tests/test_release_manifest.py","tests/test_release_audit.py")
def tracked(root="."):
 try:return subprocess.check_output(("git","ls-files","-z"),cwd=root).decode().split("\0")[:-1]
 except Exception:return [p.relative_to(root).as_posix() for p in Path(root).rglob("*") if p.is_file()]
def audit(root="."):
 findings=[];base=Path(root)
 for rel in sorted(tracked(root)):
  if rel in ALLOW:continue
  p=base/rel
  if rel.lower().endswith(BLOCKED_SUFFIXES):findings.append((rel,"generated-artifact"));continue
  try:data=p.read_bytes()
  except OSError:continue
  for name,pattern in PATTERNS:
   if pattern.search(data):findings.append((rel,name))
 return tuple(findings)
if __name__=="__main__":
 found=audit();[print(f"BLOCK {kind}: {path}") for path,kind in found];raise SystemExit(1 if found else 0)
