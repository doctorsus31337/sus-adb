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
  official=app.plugin_manager.official();assert len(official)==4;assert not app.plugin_manager.list();assert not app.plugin_registry.list()
  assert all(not item.installed and not item.manifest.enabled for item in official)
  app.open_first_run();first=app.first_run_dialog;app.open_first_run();assert app.first_run_dialog is first
  diagnostics=EnvironmentDiagnosticsWindow(app,app.theme,(DiagnosticRecord("ADB",False,False,guidance="Optional"),));crash=CrashDialog(app,app.theme,"redacted report")
  for width,height in ((1200,760),(1400,860)):
   app.geometry(f"{width}x{height}+0+0");app.update_idletasks()
   assert app.status_bar.winfo_rooty()+app.status_bar.winfo_height()<=app.winfo_rooty()+app.winfo_height()
   assert all(name in app.workspace._tab_dict for name in ("Console","Instrumentation","Scripts","Pentest"))
   app.workspace.set("Pentest");app.pentest_workspace.open_plugins();app.pentest_workspace.plugin_panel.tabs.set("Official Catalog");app.update_idletasks();assert "susadb.device-rescue-recovery" in app.pentest_workspace.plugin_panel.official_view.get("1.0","end")
  for item in official:
   assert app.plugin_manager.install_official(item.manifest.plugin_id,item.package_digest).ok
   assert app.plugin_manager.approve(item.manifest.plugin_id,item.manifest.requested_capabilities,confirmed=True).ok
   assert app.plugin_manager.enable(item.manifest.plugin_id).ok
   assert not app.plugin_registry.by_plugin(item.manifest.plugin_id)
   assert app.plugin_manager.load(item.manifest.plugin_id).ok
  app.update_idletasks();panels=app.plugin_registry.list("pentest-panel");assert len(panels)==3
  app.pentest_workspace.plugin_panel.refresh();app.update_idletasks();assert hasattr(app.pentest_workspace.plugin_panel,"panel_tabs")
  assert all(app.plugin_manager.unload(item.manifest.plugin_id).ok for item in official);app.update_idletasks();assert not app.plugin_registry.list()
  assert "1.0.0-rc.1" in app.title()
  first.destroy();diagnostics.destroy();crash.destroy()
  app.shutdown()
 print("gui-smoke=PASS sizes=1200x760,1400x860 official-catalog=4 explicit-install-load-unload=PASS dialogs=first-run,diagnostics,crash")
 return 0
if __name__=="__main__":raise SystemExit(main())
