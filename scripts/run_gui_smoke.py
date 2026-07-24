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
  from app.core.installed_app_discovery import InstalledApplication,InstalledAppResult
  from app.core.instrumentation_readiness import InstrumentationReadinessService
  from app.gui.customtkinter_compat import install_scroll_target_guard
  def descendants(widget):
   for child in widget.winfo_children():
    yield child
    yield from descendants(child)
  def fully_visible(widget,root):
   left=widget.winfo_rootx();top=widget.winfo_rooty();right=left+widget.winfo_width();bottom=top+widget.winfo_height();ancestor=widget.master
   seen=set()
   while ancestor is not None:
    if id(ancestor) in seen:return False
    seen.add(id(ancestor))
    aleft=ancestor.winfo_rootx();atop=ancestor.winfo_rooty();aright=aleft+ancestor.winfo_width();abottom=atop+ancestor.winfo_height()
    if left<aleft or top<atop or right>aright or bottom>abottom:return False
    if ancestor is root:return True
   ancestor=getattr(ancestor,"master",None)
   return False
  def button_text_fits(widget):
   text=str(widget.cget("text"))
   font=getattr(widget,"_font",None)
   if not text or font is None or not hasattr(font,"measure"):return True
   required=max(font.measure(line) for line in text.splitlines())+18
   return required<=widget.winfo_width()
  def no_question_help(root):
   return all(not str(widget.cget("text")).lstrip().startswith("?") for widget in descendants(root) if isinstance(widget,ctk.CTkButton) and "help" in str(widget.cget("text")).casefold())
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
  top=app.nametowidget(app.cget("menu"));cascades=[i for i in range(top.index("end")+1) if top.type(i)=="cascade"];labels=[top.entrycget(i,"label") for i in cascades];assert labels==["File","Settings","Tools","Addons","Help","About"]
  tools=top.nametowidget(top.entrycget(cascades[labels.index("Tools")],"menu"));tool_labels=[tools.entrycget(i,"label") for i in range(tools.index("end")+1) if tools.type(i)=="command"];assert "Sessions Center" in tool_labels and "Advanced Command Reference" in tool_labels
  help_menu=top.nametowidget(top.entrycget(cascades[labels.index("Help")],"menu"));help_labels=[help_menu.entrycget(i,"label") for i in range(help_menu.index("end")+1) if help_menu.type(i)=="command"];assert "Advanced Command Reference" not in help_labels
  assert not hasattr(app,"action_panel");assert not any(getattr(widget,"cget",lambda _key:"")("text")=="Quick Tools" for widget in descendants(app) if "text" in getattr(widget,"keys",lambda:())())
  addons=top.nametowidget(top.entrycget(cascades[labels.index("Addons")],"menu"));assert addons.entrycget(0,"label")=="Open Add-ons Center…"
  official=app.plugin_manager.official();assert len(official)==6;assert not app.plugin_manager.list();assert not app.plugin_registry.list()
  assert all(not item.installed and not item.manifest.enabled for item in official)
  console_before=app.console.get("1.0","end");app.execute_command("adb shell");app.update_idletasks();assert app.command_bar.session_prompt.winfo_ismapped();assert not app.terminal._active;assert "[BUSY]" not in app.console.get("1.0","end")[len(console_before):]
  app.command_bar.open_session_button.invoke();app.update_idletasks();sessions=app.sessions_center;assert sessions is app.open_sessions_center();assert sessions.routed_plan.session_type.value=="adb-shell";assert not app.interactive_sessions.list();assert no_question_help(sessions)
  for width,height in ((900,650),(980,650),(1180,780),(1400,860)):
   sessions.geometry(f"{width}x{height}+0+0");sessions.update_idletasks();assert sessions.winfo_width()==width and sessions.winfo_height()==height;clipped=[(widget.cget("text"),widget.winfo_width()) for widget in descendants(sessions) if isinstance(widget,ctk.CTkButton) and widget.winfo_ismapped() and not button_text_fits(widget)];assert not clipped,clipped
  sessions.close();assert app.sessions_center is None
  app.open_first_run();first=app.first_run_dialog;app.open_first_run();assert app.first_run_dialog is first
  diagnostics=EnvironmentDiagnosticsWindow(app,app.theme,(DiagnosticRecord("ADB",False,False,guidance="Optional"),),app.startup_profiler.summary());assert "No telemetry" in diagnostics.startup_view.get("1.0","end");assert tuple(diagnostics.tabs._tab_dict)==("Build","Environment","Startup");build_text=diagnostics.build_view.get("1.0","end");assert all(label in build_text for label in ("Product version:","Commit:","Branch/ref:","Build timestamp:","Build channel:"));crash=CrashDialog(app,app.theme,"redacted report")
  for width,height in ((1200,760),(1400,860)):
   app.geometry(f"{width}x{height}+0+0");app.update_idletasks()
   assert app.status_bar.winfo_rooty()+app.status_bar.winfo_height()<=app.winfo_rooty()+app.winfo_height()
   assert all(name in app.workspace._tab_dict for name in ("Console","Instrumentation","Scripts","Pentest"))
   app.navigate_workspace("Pentest");assert app.pentest_workspace.device is device and app.pentest_workspace.target is target;app.pentest_workspace.open_plugins();assert app.pentest_workspace._built_sections=={"Plugins"};app.pentest_workspace.plugin_panel.tabs.set("Official Catalog");app.update_idletasks();assert len(app.pentest_workspace.plugin_panel.official_cards.winfo_children())==6
   expected_sections=("Dashboard","Scope","ADB Explorer","Runtime Explorer","Network","Storage","APK Lab","Findings","Reports","Plugins","Timeline","Evidence","Notes","Changes");assert tuple(button.cget("text") for button in app.pentest_workspace.navigation.buttons)==expected_sections;assert all(button_text_fits(button) for button in app.pentest_workspace.navigation.buttons)
   app.pentest_workspace.workspace.set("Dashboard");app.pentest_workspace._section_selected();app.update_idletasks();dashboard_buttons=[widget for widget in descendants(app.pentest_workspace.tabs["Dashboard"]) if isinstance(widget,ctk.CTkButton) and widget.winfo_ismapped()];pentest_buttons=[*app.pentest_workspace.navigation.buttons,*dashboard_buttons];scroll=app.pentest_workspace.dashboard_scroll;viewport_bottom=min(scroll.winfo_rooty()+scroll.winfo_height(),app.pentest_workspace.winfo_rooty()+app.pentest_workspace.winfo_height(),app.status_bar.winfo_rooty());visible_buttons=[*app.pentest_workspace.navigation.buttons,*[widget for widget in dashboard_buttons if widget.winfo_rooty()>=scroll.winfo_rooty() and widget.winfo_rooty()+widget.winfo_height()<=viewport_bottom]];assert pentest_buttons and all(button_text_fits(button) for button in pentest_buttons);assert all(widget.winfo_rooty()+widget.winfo_height()<=app.status_bar.winfo_rooty() for widget in visible_buttons)
   assert app.pentest_workspace.warning.cget("text")=="Authorization must be explicitly confirmed."
  center=app.open_addons_center();assert app.open_addons_center() is center;assert no_question_help(center)
  for width,height in ((900,650),(980,650),(1180,780),(1400,860)):
   center.geometry(f"{width}x{height}+0+0");center.update_idletasks();assert len(center.cards)==6;assert len({card.plugin_id for card in center.cards.values()})==6
   text=" ".join(w.cget("text") for w in center.winfo_children() if hasattr(w,"cget") and "text" in w.keys());assert "Quick Tools" not in text and "Authorization must" not in text
  skeleton=next(item for item in official if item.manifest.plugin_id=="susadb.skeleton-module");sid=skeleton.manifest.plugin_id;assert center.cards[sid].actions==("Details","Export Template…","Install")
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
   if item.manifest.requested_capabilities:assert app.plugin_manager.approve(item.manifest.plugin_id,item.manifest.requested_capabilities,confirmed=True).ok
   else:assert app.plugin_manager.trust_zero_capability(item.manifest.plugin_id,True).ok
   assert app.plugin_manager.enable(item.manifest.plugin_id).ok
   assert not app.plugin_registry.by_plugin(item.manifest.plugin_id)
   assert app.plugin_manager.load(item.manifest.plugin_id).ok
  app.update_idletasks();panels=app.plugin_registry.list("pentest-panel");assert len(panels)==6
  courses=app.learning_service.courses();assert len(courses)==2 and {len(course.lessons) for course in courses}=={14,15};learning=app.open_learning_center("instrumentation-overview");assert app.open_learning_center() is learning;assert "Instrumentation Overview" in learning.recommendation.cget("text")
  learning.select_course(next(course for course in courses if course.course_id=="frida-foundations"));lesson=learning.current_lesson;learning.toggle_complete();learning.toggle_bookmark();progress=app.learning_service.course_progress("frida-foundations");assert lesson.lesson_id in progress.completed and lesson.lesson_id in progress.bookmarks;assert no_question_help(learning)
  for width,height in ((900,650),(980,650),(1180,780),(1400,860)):
   learning.geometry(f"{width}x{height}+0+0");learning.update_idletasks();assert learning.winfo_width()==width and learning.winfo_height()==height;mapped=[widget for widget in descendants(learning) if isinstance(widget,ctk.CTkButton) and widget.winfo_ismapped() and fully_visible(widget,learning)];assert all(widget.winfo_rootx()>=learning.winfo_rootx() and widget.winfo_rooty()>=learning.winfo_rooty() and widget.winfo_rootx()+widget.winfo_width()<=learning.winfo_rootx()+learning.winfo_width()+2 and widget.winfo_rooty()+widget.winfo_height()<=learning.winfo_rooty()+learning.winfo_height()+2 for widget in mapped)
  rescue_panel=next(v for v in panels if v.contribution_id=="device-rescue.panel");rescue_window=app.open_addon_window(rescue_panel.contribution_id);rescue_selector=app.addon_window_host.selectors[rescue_panel.contribution_id];rescue=app.addon_window_host.frames[rescue_panel.contribution_id];assert rescue_selector.selector.get().startswith("Fixture — fixture-serial");assert "device" in rescue_selector.status.cget("text").casefold();assert rescue.serial=="fixture-serial";assert all(label.cget("text")=="Serial: fixture-serial" for label in rescue.section_serial_labels.values());assert no_question_help(rescue_window);owner=f"plugin:{rescue_panel.plugin_id}";assert app.host_state.subscription_count(owner)==1
  for width,height in ((900,650),(980,650),(1180,780),(1400,860)):
   rescue_window.geometry(f"{width}x{height}+0+0");rescue_window.update_idletasks();assert rescue_window.winfo_width()==width and rescue_window.winfo_height()==height;assert all(button_text_fits(widget) for widget in descendants(rescue_window) if isinstance(widget,ctk.CTkButton) and widget.winfo_ismapped())
  app.addon_window_host.close(rescue_panel.contribution_id);assert app.host_state.subscription_count(owner)==0;app.open_addon_window(rescue_panel.contribution_id);assert app.host_state.subscription_count(owner)==1;app.addon_window_host.close(rescue_panel.contribution_id);assert app.host_state.subscription_count(owner)==0
  readiness_contribution=next(v for v in panels if v.contribution_id=="rootability.panel");readiness_window=app.open_addon_window(readiness_contribution.contribution_id);readiness=app.addon_window_host.frames[readiness_contribution.contribution_id];readiness_selector=app.addon_window_host.selectors[readiness_contribution.contribution_id];assert readiness_selector.selector.get().startswith("Fixture — fixture-serial");assert tuple(readiness.tabs._tab_dict)==readiness.SECTIONS;readiness._apply_assessment(device.serial,InstrumentationReadinessService.classify(serial=device.serial,adb_state="device",architecture="arm64",root_available=True));assert readiness.header_values["route"].cget("text")=="ROOTED_SERVER_SETUP_AVAILABLE";assert no_question_help(readiness_window)
  for width,height in ((900,650),(980,650),(1180,780),(1400,860)):
   readiness_window.geometry(f"{width}x{height}+0+0");readiness_window.update_idletasks();assert readiness_window.winfo_width()==width and readiness_window.winfo_height()==height
   for section in readiness.SECTIONS:
    readiness.tabs.set(section);readiness_window.update_idletasks();mapped=[widget for widget in descendants(readiness_window) if isinstance(widget,ctk.CTkButton) and widget.winfo_ismapped()];assert all(widget.winfo_rootx()>=readiness_window.winfo_rootx() and widget.winfo_rooty()>=readiness_window.winfo_rooty() and widget.winfo_rootx()+widget.winfo_width()<=readiness_window.winfo_rootx()+readiness_window.winfo_width()+2 and widget.winfo_rooty()+widget.winfo_height()<=readiness_window.winfo_rooty()+readiness_window.winfo_height()+2 for widget in mapped)
  app.addon_window_host.close(readiness_contribution.contribution_id)
  assistant_ids=("frida-assistant.panel","objection-assistant.panel")
  assistant_windows=[]
  for contribution_id in assistant_ids:
   contribution=next(v for v in panels if v.contribution_id==contribution_id);assistant_window=app.open_addon_window(contribution_id);assistant=app.addon_window_host.frames[contribution_id];assert assistant_window is app.open_addon_window(contribution_id);assert assistant.state.serial=="fixture-serial";assert assistant.state.target=="org.example.fixture";assert not assistant.output.get("1.0","end").strip();assert no_question_help(assistant_window);assert not app.interactive_sessions.list();assistant_windows.append((contribution_id,assistant_window,assistant))
   for width,height in ((900,650),(980,650),(1180,780),(1400,860)):
    assistant_window.geometry(f"{width}x{height}+0+0");assistant_window.update_idletasks();assert assistant_window.winfo_width()==width and assistant_window.winfo_height()==height;assert all(button_text_fits(widget) for widget in descendants(assistant_window) if isinstance(widget,ctk.CTkButton) and widget.winfo_ismapped())
  app.addon_window_host.close(assistant_ids[0]);assert not app.addon_window_host.is_open(assistant_ids[0]) and app.addon_window_host.is_open(assistant_ids[1]);app.addon_window_host.close(assistant_ids[1])
  app.menu_bar.refresh_loaded_addons();assert app.menu_bar.loaded_menu.index("end")==5
  skeleton_panel=next(v for v in panels if v.plugin_id==sid);skeleton_window=app.open_addon_window(skeleton_panel.contribution_id);assert skeleton_window is app.open_addon_window(skeleton_panel.contribution_id);center.refresh();assert center.cards[sid].actions==("Details","Export Template…","Focus","Unload")
  first_panel=panels[0];window=app.open_addon_window(first_panel.contribution_id);assert window is app.open_addon_window(first_panel.contribution_id);window.update_idletasks();app.addon_window_host.close(first_panel.contribution_id);assert app.plugin_manager.loader.statuses[first_panel.plugin_id].state.value=="active"
  window=app.open_addon_window(first_panel.contribution_id);assert window;app.plugin_manager.unload(first_panel.plugin_id);app.update_idletasks();assert not app.addon_window_host.is_open(first_panel.contribution_id)
  app.workspace.set("Pentest");app.go_home();assert app.workspace.get()=="Console";assert center.winfo_exists()
  app.pentest_workspace.plugin_panel.refresh();app.update_idletasks()
  for name in app.pentest_workspace.HEAVY_SECTIONS:assert app.pentest_workspace._ensure_section(name)
  app.navigate_workspace("Instrumentation");instrumentation=app.instrumentation_panel;assert instrumentation is not None and instrumentation.device is device;assert app.navigate_workspace("Instrumentation") is instrumentation;assert tuple(instrumentation.target_sources._tab_dict)==("Installed Applications","Runtime Targets");instrumentation._apply_installed_apps(InstalledAppResult(device.serial,(InstalledApplication("org.example.fixture","Fixture App",launchable=True,running=True,pid=101),)));assert instrumentation.installed_scan_complete and len(instrumentation.installed_list.winfo_children())==1;assert instrumentation.interface_mode=="guided";assert instrumentation.frida_attach_button.cget("text")=="Observe Running App";app.set_interface_mode("advanced");assert instrumentation.frida_attach_button.cget("text")=="Attach";app.set_interface_mode("guided")
  help_window=app.open_context_help("targets");assert app.open_context_help("console") is help_window;assert "Console" in help_window.topic_text.get("1.0","end");help_window.tabs.set("Glossary");help_window.search.delete(0,"end");help_window.search.insert(0,"temporary numeric");help_window._search_changed();assert "PID" in help_window.glossary_text.get("1.0","end")
  for width,height in ((900,650),(980,650),(1180,780),(1400,860)):
   help_window.geometry(f"{width}x{height}+0+0");help_window.update_idletasks();assert help_window.winfo_width()==width and help_window.winfo_height()==height;assert all(button_text_fits(widget) for widget in descendants(help_window) if isinstance(widget,ctk.CTkButton) and widget.winfo_ismapped())
  guide=app.open_guided_setup();assert app.open_guided_setup() is guide;assert len(guide.STEPS)==10 and not guide.plan.executes_automatically
  app.navigate_workspace("Scripts");scripts=app.script_studio_panel;assert scripts is not None and scripts.device is device and scripts.target is target;assert app.navigate_workspace("Scripts") is scripts;assert no_question_help(app)
  assert all(app.plugin_manager.unload(item.manifest.plugin_id).ok for item in official);app.update_idletasks();assert not app.plugin_registry.list();app.menu_bar.refresh_loaded_addons();assert app.menu_bar.loaded_menu.entrycget(0,"label")=="No loaded addons"
  assert "SUS Companion" in app.title() and "1.0.0-rc.1" in app.title();assert "SUS COMPANION" in app.gothic_header.title.cget("text")
  assert all(not value.casefold().startswith("blue") for value in app.theme.values() if isinstance(value,str))
  assert not any(worker.is_alive() for worker in app._background_workers)
  first.destroy();diagnostics.destroy();crash.destroy()
  app.shutdown()
 print("gui-smoke=PASS main=1200x760,1400x860 splash=600x360,720x430 compact-windows=900x650,980x650,1180x780,1400x860 addons-rescue-assistants-help-sessions-learning=PASS lazy-workspaces=PASS cards=6 wheel-guard-export-scroll-shutdown=PASS")
 return 0
if __name__=="__main__":raise SystemExit(main())
