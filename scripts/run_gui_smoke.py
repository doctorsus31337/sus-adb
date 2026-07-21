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
  top=app.nametowidget(app.cget("menu"));cascades=[i for i in range(top.index("end")+1) if top.type(i)=="cascade"];labels=[top.entrycget(i,"label") for i in cascades];assert labels==["File","Settings","Tools","Addons","About"]
  addons=top.nametowidget(top.entrycget(cascades[labels.index("Addons")],"menu"));assert addons.entrycget(0,"label")=="Open Add-ons Center…"
  official=app.plugin_manager.official();assert len(official)==4;assert not app.plugin_manager.list();assert not app.plugin_registry.list()
  assert all(not item.installed and not item.manifest.enabled for item in official)
  app.open_first_run();first=app.first_run_dialog;app.open_first_run();assert app.first_run_dialog is first
  diagnostics=EnvironmentDiagnosticsWindow(app,app.theme,(DiagnosticRecord("ADB",False,False,guidance="Optional"),));crash=CrashDialog(app,app.theme,"redacted report")
  for width,height in ((1200,760),(1400,860)):
   app.geometry(f"{width}x{height}+0+0");app.update_idletasks()
   assert app.status_bar.winfo_rooty()+app.status_bar.winfo_height()<=app.winfo_rooty()+app.winfo_height()
   assert all(name in app.workspace._tab_dict for name in ("Console","Instrumentation","Scripts","Pentest"))
   app.workspace.set("Pentest");app.pentest_workspace.open_plugins();app.pentest_workspace.plugin_panel.tabs.set("Official Catalog");app.update_idletasks();assert len(app.pentest_workspace.plugin_panel.official_cards.winfo_children())==4
   assert app.pentest_workspace.warning.cget("text")=="Authorization must be explicitly confirmed."
  center=app.open_addons_center();assert app.open_addons_center() is center
  for width,height in ((980,650),(1180,780),(1400,860)):
   center.geometry(f"{width}x{height}+0+0");center.update_idletasks();assert len(center.cards)==4;assert len({card.plugin_id for card in center.cards.values()})==4
   text=" ".join(w.cget("text") for w in center.winfo_children() if hasattr(w,"cget") and "text" in w.keys());assert "Quick Tools" not in text and "Authorization must" not in text
  skeleton=next(item for item in official if not item.manifest.requested_capabilities);sid=skeleton.manifest.plugin_id;assert center.cards[sid].actions==("Details","Export Template…","Install")
  export_parent=Path(d)/"export";export_parent.mkdir();center.destination_chooser=lambda:str(export_parent);center.action("Export Template…",sid);assert "not installed or executed" in center.status_message;assert not app.plugin_manager.list()
  assert app.plugin_manager.install_official(sid,skeleton.package_digest).ok;center.refresh();assert center.cards[sid].actions==("Details","Export Template…","Trust");assert "Permissions" not in center.cards[sid].actions
  assert app.plugin_manager.trust_zero_capability(sid,True).ok;center.refresh();assert center.cards[sid].actions==("Details","Export Template…","Enable")
  assert app.plugin_manager.enable(sid).ok;center.refresh();assert center.cards[sid].actions==("Details","Export Template…","Load")
  assert app.plugin_manager.load(sid).ok;center.refresh();assert center.cards[sid].actions==("Details","Export Template…","Open","Unload")
  for item in official:
   if item.manifest.plugin_id==sid:continue
   assert app.plugin_manager.install_official(item.manifest.plugin_id,item.package_digest).ok
   assert app.plugin_manager.approve(item.manifest.plugin_id,item.manifest.requested_capabilities,confirmed=True).ok
   assert app.plugin_manager.enable(item.manifest.plugin_id).ok
   assert not app.plugin_registry.by_plugin(item.manifest.plugin_id)
   assert app.plugin_manager.load(item.manifest.plugin_id).ok
  app.update_idletasks();panels=app.plugin_registry.list("pentest-panel");assert len(panels)==4
  app.menu_bar.refresh_loaded_addons();assert app.menu_bar.loaded_menu.index("end")==3
  skeleton_panel=next(v for v in panels if v.plugin_id==sid);skeleton_window=app.open_addon_window(skeleton_panel.contribution_id);assert skeleton_window is app.open_addon_window(skeleton_panel.contribution_id);center.refresh();assert center.cards[sid].actions==("Details","Export Template…","Focus","Unload")
  first_panel=panels[0];window=app.open_addon_window(first_panel.contribution_id);assert window is app.open_addon_window(first_panel.contribution_id);window.update_idletasks();app.addon_window_host.close(first_panel.contribution_id);assert app.plugin_manager.loader.statuses[first_panel.plugin_id].state.value=="active"
  window=app.open_addon_window(first_panel.contribution_id);assert window;app.plugin_manager.unload(first_panel.plugin_id);app.update_idletasks();assert not app.addon_window_host.is_open(first_panel.contribution_id)
  app.workspace.set("Pentest");app.go_home();assert app.workspace.get()=="Console";assert center.winfo_exists()
  app.pentest_workspace.plugin_panel.refresh();app.update_idletasks()
  assert all(app.plugin_manager.unload(item.manifest.plugin_id).ok for item in official);app.update_idletasks();assert not app.plugin_registry.list();app.menu_bar.refresh_loaded_addons();assert app.menu_bar.loaded_menu.entrycget(0,"label")=="No loaded addons"
  assert "1.0.0-rc.1" in app.title()
  first.destroy();diagnostics.destroy();crash.destroy()
  app.shutdown()
 print("gui-smoke=PASS main=1200x760,1400x860 addons=980x650,1180x780,1400x860 cards=4 singleton-window-home-warning=PASS")
 return 0
if __name__=="__main__":raise SystemExit(main())
