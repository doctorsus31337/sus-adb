"""Headless construction and reachability checks; never contacts a device."""
from __future__ import annotations
import os,sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
def main():
 with tempfile.TemporaryDirectory() as d:
  os.environ["XDG_CONFIG_HOME"]=d
  from app.gui.main_window import SusADBWindow
  from app.gui.first_run_dialog import FirstRunDialog
  from app.gui.environment_diagnostics_window import EnvironmentDiagnosticsWindow
  from app.gui.crash_dialog import CrashDialog
  from app.core.environment_diagnostics import DiagnosticRecord
  app=SusADBWindow()
  for ident in app.tk.call("after","info"):
   try:app.after_cancel(ident)
   except Exception:pass
  first=FirstRunDialog(app,app.theme);diagnostics=EnvironmentDiagnosticsWindow(app,app.theme,(DiagnosticRecord("ADB",False,False,guidance="Optional"),));crash=CrashDialog(app,app.theme,"redacted report")
  for width,height in ((1200,760),(1400,860)):
   app.geometry(f"{width}x{height}+0+0");app.update_idletasks()
   assert app.status_bar.winfo_rooty()+app.status_bar.winfo_height()<=app.winfo_rooty()+app.winfo_height()
   assert all(name in app.workspace._tab_dict for name in ("Console","Instrumentation","Scripts","Pentest"))
  assert "1.0.0-rc.1" in app.title()
  first.destroy();diagnostics.destroy();crash.destroy()
  try:app.shutdown()
  except Exception:pass
 print("gui-smoke=PASS sizes=1200x760,1400x860 dialogs=first-run,diagnostics,crash")
 return 0
if __name__=="__main__":raise SystemExit(main())
