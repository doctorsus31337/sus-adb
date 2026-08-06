"""Responsive Gothic local Plugin Manager; no automatic plugin execution."""
from __future__ import annotations
import json
from pathlib import Path
import threading
import tkinter as tk
from tkinter import BooleanVar,StringVar,filedialog,messagebox,simpledialog
import customtkinter as ctk
from app.core.responsive_layout import estimated_button_width
from app.core.worker import BackgroundWorker
from app.gui.customtkinter_compat import (
    DeterministicTabview,PendingCallbackOwner,ScopedScrollableFrame,
    clamp_scroll_offset,wheel_scroll_units,widget_exists,widget_within,
)
from app.gui.read_only_text import ReadOnlyTextView
from app.plugins.plugin_capabilities import HIGH_IMPACT
from app.plugins.plugin_interactive import (
    PluginActionRequest,PluginActionResult,PluginContextBinding,PluginFieldType,
    PluginProgressUpdate,validate_form,
)
from app.plugins.plugin_ui import PluginPanelSpec
class PluginActionScrollableFrame(ScopedScrollableFrame):
    """Plugin action viewport using the canonical host-owned scroll router."""
class PluginSpecFrame(ctk.CTkFrame):
    def __init__(self,parent,theme,spec,*,plugin_id="",context_provider=lambda:None,authorize=lambda _caps:None,start_background=None,ui_dispatch=None,confirm=None,navigate=None,refresh_factory=None):
        super().__init__(parent,fg_color=theme["bg"],corner_radius=0);self.theme=theme;self.spec=None;self.pages={};self.plugin_id=plugin_id;self.context_provider=context_provider;self.authorize=authorize;self.start_background=start_background or (lambda target,callback:BackgroundWorker(target,callback=callback).start());self.ui_dispatch=ui_dispatch or (lambda callback,*args:self.after(0,callback,*args));self.confirm=confirm or (lambda title,text:messagebox.askyesno(title,text,parent=self.winfo_toplevel()));self.navigate=navigate or (lambda _spec:False);self.refresh_factory=refresh_factory;self.field_vars={};self.field_widgets={};self.field_labels={};self.action_cards={};self.action_titles={};self.action_descriptions={};self.action_buttons={};self._multiline_widgets=[];self.active_action=None;self.cancel_event=None;self.generation=0;self.closed=False;self._callbacks=PendingCallbackOwner(self);self.grid_columnconfigure(0,weight=1);self.grid_rowconfigure(2,weight=1)
        self.title_label=ctk.CTkLabel(self,text="",text_color=theme["gold"],font=theme["header_font"],anchor="w",wraplength=760);self.title_label.grid(row=0,column=0,sticky="ew",padx=8,pady=4)
        self.status_label=ctk.CTkLabel(self,text="",text_color=theme["muted"],anchor="w",wraplength=900);self.status_label.grid(row=1,column=0,sticky="ew",padx=8)
        self.tabs=ctk.CTkTabview(self,fg_color=theme["panel"],segmented_button_fg_color=theme["panel_alt"],segmented_button_selected_color=theme["red"],segmented_button_selected_hover_color=theme["red_hover"],segmented_button_unselected_color=theme["panel_alt"],segmented_button_unselected_hover_color=theme["gold_dark"],text_color=theme["text"]);self.tabs.grid(row=2,column=0,sticky="nsew",padx=5,pady=5)
        self.action_host=PluginActionScrollableFrame(self,fg_color=theme["panel"],height=210);self.action_host.grid(row=3,column=0,sticky="ew",padx=5,pady=(0,5));self.action_host.grid_columnconfigure(0,weight=1)
        self.action_host._parent_canvas.configure(takefocus=True,yscrollincrement=1)
        self.action_status=ctk.CTkLabel(self.action_host,text="",text_color=theme["muted"],anchor="w",wraplength=820);self.action_status.grid(row=999,column=0,sticky="ew",padx=8,pady=4)
        self.update_spec(spec)
    def update_spec(self,spec):
        if spec==self.spec:return
        selected=self.tabs.get() if self.pages else ""
        self.spec=spec;self.title_label.configure(text=spec.title);self.status_label.configure(text=" · ".join(f"{k}: {v}" for k,v in spec.status.items()))
        existing=set(self.pages);wanted={view.name for view in spec.views}
        for name in existing-wanted:self.tabs.delete(name);self.pages.pop(name,None)
        for view in spec.views:
            body=self.pages.get(view.name)
            if body is None:
                page=self.tabs.add(view.name);page.grid_columnconfigure(0,weight=1);page.grid_rowconfigure(0,weight=1);body=ReadOnlyTextView(page,fg_color=self.theme["terminal_bg"],text_color=self.theme["terminal_text"],border_color=self.theme["border"],border_width=1,wrap="word");body.grid(row=0,column=0,sticky="nsew",padx=4,pady=4);self.pages[view.name]=body
            text=view.body+("\n\n"+"\n".join(f"{k}: {v}" for k,v in view.rows) if view.rows else "")+(f"\n\nWARNING: {view.warning}" if view.warning else "");body.replace(text)
        if selected in self.pages:self.tabs.set(selected)
        self._render_actions()
    def _render_actions(self):
        offset=self._action_scroll_offset()
        self.action_host.clear_nested_scrolls()
        for child in self.action_host.winfo_children():
            if child is not self.action_status:child.destroy()
        self.field_vars={};self.field_widgets={};self.field_labels={};self.action_cards={};self.action_titles={};self.action_descriptions={};self.action_buttons={};self._multiline_widgets=[]
        if not self.spec.actions:
            self.action_host.grid_remove();return
        self.action_host.grid();row=0
        for action in self.spec.actions:
            card=ctk.CTkFrame(self.action_host,fg_color=self.theme["panel_alt"],border_width=1,border_color=self.theme["border"]);card.grid(row=row,column=0,sticky="ew",padx=5,pady=4);card.grid_columnconfigure(0,weight=1);row+=1
            self.action_cards[action.action_id]=card
            title=ctk.CTkLabel(card,text=action.label,text_color=self.theme["gold"],anchor="w",font=self.theme["header_font"],wraplength=700);title.grid(row=0,column=0,sticky="ew",padx=8,pady=(6,1));self.action_titles[action.action_id]=title
            if action.description:
                description=ctk.CTkLabel(card,text=action.description,text_color=self.theme["muted"],anchor="w",justify="left",wraplength=780);description.grid(row=1,column=0,columnspan=2,sticky="ew",padx=8);self.action_descriptions[action.action_id]=description
            field_row=2
            if action.form:
                for field in action.form.fields:
                    label=ctk.CTkLabel(card,text=field.label,text_color=self.theme["text"],anchor="w");label.grid(row=field_row,column=0,sticky="ew",padx=8,pady=(4,0));self.field_labels[(action.action_id,field.field_id)]=label;field_row+=1
                    key=(action.action_id,field.field_id);default=field.default if field.default is not None else False if field.field_type is PluginFieldType.CHECKBOX else ""
                    variable=BooleanVar(value=bool(default)) if field.field_type is PluginFieldType.CHECKBOX else StringVar(value=str(default));self.field_vars[key]=(field,variable)
                    if field.field_type is PluginFieldType.CHECKBOX:widget=ctk.CTkCheckBox(card,text=field.description or field.label,variable=variable,fg_color=self.theme["red"],hover_color=self.theme["red_hover"],border_color=self.theme["gold_dark"])
                    elif field.field_type is PluginFieldType.CHOICE:widget=ctk.CTkComboBox(card,values=[v.option_id for v in field.options],variable=variable,fg_color=self.theme["terminal_bg"],border_color=self.theme["gold_dark"],button_color=self.theme["gold_dark"],button_hover_color=self.theme["red_hover"],text_color=self.theme["text"])
                    elif field.field_type is PluginFieldType.MULTILINE:
                        widget=ctk.CTkTextbox(card,height=70,fg_color=self.theme["terminal_bg"],text_color=self.theme["text"],border_color=self.theme["gold_dark"],border_width=1,wrap="word");widget.insert("1.0",str(default));self.field_vars[key]=(field,widget);self._multiline_widgets.append(widget)
                        self.action_host.register_nested_scroll(widget)
                    else:widget=ctk.CTkEntry(card,textvariable=variable,placeholder_text=field.placeholder,show="•" if field.field_type is PluginFieldType.PASSWORD or field.sensitive else "",fg_color=self.theme["terminal_bg"],border_color=self.theme["gold_dark"],text_color=self.theme["text"],state="disabled" if field.field_type is PluginFieldType.READ_ONLY else "normal")
                    widget.grid(row=field_row,column=0,columnspan=2,sticky="ew",padx=8,pady=(0,3));self.field_widgets[key]=widget;field_row+=1
            button=ctk.CTkButton(card,text=action.label,command=lambda value=action:self.invoke_action(value),fg_color=self.theme["red"] if action.primary else self.theme["panel_alt"],hover_color=self.theme["red_hover"] if action.primary else self.theme["gold_dark"],border_width=1,border_color=self.theme["gold_dark"],text_color=self.theme["text"]);button.grid(row=field_row,column=1,sticky="e",padx=8,pady=7);self.action_buttons[action.action_id]=button
            if not action.enabled:button.configure(state="disabled");ctk.CTkLabel(card,text=action.unavailable_reason or "Unavailable",text_color=self.theme["error"],anchor="w",wraplength=600).grid(row=field_row,column=0,sticky="ew",padx=8)
        self.action_status.grid(row=row,column=0,sticky="ew",padx=8,pady=4)
        self._callbacks.schedule_idle(self._restore_action_scroll,offset)
    def _action_visible(self):
        return not self.closed and widget_exists(self.action_host._parent_frame) and bool(self.action_host._parent_frame.winfo_ismapped())
    def _action_contains(self,widget):
        return widget in {self.action_host._parent_frame,self.action_host._parent_canvas,self.action_host._scrollbar} or widget_within(widget,self.action_host)
    def _action_scroll_offset(self):
        if not widget_exists(getattr(self.action_host,"_parent_canvas",None)):return 0.0
        try:return max(0.0,float(self.action_host._parent_canvas.canvasy(0)))
        except (TypeError,ValueError,tk.TclError):return 0.0
    def _restore_action_scroll(self,offset):
        if not self._action_visible():return
        canvas=self.action_host._parent_canvas
        try:
            region=tuple(float(value) for value in str(canvas.cget("scrollregion")).split())
            extent=region[3]-region[1] if len(region)==4 else 0.0
            viewport=max(1,canvas.winfo_height())
            offset=clamp_scroll_offset(offset,extent,viewport)
            canvas.yview_moveto(offset/extent if extent else 0)
        except (TypeError,ValueError,tk.TclError):return
    def _multiline_for(self,origin):
        return next((widget for widget in self._multiline_widgets if widget_within(origin,widget)),None)
    @staticmethod
    def _editing_control(origin):
        while isinstance(origin,tk.Misc):
            if isinstance(origin,(ctk.CTkEntry,ctk.CTkTextbox,ctk.CTkComboBox)):return True
            origin=getattr(origin,"master",None)
        return False
    def _scroll_multiline(self,widget,event):
        if not widget_exists(widget):return False
        units=wheel_scroll_units(event,lines=3)
        if not units:return False
        try:
            first,last=widget._textbox.yview()
            available=units<0 and first>0.0001 or units>0 and last<0.9999
            if available:widget._textbox.yview_scroll(units,"units");return True
        except (AttributeError,tk.TclError):return False
        return False
    def _multiline_wheel(self,event):
        return self.action_host._scroll_router._nested_wheel(event)
    def _action_wheel(self,event):
        router=self.action_host._scroll_router
        origin=getattr(event,"widget",None)
        nested=router._nested_for(origin)
        units=wheel_scroll_units(event,lines=3)
        if nested is not None and units and router._can_scroll(nested,units):
            return router._nested_wheel(event)
        return self.action_host._scroll_router._wheel(event)
    def _action_key(self,event):
        return self.action_host._scroll_router._key(event)
    def _action_focus_in(self,event):
        return self.action_host._scroll_router._focus_in(event)
    def _ensure_action_visible(self,widget):
        if not self._action_visible() or not self._action_contains(widget):return
        try:
            canvas=self.action_host._parent_canvas
            view_top=self._action_scroll_offset()
            top=view_top+widget.winfo_rooty()-canvas.winfo_rooty()
            bottom=top+widget.winfo_height();viewport=max(1,canvas.winfo_height());target=view_top
            if top<view_top:target=top
            elif bottom>view_top+viewport:target=bottom-viewport
            region=tuple(float(value) for value in str(canvas.cget("scrollregion")).split());extent=region[3]-region[1] if len(region)==4 else viewport
            target=clamp_scroll_offset(target,extent,viewport);canvas.yview_moveto(target/extent if extent else 0)
        except (TypeError,ValueError,tk.TclError):return
    def _values(self,action):
        values={}
        for field in action.form.fields if action.form else ():
            holder=self.field_vars[(action.action_id,field.field_id)][1]
            values[field.field_id]=holder.get("1.0","end-1c") if isinstance(holder,ctk.CTkTextbox) else holder.get()
        return validate_form(action.form,values)
    def invoke_action(self,action):
        if self.closed or self.active_action or not action.enabled:return False
        authorization=self.authorize(action.required_capabilities)
        if not authorization or not getattr(authorization,"ok",False):self.action_status.configure(text=getattr(authorization,"error","Action is unavailable."),text_color=self.theme["error"]);return False
        try:values=self._values(action)
        except ValueError as exc:self.action_status.configure(text=str(exc)[:240],text_color=self.theme["error"]);return False
        context=self.context_provider();serial=str(getattr(context,"selected_device",{}).get("serial",""));target=str(getattr(context,"selected_target",{}).get("identifier") or getattr(context,"selected_target",{}).get("name") or "")
        if action.confirmation:
            detail=action.confirmation.summary+f"\n\nSelected serial: {serial or 'None'}\nSelected target: {target or 'None'}\nCapabilities: {', '.join(action.required_capabilities) or 'None'}"
            if not self.confirm("Confirm Plugin Action",detail):return False
        current=self.context_provider();now_serial=str(getattr(current,"selected_device",{}).get("serial",""));now_target=str(getattr(current,"selected_target",{}).get("identifier") or getattr(current,"selected_target",{}).get("name") or "")
        if action.context_binding in {PluginContextBinding.DEVICE,PluginContextBinding.DEVICE_AND_TARGET} and serial!=now_serial or action.context_binding in {PluginContextBinding.TARGET,PluginContextBinding.DEVICE_AND_TARGET} and target!=now_target:self.action_status.configure(text="Selected device or target changed; review the action again.",text_color=self.theme["error"]);return False
        self.active_action=action.action_id;self.cancel_event=threading.Event();self.generation+=1;generation=self.generation
        for button in self.action_buttons.values():button.configure(state="disabled")
        if action.supports_cancellation:
            self.cancel_button=ctk.CTkButton(self.action_host,text="Cancel Action",command=self.cancel_action,fg_color=self.theme["panel_alt"],hover_color=self.theme["gold_dark"],border_width=1,border_color=self.theme["gold_dark"],text_color=self.theme["text"]);self.cancel_button.grid(row=998,column=0,sticky="e",padx=8,pady=3)
        self.action_status.configure(text="Action running…",text_color=self.theme["gold"])
        request=PluginActionRequest(action.action_id,values,current,serial if "read-selected-device" in action.required_capabilities else "",target if "read-selected-target" in action.required_capabilities else "",self.cancel_event.is_set,lambda update:self.ui_dispatch(self._progress,generation,update))
        def run():
            try:
                result=action.callback(request)
                return result if isinstance(result,PluginActionResult) else PluginActionResult(False,"Plugin action returned an invalid result.",error_code="invalid-result")
            except Exception:return PluginActionResult(False,"Plugin action failed safely.",error_code="plugin-action-failed")
        self.start_background(run,lambda result:self.ui_dispatch(self._finish_action,generation,action,result));return True
    def _progress(self,generation,update):
        if self.closed or generation!=self.generation:return
        try:update=update if isinstance(update,PluginProgressUpdate) else PluginProgressUpdate(str(update))
        except (TypeError,ValueError):return
        suffix=f" · {round(update.value*100)}%" if update.value is not None else "";self.action_status.configure(text=(update.text or "Action running")+suffix,text_color=self.theme["gold"])
    def _finish_action(self,generation,action,result):
        if self.closed or generation!=self.generation:return
        self.active_action=None;self.cancel_event=None
        if hasattr(self,"cancel_button") and self.cancel_button.winfo_exists():self.cancel_button.destroy()
        for spec in self.spec.actions:
            self.action_buttons[spec.action_id].configure(state="normal" if spec.enabled else "disabled")
        self.action_status.configure(text=result.message or ("Complete" if result.ok else "Action failed"),text_color=self.theme["gold"] if result.ok else self.theme["error"])
        if result.ok and result.navigation:self.navigate(result.navigation)
        if result.ok and isinstance(result.panel,PluginPanelSpec):self.update_spec(result.panel)
        elif result.ok and action.refresh.value=="panel" and self.refresh_factory:
            refreshed=self.refresh_factory(self.context_provider())
            if isinstance(refreshed,PluginPanelSpec):self.update_spec(refreshed)
    def cancel_action(self):
        if self.cancel_event:self.cancel_event.set();self.action_status.configure(text="Cancellation requested…",text_color=self.theme["gold"])
    def cleanup(self):
        self.closed=True;self.generation+=1;self.cancel_action()
        self.action_host._scroll_router.close();self._callbacks.cancel_all()
        for (action_id,field_id),(field,holder) in tuple(self.field_vars.items()):
            if field.sensitive or field.field_type is PluginFieldType.PASSWORD:
                if isinstance(holder,ctk.CTkTextbox):holder.delete("1.0","end")
                else:holder.set("")
class PluginManagerPanel(ctk.CTkFrame):
    SECTIONS=("Official Catalog","Installed","Active Panels","Details","Permissions","Contributions","Diagnostics","SDK")
    def __init__(self,parent,theme,manager,log,confirm=None):
        super().__init__(parent,fg_color=theme["bg"],corner_radius=0);self.theme=theme;self.manager=manager;self.log=log;self.confirm=confirm or (lambda t,m:messagebox.askyesno(t,m,parent=self.winfo_toplevel()));self.selected=None;self._callbacks=PendingCallbackOwner(self);self.grid_columnconfigure(0,weight=1);self.grid_rowconfigure(1,weight=1);self._header();self.tabs=DeterministicTabview(self,fg_color=theme["panel"],segmented_button_fg_color=theme["panel_alt"],segmented_button_selected_color=theme["red"],segmented_button_selected_hover_color=theme["red_hover"],segmented_button_unselected_color=theme["panel_alt"],segmented_button_unselected_hover_color=theme["gold_dark"],text_color=theme["text"]);self.tabs.grid(row=1,column=0,sticky="nsew",padx=6,pady=4);self.views={n:self.tabs.add(n) for n in self.SECTIONS}
        for name,v in self.views.items():
            v.configure(fg_color=theme["bg"]);v.grid_columnconfigure(0,weight=1)
            v.grid_rowconfigure(0,weight=1 if name in {"Official Catalog","Active Panels","Details","Contributions"} else 0)
            v.grid_rowconfigure(1,weight=1 if name in {"Installed","Permissions","Diagnostics","SDK"} else 0)
        self._build();self.unsubscribe=self.manager.registry.subscribe(lambda _items:self.after(0,self.refresh));self.refresh()
    def show_section(self,name):
        if name not in self.views:raise ValueError(f"Unknown Plugin Manager section: {name}")
        self.tabs.set(name);return self
    def _button(self,p,text,cmd,row,col):b=ctk.CTkButton(p,text=text,command=cmd,fg_color=self.theme["red"],hover_color=self.theme["red_hover"],text_color=self.theme["text"],border_width=1,border_color=self.theme["gold_dark"],height=30,width=estimated_button_width(text,90));b.grid(row=row,column=col,sticky="ew",padx=3,pady=3);return b
    def _text(self,p):t=ReadOnlyTextView(p,fg_color=self.theme["terminal_bg"],text_color=self.theme["terminal_text"],border_width=1,border_color=self.theme["border"],wrap="word");t.grid(row=1,column=0,sticky="nsew",padx=6,pady=4);return t
    def _set(self,w,text):w.replace(text)
    def _header(self):
        h=ctk.CTkFrame(self,fg_color=self.theme["panel"],border_width=1,border_color=self.theme["gold_dark"]);h.grid(row=0,column=0,sticky="ew",padx=6,pady=4);h.grid_columnconfigure(0,weight=1);self.summary=ctk.CTkLabel(h,text="Plugins",text_color=self.theme["gold"],anchor="w",wraplength=760);self.summary.grid(row=0,column=0,sticky="ew",padx=7);self._button(h,"Refresh",self.refresh,0,1);self._button(h,"Install Local Plugin",self.install,0,2);self._button(h,"Verify All",self.verify_all,0,3);self._button(h,"Disable All Third-Party",self.disable_all,0,4);self.warning=ctk.CTkLabel(h,text="Third-party plugins remain disabled and untrusted by default.",text_color=self.theme["gold"],anchor="w",wraplength=900);self.warning.grid(row=1,column=0,columnspan=5,sticky="ew",padx=7)
    def _build(self):
        p=self.views["Official Catalog"];self.official_cards=ScopedScrollableFrame(p,fg_color=self.theme["bg"]);self.official_cards.grid(row=0,column=0,sticky="nsew");self.official_cards.grid_columnconfigure(0,weight=1);self.official_cards._parent_canvas.bind("<Configure>",self._sync_official_scrollregion,add="+")
        p=self.views["Installed"];bar=ctk.CTkFrame(p,fg_color="transparent");bar.grid(row=0,column=0,sticky="ew");bar.grid_columnconfigure(0,weight=1);self.search=ctk.CTkEntry(bar,placeholder_text="Search plugins",fg_color=self.theme["terminal_bg"],border_color=self.theme["gold_dark"],text_color=self.theme["text"]);self.search.grid(row=0,column=0,sticky="ew",padx=3);self._button(bar,"Apply",self.render,0,1)
        for i,(n,c) in enumerate((("Enable",self.enable),("Disable",self.disable),("Load",self.load),("Unload",self.unload),("Reload",self.reload),("Uninstall",self.uninstall)),2):self._button(bar,n,c,0,i)
        self.installed=self._text(p)
        for name in ("Details","Contributions"):self.__dict__[name.lower()+"_view"]=self._text(self.views[name]);self.__dict__[name.lower()+"_view"].grid_configure(row=0)
        for name in ("Permissions","Diagnostics","SDK"):self.__dict__[name.lower()+"_view"]=self._text(self.views[name])
        self.active_host=ctk.CTkFrame(self.views["Active Panels"],fg_color=self.theme["bg"]);self.active_host.grid(row=0,column=0,sticky="nsew");self.active_host.grid_columnconfigure(0,weight=1);self.active_host.grid_rowconfigure(0,weight=1)
        p=self.views["Permissions"];bar=ctk.CTkFrame(p,fg_color="transparent");bar.grid(row=0,column=0,sticky="ew");self._button(bar,"Approve Selected Requested",self.approve,0,0);self._button(bar,"Revoke Trust",self.revoke,0,1)
        p=self.views["Diagnostics"];bar=ctk.CTkFrame(p,fg_color="transparent");bar.grid(row=0,column=0,sticky="ew");self._button(bar,"Copy Diagnostics",lambda:self._copy(self.diagnostics_view.get("1.0","end-1c")),0,0);self._button(bar,"Quarantine",self.quarantine,0,1)
        p=self.views["SDK"];bar=ctk.CTkFrame(p,fg_color="transparent");bar.grid(row=0,column=0,sticky="ew");self._button(bar,"Create Plugin Skeleton",self.skeleton,0,0)
    def refresh(self):self.manager.refresh();self.render();self.render_official();self.render_active()
    def render(self):
        items=self.manager.list(self.search.get() if hasattr(self,"search") else "");self.selected=self.selected if self.selected and any(v.plugin_id==self.selected.plugin_id for v in items) else (items[-1] if items else None);statuses=self.manager.loader.statuses;active=sum(s.state.value=="active" for s in statuses.values());failed=sum(s.state.value=="failed" for s in statuses.values());enabled=sum(v.enabled for v in items);untrusted=sum(v.trust_state.value=="untrusted" for v in items);changed=self.manager.changed_digest_count();self.summary.configure(text=f"Installed {len(items)} · Enabled {enabled} · Active {active} · Untrusted {untrusted} · Failed {failed} · Changed {changed}");self._set(self.installed,"\n\n".join(f"{m.display_label}\nID: {m.plugin_id}\nDigest: {m.package_digest}\nStatus: {getattr(statuses.get(m.plugin_id),'state','discovered')}" for m in items) or "No installed plugins. Files in examples do not install or execute automatically.");self._details()
    def _details(self):
        m=self.selected
        if not m:
            for name in ("details_view","permissions_view","contributions_view","diagnostics_view"):self._set(getattr(self,name),"No plugin selected.")
        else:
            self._set(self.details_view,json.dumps(m.to_dict(),indent=2,default=str));approved=self.manager.trust.approved(m.plugin_id,m.package_digest);self._set(self.permissions_view,"Requested:\n"+"\n".join(f"- {v}{' — HIGH IMPACT' if v in HIGH_IMPACT else ''}" for v in m.requested_capabilities)+"\n\nApproved:\n"+"\n".join(approved));self._set(self.contributions_view,"\n".join(f"{c.contribution_type} · {c.contribution_id} · {c.title}" for c in self.manager.registry.by_plugin(m.plugin_id)) or "No active contributions; contributions register only after explicit trusted load.");status=self.manager.loader.statuses.get(m.plugin_id);self._set(self.diagnostics_view,f"Digest: {m.package_digest}\nTrust: {m.trust_state.value}\nEnabled: {m.enabled}\nLoader: {getattr(status,'state','discovered')}\nLast error: {getattr(status,'last_error','')}")
        self._set(self.sdk_view,"Plugin API v1.1 (compatible with v1.0)\n\nDocumentation: docs/plugin-sdk/README.md\nHarmless disabled example: plugins/examples/hello_plugin\n\nPython plugins are trusted code. In-process loading is not a hardened sandbox. No download, update, enable, trust, or load occurs automatically.")
    def render_official(self):
        canvas=self.official_cards._parent_canvas
        try:offset=max(0.0,float(canvas.canvasy(0)))
        except (TypeError,ValueError,tk.TclError):offset=0.0
        for child in self.official_cards.winfo_children():child.destroy()
        for row,item in enumerate(self.manager.official()):
            card=ctk.CTkFrame(self.official_cards,fg_color=self.theme["panel_alt"],border_width=1,border_color=self.theme["border"]);card.grid(row=row,column=0,sticky="ew",padx=8,pady=6);card.grid_columnconfigure(0,weight=1);m=item.manifest
            title=ctk.CTkLabel(card,text=f"{m.name} · {m.version} · Official",text_color=self.theme["gold"],anchor="w",font=self.theme["header_font"],wraplength=420);title.grid(row=0,column=0,sticky="ew",padx=10,pady=(8,2))
            description=ctk.CTkLabel(card,text=f"{m.description}\nCapabilities: {len(m.requested_capabilities)} · {'Installed' if item.installed else 'Available'}",text_color=self.theme["text"],anchor="w",justify="left",wraplength=420);description.grid(row=1,column=0,sticky="ew",padx=10,pady=(0,8))
            button=self._button(card,"Installed" if item.installed else "Install",lambda pid=m.plugin_id,digest=item.package_digest:self.install_official(pid,digest),0,1);button.configure(state="disabled" if item.installed else "normal")
            card.bind("<Configure>",lambda _event,c=card,t=title,d=description,b=button:self._resize_official_card(c,t,d,b),add="+")
        self._callbacks.schedule_idle(self._restore_official_scroll,offset)
    def _resize_official_card(self,card,title,description,button):
        try:
            logical_width=card._reverse_widget_scaling(card.winfo_width())
            available=max(180,int(logical_width-float(button.cget("width"))-50))
            if getattr(title,"_susadb_wraplength",None)==available:return
            title._susadb_wraplength=available;description._susadb_wraplength=available
            title.configure(wraplength=available);description.configure(wraplength=available)
        except (AttributeError,TypeError,ValueError,tk.TclError):return
    def _sync_official_scrollregion(self,_event=None):
        canvas=self.official_cards._parent_canvas
        try:
            region=canvas.bbox("all")
            if region:canvas.configure(scrollregion=region)
        except (AttributeError,tk.TclError):return
    def _restore_official_scroll(self,offset):
        canvas=self.official_cards._parent_canvas
        if not widget_exists(canvas):return
        try:
            self._sync_official_scrollregion()
            region=tuple(float(value) for value in str(canvas.cget("scrollregion")).split())
            extent=region[3]-region[1] if len(region)==4 else 0.0
            viewport=max(1,canvas.winfo_height())
            offset=clamp_scroll_offset(offset,extent,viewport)
            canvas.yview_moveto(offset/extent if extent else 0)
        except (TypeError,ValueError,tk.TclError):return
    def install_official(self,plugin_id=None,digest=""):
        if plugin_id:self._run("Install official plugin",lambda:self.manager.install_official(plugin_id,digest))
    def render_active(self):
        for child in self.active_host.winfo_children():child.destroy()
        panels=list(self.manager.registry.list("pentest-panel"))
        if not panels:ctk.CTkLabel(self.active_host,text="No active plugin panels. Install, approve, enable, and explicitly load a plugin.",text_color=self.theme["muted"],wraplength=800).grid(row=0,column=0,sticky="nsew");return
        for row,contribution in enumerate(panels):
            line=ctk.CTkFrame(self.active_host,fg_color=self.theme["panel_alt"],border_width=1,border_color=self.theme["border"]);line.grid(row=row,column=0,sticky="ew",padx=8,pady=5);line.grid_columnconfigure(0,weight=1);host=self.winfo_toplevel();opened=bool(getattr(host,"addon_window_host",None) and host.addon_window_host.is_open(contribution.contribution_id));ctk.CTkLabel(line,text=f"{contribution.title}\nLoaded · Window {'open' if opened else 'closed'}",text_color=self.theme["gold"],anchor="w",justify="left").grid(row=0,column=0,sticky="ew",padx=8,pady=6);self._button(line,"Focus" if opened else "Open",lambda cid=contribution.contribution_id:getattr(self.winfo_toplevel(),"open_addon_window")(cid),0,1);self._button(line,"Unload",lambda pid=contribution.plugin_id:self._done("Unload",self.manager.unload(pid)),0,2)
    def open_contribution(self,contribution_id):
        item=next((value for value in self.manager.registry.list("pentest-panel") if value.contribution_id==contribution_id),None)
        self.tabs.set("Active Panels")
        if item and hasattr(self.winfo_toplevel(),"open_addon_window"):self.winfo_toplevel().open_addon_window(item.contribution_id)
    def _run(self,title,fn):self.warning.configure(text=title+"…",text_color=self.theme["gold"]);BackgroundWorker(fn,callback=lambda r:self.after(0,self._done,title,r)).start()
    def _done(self,title,r):self.warning.configure(text=(title+" complete.") if r.ok else (r.error or title+" failed."),text_color=self.theme["success"] if r.ok else self.theme["error"]);self.refresh()
    def install(self):
        path=filedialog.askopenfilename(parent=self.winfo_toplevel(),title="Select local plugin ZIP") or filedialog.askdirectory(parent=self.winfo_toplevel(),title="Select local plugin directory")
        if path:self._run("Store disabled plugin",lambda:self.manager.install(path))
    def _id(self):return self.selected.plugin_id if self.selected else None
    def enable(self):
        if self._id():self._done("Enable",self.manager.enable(self._id()))
    def disable(self):
        if self._id():self._done("Disable",self.manager.disable(self._id()))
    def load(self):
        if self._id() and self.confirm("Load Trusted Plugin","Load this explicitly enabled, digest-verified plugin as trusted Python code?"):self._done("Load",self.manager.load(self._id()))
    def unload(self):
        if self._id():self._done("Unload",self.manager.unload(self._id()))
    def reload(self):
        if self._id() and self.confirm("Reload Plugin","Unload and reload this trusted plugin?"):self._done("Reload",self.manager.reload(self._id()))
    def uninstall(self):
        if self._id() and self.confirm("Uninstall Plugin","Remove executable plugin files? Plugin state and assessment data remain preserved."):self._done("Uninstall",self.manager.uninstall(self._id(),True))
    def approve(self):
        if not self.selected:return
        high=bool(set(self.selected.requested_capabilities)&HIGH_IMPACT);confirmed=not high or self.confirm("High-impact Plugin Permissions","Approve the displayed high-impact capabilities for this exact package digest?");self._done("Trust approval",self.manager.approve(self._id(),self.selected.requested_capabilities,confirmed))
    def revoke(self):
        if self._id():self._done("Revoke trust",self.manager.revoke(self._id()))
    def verify_all(self):
        for m in tuple(self.manager.list()):self.manager.verify(m.plugin_id)
        self.refresh()
    def disable_all(self):
        for m in tuple(self.manager.list()):
            if m.trust_state.value!="built-in":self.manager.disable(m.plugin_id)
        self.refresh()
    def quarantine(self):
        if self._id() and self.confirm("Quarantine Plugin","Disable, revoke trust, and move this plugin package to quarantine?"):self._done("Quarantine",self.manager.quarantine(self._id()))
    def skeleton(self):
        pid=simpledialog.askstring("Plugin Skeleton","Stable plugin ID (lowercase):",parent=self.winfo_toplevel())
        if not pid:return
        dest=self.manager.store.root/"disabled"/pid/"0.1.0"
        if dest.exists():self.warning.configure(text="Skeleton path already exists.",text_color=self.theme["error"]);return
        try:
            dest.mkdir(parents=True);(dest/"manifest.json").write_text(json.dumps({"plugin_id":pid,"name":pid,"version":"0.1.0","entry_point":"plugin.py:Plugin","enabled":False},indent=2),encoding="utf-8");(dest/"plugin.py").write_text("class Plugin:\n    def activate(self, api):\n        return ()\n    def deactivate(self):\n        pass\n",encoding="utf-8");self.warning.configure(text=f"Disabled skeleton created at {dest}. It was not imported, enabled, or executed.",text_color=self.theme["gold"])
        except (OSError,ValueError) as exc:self.warning.configure(text=str(exc),text_color=self.theme["error"])
    def _copy(self,text):self.clipboard_clear();self.clipboard_append(text)
    def set_selected_device(self,_):pass
    def set_selected_target(self,_):pass
    def cleanup(self):
        if getattr(self,"unsubscribe",None):self.unsubscribe();self.unsubscribe=None
        self._callbacks.cancel_all()
        self.manager.shutdown()
