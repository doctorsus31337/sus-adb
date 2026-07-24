"""Headless construction and reachability checks; never contacts a device."""
from __future__ import annotations
import os,sys,tempfile
from types import SimpleNamespace
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
def main():
 with tempfile.TemporaryDirectory() as d:
  os.environ["XDG_CONFIG_HOME"]=d
  import customtkinter as ctk
  from app.gui.main_window import SusADBWindow
  from app.gui.first_run_dialog import FirstRunDialog
  from app.gui.environment_diagnostics_window import EnvironmentDiagnosticsWindow
  from app.gui.crash_dialog import CrashDialog
  from app.gui.splash_screen import SplashScreen
  from app.gui.lazy_panel_host import LazyPanelHost
  from app.core.startup_tips import load_startup_tips
  from app.core.environment_diagnostics import DiagnosticRecord
  from app.core.device import Device
  from app.core.frida_target import FridaTarget,TargetType
  from app.gui.customtkinter_compat import install_scroll_target_guard
  app=SusADBWindow()
  app._deferred_started=True
  assert app.workspace.get()=="Console"
  assert app.instrumentation_panel is None and app.script_studio_panel is None and app.pentest_workspace is None
  assert all(host.state=="pending" for host in app.workspace_hosts.values())
  stage_names={stage.name for stage in app.startup_profiler.stages()};assert {"tk-root","splash-construction","first-splash-paint","console-shell","first-responsive-idle"}<=stage_names
  for width,height in ((600,360),(720,430)):
   splash=SplashScreen(app,app.theme,load_startup_tips(),width=width,height=height);assert splash.master is app;splash.paint_now();splash.update_stage(1,2,"Testing real stage text");assert "SUS COMPANION" in splash.brand_label.cget("text");assert splash.stage_label.cget("text")=="Testing real stage text";splash.show_failure("fixture failure");assert "fixture failure" in splash.stage_label.cget("text");splash.close()
  failed=LazyPanelHost(app,app.theme,"Fixture",lambda _parent:(_ for _ in ()).throw(RuntimeError("bounded fixture")));failed.grid();assert failed.ensure() is None and failed.state=="failed";failed.factory=lambda parent:ctk.CTkFrame(parent,fg_color=app.theme["bg"]);assert failed.ensure() is not None and failed.state=="ready";failed.destroy()
  unopened=LazyPanelHost(app,app.theme,"Unopened",lambda parent:ctk.CTkFrame(parent));unopened.shutdown();assert unopened.ensure() is None;unopened.destroy()
  device=Device("fixture-serial",state="device",model="Fixture");target=FridaTarget("Fixture App","org.example.fixture",101,TargetType.APPLICATION,True);app.devices.cache.update((device,));app.devices.selected_serial=device.serial;app._sync_script_target(target)
  assert not install_scroll_target_guard().installed
  top=app.nametowidget(app.cget("menu"));cascades=[i for i in range(top.index("end")+1) if top.type(i)=="cascade"];labels=[top.entrycget(i,"label") for i in cascades];assert labels==["File","Settings","Tools","Addons","About"]
  addons=top.nametowidget(top.entrycget(cascades[labels.index("Addons")],"menu"));assert addons.entrycget(0,"label")=="Open Add-ons Center…"
  official=app.plugin_manager.official();assert len(official)==4;assert not app.plugin_manager.list();assert not app.plugin_registry.list()
  assert all(not item.installed and not item.manifest.enabled for item in official)
  app.open_first_run();first=app.first_run_dialog;app.open_first_run();assert app.first_run_dialog is first
  diagnostics=EnvironmentDiagnosticsWindow(app,app.theme,(DiagnosticRecord("ADB",False,False,guidance="Optional"),),app.startup_profiler.summary());assert "No telemetry" in diagnostics.startup_view.get("1.0","end");crash=CrashDialog(app,app.theme,"redacted report")
  for width,height in ((1200,760),(1400,860)):
   app.geometry(f"{width}x{height}+0+0");app.update_idletasks()
   assert app.status_bar.winfo_rooty()+app.status_bar.winfo_height()<=app.winfo_rooty()+app.winfo_height()
   assert all(name in app.workspace._tab_dict for name in ("Console","Instrumentation","Scripts","Pentest"))
   app.navigate_workspace("Pentest");assert app.pentest_workspace.device is device and app.pentest_workspace.target is target;app.pentest_workspace.open_plugins();assert app.pentest_workspace._built_sections=={"Plugins"};app.pentest_workspace.plugin_panel.tabs.set("Official Catalog");app.update_idletasks();assert len(app.pentest_workspace.plugin_panel.official_cards.winfo_children())==4
   assert app.pentest_workspace.warning.cget("text")=="Authorization must be explicitly confirmed."
  center=app.open_addons_center();assert app.open_addons_center() is center
  for width,height in ((980,650),(1180,780),(1400,860)):
   center.geometry(f"{width}x{height}+0+0");center.update_idletasks();assert len(center.cards)==4;assert len({card.plugin_id for card in center.cards.values()})==4
   text=" ".join(w.cget("text") for w in center.winfo_children() if hasattr(w,"cget") and "text" in w.keys());assert "Quick Tools" not in text and "Authorization must" not in text
  skeleton=next(item for item in official if not item.manifest.requested_capabilities);sid=skeleton.manifest.plugin_id;assert center.cards[sid].actions==("Details","Export Template…","Install")
  validator=getattr(center.card_area,"_check_if_valid_scroll",getattr(center.card_area,"check_if_master_is_canvas",None));assert validator is not None;assert validator(center.cards[sid]);assert not validator(".native.file.dialog")
  for _ in range(25):center.card_area._mouse_wheel_all(SimpleNamespace(widget=".native.file.dialog",delta=-1,num=5))
  before=(tuple(app.plugin_manager.records),tuple(app.plugin_manager.loader.statuses));center.destination_chooser=lambda:"";center.action("Export Template…",sid);assert before==(tuple(app.plugin_manager.records),tuple(app.plugin_manager.loader.statuses))
  export_parent=Path(d)/"export";export_parent.mkdir();center.destination_chooser=lambda:str(export_parent);center.action("Export Template…",sid);assert "not installed or executed" in center.status_message;assert not app.plugin_manager.list()
  center.geometry("980x650+0+0");center.update_idletasks();canvas=center.card_area._parent_canvas;canvas.configure(scrollregion=(0,0,1000,3000));canvas.yview_moveto(0);scroll_before=canvas.yview();center.card_area._mouse_wheel_all(SimpleNamespace(widget=center.cards[sid],delta=-1,num=5));assert canvas.yview()!=scroll_before;center.update_idletasks()
  stable_card=center.cards[sid]
  assert app.plugin_manager.install_official(sid,skeleton.package_digest).ok;center.refresh();assert center.cards[sid] is stable_card;assert center.cards[sid].actions==("Details","Export Template…","Trust");assert "Permissions" not in center.cards[sid].actions
  assert app.plugin_manager.trust_zero_capability(sid,True).ok;center.refresh();assert center.cards[sid] is stable_card;assert center.cards[sid].actions==("Details","Export Template…","Enable")
  assert app.plugin_manager.enable(sid).ok;center.refresh();assert center.cards[sid] is stable_card;assert center.cards[sid].actions==("Details","Export Template…","Load")
  assert app.plugin_manager.load(sid).ok;center.refresh();assert center.cards[sid] is stable_card;assert center.cards[sid].actions==("Details","Export Template…","Open","Unload")
  for item in official:
   if item.manifest.plugin_id==sid:continue
   assert app.plugin_manager.install_official(item.manifest.plugin_id,item.package_digest).ok
   assert app.plugin_manager.approve(item.manifest.plugin_id,item.manifest.requested_capabilities,confirmed=True).ok
   assert app.plugin_manager.enable(item.manifest.plugin_id).ok
   assert not app.plugin_registry.by_plugin(item.manifest.plugin_id)
   assert app.plugin_manager.load(item.manifest.plugin_id).ok
  app.update_idletasks();panels=app.plugin_registry.list("pentest-panel");assert len(panels)==4
  rescue_panel=next(v for v in panels if v.contribution_id=="device-rescue.panel");rescue_window=app.open_addon_window(rescue_panel.contribution_id);rescue_selector=app.addon_window_host.selectors[rescue_panel.contribution_id];assert rescue_selector.selector.get().startswith("Fixture — fixture-serial");assert "device" in rescue_selector.status.cget("text").casefold();app.addon_window_host.close(rescue_panel.contribution_id)
  app.menu_bar.refresh_loaded_addons();assert app.menu_bar.loaded_menu.index("end")==3
  skeleton_panel=next(v for v in panels if v.plugin_id==sid);skeleton_window=app.open_addon_window(skeleton_panel.contribution_id);assert skeleton_window is app.open_addon_window(skeleton_panel.contribution_id);center.refresh();assert center.cards[sid].actions==("Details","Export Template…","Focus","Unload")
  first_panel=panels[0];window=app.open_addon_window(first_panel.contribution_id);assert window is app.open_addon_window(first_panel.contribution_id);window.update_idletasks();app.addon_window_host.close(first_panel.contribution_id);assert app.plugin_manager.loader.statuses[first_panel.plugin_id].state.value=="active"
  window=app.open_addon_window(first_panel.contribution_id);assert window;app.plugin_manager.unload(first_panel.plugin_id);app.update_idletasks();assert not app.addon_window_host.is_open(first_panel.contribution_id)
  app.workspace.set("Pentest");app.go_home();assert app.workspace.get()=="Console";assert center.winfo_exists()
  app.pentest_workspace.plugin_panel.refresh();app.update_idletasks()
  for name in app.pentest_workspace.HEAVY_SECTIONS:assert app.pentest_workspace._ensure_section(name)
  app.navigate_workspace("Instrumentation");instrumentation=app.instrumentation_panel;assert instrumentation is not None and instrumentation.device is device;assert app.navigate_workspace("Instrumentation") is instrumentation
  app.navigate_workspace("Scripts");scripts=app.script_studio_panel;assert scripts is not None and scripts.device is device and scripts.target is target;assert app.navigate_workspace("Scripts") is scripts
  assert all(app.plugin_manager.unload(item.manifest.plugin_id).ok for item in official);app.update_idletasks();assert not app.plugin_registry.list();app.menu_bar.refresh_loaded_addons();assert app.menu_bar.loaded_menu.entrycget(0,"label")=="No loaded addons"
  assert "SUS Companion" in app.title() and "1.0.0-rc.1" in app.title();assert "SUS COMPANION" in app.gothic_header.title.cget("text")
  assert all(not value.casefold().startswith("blue") for value in app.theme.values() if isinstance(value,str))
  assert not any(worker.is_alive() for worker in app._background_workers)
  first.destroy();diagnostics.destroy();crash.destroy()
  app.shutdown()
 print("gui-smoke=PASS main=1200x760,1400x860 splash=600x360,720x430 addons=980x650,1180x780,1400x860 lazy-workspaces=PASS cards=4 wheel-guard-export-scroll-shutdown=PASS")
 return 0
if __name__=="__main__":raise SystemExit(main())
