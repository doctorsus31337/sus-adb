"""Focused non-modal Add-ons Center with explicit lifecycle cards."""
from __future__ import annotations

import tkinter as tk
from tkinter import filedialog,messagebox

import customtkinter as ctk

from app.core.app_metadata import METADATA
from app.core.responsive_layout import estimated_button_width
from app.gui.customtkinter_compat import (
    PendingCallbackOwner,
    ScopedScrollRouter,
    clamp_scroll_offset,
    focused_within,
    safe_focus,
    widget_exists,
)
from app.gui.read_only_text import ReadOnlyTextView
from app.plugins.addon_presenter import card_actions,card_spec
from app.plugins.plugin_capabilities import HIGH_IMPACT


class AddonCardScroller(ctk.CTkFrame):
    """One bounded vertical card viewport with scoped input bindings."""

    BOTTOM_PADDING=10

    def __init__(self,parent,theme,resize_callback):
        super().__init__(
            parent,
            fg_color=theme["panel"],
            border_width=1,
            border_color=theme["border"],
            corner_radius=8,
        )
        self.theme=theme
        self.resize_callback=resize_callback
        self.grid_columnconfigure(0,weight=1)
        self.grid_rowconfigure(0,weight=1)
        self._parent_canvas=tk.Canvas(
            self,
            background=theme["panel"],
            borderwidth=0,
            highlightthickness=1,
            highlightbackground=theme["border"],
            highlightcolor=theme["gold"],
            takefocus=True,
            yscrollincrement=1,
        )
        self._parent_canvas.grid(row=0,column=0,sticky="nsew")
        self._scrollbar=ctk.CTkScrollbar(
            self,
            orientation="vertical",
            width=18,
            command=self._parent_canvas.yview,
            fg_color=theme["panel"],
            button_color=theme["gold_dark"],
            button_hover_color=theme["red_hover"],
        )
        self._scrollbar.grid(row=0,column=1,sticky="ns",padx=(5,3),pady=3)
        self._parent_canvas.configure(yscrollcommand=self._scrollbar.set)
        self.content=ctk.CTkFrame(
            self._parent_canvas,
            fg_color=theme["panel"],
            corner_radius=0,
        )
        self._window_id=self._parent_canvas.create_window(
            0,0,window=self.content,anchor="nw"
        )
        self._callbacks=PendingCallbackOwner(self)
        self._sync_pending=None
        self._restore_offset=None
        self._last_width=0
        self._scroll_router=None
        self.content.bind("<Configure>",self._content_configured,add="+")
        self._parent_canvas.bind(
            "<Configure>",self._canvas_configured,add="+"
        )

    @property
    def viewport_width(self):
        return max(1,self._parent_canvas.winfo_width()-2)

    @property
    def viewport_height(self):
        return max(1,self._parent_canvas.winfo_height()-2)

    @property
    def content_height(self):
        region=self._parent_canvas.cget("scrollregion")
        try:
            values=tuple(float(value) for value in str(region).split())
        except (TypeError,ValueError):
            return 0.0
        return values[3]-values[1] if len(values)==4 else 0.0

    def attach_input(self,owner):
        self.detach_input()
        self._scroll_router=ScopedScrollRouter(
            self,self._parent_canvas,owner=owner,scroll_units=48,
        )

    def detach_input(self):
        if self._scroll_router is not None:self._scroll_router.close()
        self._scroll_router=None

    def check_if_master_is_canvas(self,widget):
        """Return true only for live widgets inside this bounded viewport."""
        if not isinstance(widget,tk.Misc):return False
        seen=set()
        try:
            while widget is not None and id(widget) not in seen:
                if widget in {self,self._parent_canvas,self.content}:return True
                seen.add(id(widget))
                widget=getattr(widget,"master",None)
        except (AttributeError,tk.TclError):
            return False
        return False

    _check_if_valid_scroll=check_if_master_is_canvas

    def _mouse_wheel_all(self,event):
        return (
            self._scroll_router._wheel(event)
            if self._scroll_router is not None else None
        )

    def _keyboard_scroll(self,event):
        return (
            self._scroll_router._key(event)
            if self._scroll_router is not None else None
        )

    def scroll_offset(self):
        if not widget_exists(self._parent_canvas):return 0.0
        try:return max(0.0,float(self._parent_canvas.canvasy(0)))
        except (TypeError,ValueError,tk.TclError):return 0.0

    def schedule_scrollregion(self,preserve_offset=None):
        if preserve_offset is not None:
            self._restore_offset=max(0.0,float(preserve_offset))
        if self._sync_pending is not None:return
        def synchronize():
            self._sync_pending=None
            self._sync_scrollregion()
        self._sync_pending=self._callbacks.schedule_idle(synchronize)

    def _requested_content_height(self):
        managed=(
            child for child in self.content.winfo_children()
            if child.winfo_manager()
        )
        return max(
            (
                child.winfo_y()+max(child.winfo_height(),child.winfo_reqheight())
                for child in managed
            ),
            default=1,
        )

    def _sync_scrollregion(self):
        if not widget_exists(self):return
        canvas_width=self.viewport_width
        self._parent_canvas.itemconfigure(self._window_id,width=canvas_width)
        self.update_idletasks()
        requested=self._requested_content_height()
        self._parent_canvas.itemconfigure(self._window_id,height=requested)
        extent=max(
            self.viewport_height,
            requested+self.BOTTOM_PADDING,
        )
        self._parent_canvas.configure(
            scrollregion=(0,0,canvas_width,extent)
        )
        offset=self.scroll_offset() if self._restore_offset is None else self._restore_offset
        self._restore_offset=None
        offset=clamp_scroll_offset(offset,extent,self.viewport_height)
        self._parent_canvas.yview_moveto(offset/extent if extent else 0)

    def _content_configured(self,_event):
        self.schedule_scrollregion(self.scroll_offset())

    def _canvas_configured(self,event):
        offset=self.scroll_offset()
        width=max(1,int(event.width)-2)
        self._parent_canvas.itemconfigure(self._window_id,width=width)
        extent=max(
            max(1,int(event.height)-2),
            self._requested_content_height()+self.BOTTOM_PADDING,
        )
        self._parent_canvas.configure(scrollregion=(0,0,width,extent))
        if width!=self._last_width:
            self._last_width=width
            self.resize_callback(width,offset)
        self.schedule_scrollregion(offset)

    def ensure_visible(self,widget):
        if not self.check_if_master_is_canvas(widget) or not widget_exists(widget):
            return
        self.schedule_scrollregion(self.scroll_offset())
        try:
            top=widget.winfo_rooty()-self.content.winfo_rooty()
            bottom=top+widget.winfo_height()
            view_top=self.scroll_offset()
            view_bottom=view_top+self.viewport_height
            target=view_top
            if top<view_top:target=top
            elif bottom>view_bottom:target=bottom-self.viewport_height
            extent=max(self.content_height,self.viewport_height)
            target=clamp_scroll_offset(target,extent,self.viewport_height)
            self._parent_canvas.yview_moveto(target/extent if extent else 0)
        except tk.TclError:
            return

    def close(self):
        self.detach_input()
        self._callbacks.cancel_all()


class AddonCard(ctk.CTkFrame):
    def __init__(self,parent,theme,spec,actions,focus_callback):
        super().__init__(
            parent,
            fg_color=theme["panel_alt"],
            border_width=1,
            border_color=theme["border"],
            corner_radius=10,
        )
        self.plugin_id=spec.plugin_id
        self.theme=theme
        self.action_callback=actions
        self.focus_callback=focus_callback
        self.spec=None
        self.buttons={}
        self.actions=()
        self.button_bindings=[]
        self.callbacks=PendingCallbackOwner(self)
        self.grid_columnconfigure(0,weight=1)
        self.name_label=ctk.CTkLabel(
            self,text="",text_color=theme["gold"],
            font=theme["header_font"],anchor="w",wraplength=390,
        )
        self.name_label.grid(row=0,column=0,sticky="ew",padx=12,pady=(10,2))
        self.version_label=ctk.CTkLabel(
            self,text="",text_color=theme["muted"],anchor="w",
        )
        self.version_label.grid(row=1,column=0,sticky="ew",padx=12)
        self.description_label=ctk.CTkLabel(
            self,text="",text_color=theme["text"],anchor="nw",
            justify="left",wraplength=390,height=54,
        )
        self.description_label.grid(
            row=2,column=0,sticky="ew",padx=12,pady=5
        )
        self.state_label=ctk.CTkLabel(
            self,text="",text_color=theme["gold"],anchor="w",justify="left",
        )
        self.state_label.grid(row=3,column=0,sticky="ew",padx=12)
        self.privacy_label=ctk.CTkLabel(
            self,text="",text_color=theme["muted"],anchor="nw",
            justify="left",wraplength=390,height=48,
        )
        self.privacy_label.grid(
            row=4,column=0,sticky="ew",padx=12,pady=5
        )
        self.bar=ctk.CTkFrame(self,fg_color="transparent")
        self.bar.grid(row=5,column=0,sticky="ew",padx=8,pady=(2,10))
        self.bar.bind("<Configure>",self._bar_configured,add="+")
        self.update_spec(spec)

    def _bar_configured(self,_event):
        self.callbacks.schedule_idle(self._layout_actions)

    @staticmethod
    def _owned_button_event(event,button):
        return (
            getattr(event,"widget",None) is button
            and widget_exists(button)
            and bool(button.winfo_ismapped())
        )

    def _focus_in(self,event,button):
        if not self._owned_button_event(event,button):return None
        button.configure(border_color=self.theme["gold"])
        self.focus_callback(button)
        return None

    def _focus_out(self,event,button):
        if getattr(event,"widget",None) is not button:return None
        if widget_exists(button):
            button.configure(border_color=self.theme["gold_dark"])
        return None

    def _invoke_focused(self,event,button):
        if (
            not self._owned_button_event(event,button)
            or getattr(event,"keysym","") not in {"Return","space"}
            or not focused_within(button)
        ):
            return None
        button.invoke()
        return "break"

    def _bind_button(self,button,sequence,callback):
        binding_id=tk.Frame.bind(button,sequence,callback,add="+")
        if binding_id:
            self.button_bindings.append((button,sequence,binding_id))

    def _unbind_buttons(self):
        for button,sequence,binding_id in tuple(self.button_bindings):
            if widget_exists(button):
                try:tk.Frame.unbind(button,sequence,binding_id)
                except tk.TclError:pass
        self.button_bindings.clear()

    @property
    def binding_count(self):
        return len(self.button_bindings)

    def _layout_actions(self):
        if not widget_exists(self.bar):return
        wanted=[self.buttons[name] for name in self.actions]
        if not wanted:return
        available=max(1,self.bar.winfo_width())
        columns=1
        for candidate in range(len(wanted),0,-1):
            rows=[
                wanted[index:index+candidate]
                for index in range(0,len(wanted),candidate)
            ]
            if all(
                sum(button.winfo_reqwidth()+6 for button in row)<=available
                for row in rows
            ):
                columns=candidate
                break
        for index,button in enumerate(wanted):
            button.grid(
                row=index//columns,column=index%columns,padx=3,pady=2
            )

    def update_spec(self,spec):
        if spec.plugin_id!=self.plugin_id:
            raise ValueError("Addon card identity cannot change.")
        self.spec=spec
        impact=" · High-impact approval" if spec.high_impact else ""
        self.name_label.configure(text=spec.name)
        self.version_label.configure(
            text=f"Official · v{spec.version} · {spec.preferred_mode.value.title()}"
        )
        self.description_label.configure(text=spec.description)
        update_line=f"\n{spec.update_status}" if spec.update_status else ""
        self.state_label.configure(
            text=(
                f"Capabilities: {spec.capability_count}{impact}\n"
                f"State: {spec.lifecycle_status}"
                f"{update_line}"
            ),
            text_color=self.theme["error"] if spec.high_impact else self.theme["gold"],
        )
        self.privacy_label.configure(text=spec.privacy_note)
        wanted=card_actions(spec)
        for name,button in self.buttons.items():
            if name not in wanted:
                if focused_within(button):
                    target=self.buttons.get("Details")
                    if widget_exists(target):
                        tk.Frame.focus_set(target)
                    else:
                        safe_focus(self)
                button.grid_remove()
        for name in wanted:
            button=self.buttons.get(name)
            if button is None:
                button=ctk.CTkButton(
                    self.bar,
                    text=name,
                    width=estimated_button_width(name,90),
                    fg_color=(
                        self.theme["gold_dark"]
                        if name in {"Details","Focus"}
                        else self.theme["red"]
                    ),
                    hover_color=self.theme["red_hover"],
                    text_color=self.theme["text"],
                    border_width=1,
                    border_color=self.theme["gold_dark"],
                    command=lambda action=name:self.action_callback(
                        action,self.plugin_id
                    ),
                )
                self._bind_button(
                    button,
                    "<FocusIn>",
                    lambda event,target=button:self._focus_in(event,target),
                )
                self._bind_button(
                    button,
                    "<FocusOut>",
                    lambda event,target=button:self._focus_out(event,target),
                )
                for sequence in ("<Return>","<space>"):
                    self._bind_button(
                        button,
                        sequence,
                        lambda event,target=button:self._invoke_focused(
                            event,target
                        ),
                    )
                tk.Frame.configure(button,takefocus=True)
                if hasattr(button,"_canvas"):
                    tk.Canvas.configure(button._canvas,takefocus=False)
                self.buttons[name]=button
        self.actions=wanted
        self.callbacks.schedule_idle(self._layout_actions)

    def destroy(self):
        self.callbacks.cancel_all()
        self._unbind_buttons()
        super().destroy()


class UpdateReviewDialog(ctk.CTkToplevel):
    """Non-mutating official-addon comparison with one explicit review action."""

    def __init__(self,parent,theme,review,mark_callback,close_callback):
        super().__init__(parent)
        self.theme=theme
        self.review=review
        self.mark_callback=mark_callback
        self.close_callback=close_callback
        self._closed=False
        self.title("Review Official Addon Update")
        self.configure(fg_color=theme["bg"])
        self.geometry(parent._center(760,580))
        self.minsize(680,500)
        self.transient(parent)
        self.grid_columnconfigure(0,weight=1)
        self.grid_rowconfigure(1,weight=1)
        self.protocol("WM_DELETE_WINDOW",self.close)
        self.bind("<Escape>",lambda _event:self.close(),add="+")
        ctk.CTkLabel(
            self,text="REVIEW OFFICIAL ADDON UPDATE",
            font=("Times New Roman",22,"bold"),text_color=theme["gold"],
        ).grid(row=0,column=0,sticky="ew",padx=18,pady=(16,8))
        details=ReadOnlyTextView(
            self,fg_color=theme["terminal_bg"],
            text_color=theme["terminal_text"],border_width=1,
            border_color=theme["gold_dark"],wrap="word",
        )
        details.grid(row=1,column=0,sticky="nsew",padx=18,pady=6)
        details.replace(self._summary())
        bar=ctk.CTkFrame(self,fg_color="transparent")
        bar.grid(row=2,column=0,sticky="ew",padx=18,pady=(8,16))
        bar.grid_columnconfigure(0,weight=1)
        ctk.CTkButton(
            bar,text="Close",command=self.close,width=110,
            fg_color=theme["gold_dark"],hover_color=theme["red_hover"],
            text_color=theme["text"],border_width=1,
            border_color=theme["gold"],
        ).grid(row=0,column=1,padx=5)
        mark=ctk.CTkButton(
            bar,text="Mark Reviewed",command=self.mark_reviewed,width=150,
            fg_color=theme["red"],hover_color=theme["red_hover"],
            text_color=theme["text"],border_width=1,
            border_color=theme["gold_dark"],
        )
        mark.grid(row=0,column=2,padx=5)
        self.grab_set()
        mark.focus_set()

    @staticmethod
    def _values(values):
        return ", ".join(values) if values else "None"

    def _summary(self):
        review=self.review
        warning=(
            "\nWARNING: Package contents changed without a version change.\n"
            if review.digest_only_changed else ""
        )
        return (
            f"Addon: {review.name}\n"
            f"Installed version: {review.installed_version}\n"
            f"Candidate version: {review.candidate_version}\n"
            f"Installed digest: {review.installed_digest[:12]}…\n"
            f"Candidate digest: {review.candidate_digest[:12]}…\n"
            f"Publisher: {review.publisher}\n"
            f"Source: {review.source_classification}\n"
            f"{warning}\n"
            "Requested capabilities\n"
            f"  Added: {self._values(review.capability_additions)}\n"
            f"  Removed: {self._values(review.capability_removals)}\n\n"
            "Contributions\n"
            f"  Added: {self._values(review.contribution_additions)}\n"
            f"  Removed: {self._values(review.contribution_removals)}\n"
            f"  Changed: {self._values(review.contribution_changes)}\n\n"
            f"Presentation metadata changed: "
            f"{self._values(review.presentation_changes)}\n"
            f"Executable/plugin files changed: "
            f"{'Yes' if review.executable_files_changed else 'No'}\n"
            f"Version changed: {'Yes' if review.version_changed else 'No'}\n\n"
            "Mark Reviewed records only this exact candidate digest. It does "
            "not install, unload, disable, trust, approve, enable, load, or "
            "open the addon. Prior trust and capability approval do not "
            "transfer if the changed package is later installed."
        )

    def mark_reviewed(self):
        result=self.mark_callback()
        self.close(result)

    def close(self,result=None):
        if self._closed:return
        self._closed=True
        try:self.grab_release()
        except tk.TclError:pass
        self.destroy()
        self.close_callback(result)


class AddonsCenter(ctk.CTkToplevel):
    def __init__(
        self,parent,theme,manager,window_host,on_close=None,
        destination_chooser=None,help_callback=None,
    ):
        super().__init__(parent)
        self.theme=theme
        self.manager=manager
        self.window_host=window_host
        self.on_close=on_close
        self.help_callback=help_callback
        self.destination_chooser=destination_chooser or (
            lambda:filedialog.askdirectory(
                parent=self,title="Choose template export destination"
            )
        )
        self.cards={}
        self.visible_plugin_ids=()
        self.status_message=""
        self.review_dialog=None
        self.title(f"{METADATA.application_name} — Add-ons Center")
        self.configure(fg_color=theme["bg"])
        self.minsize(900,650)
        self.geometry(self._center(1180,780))
        self.grid_columnconfigure(0,weight=1)
        self.grid_rowconfigure(2,weight=1)
        self.protocol("WM_DELETE_WINDOW",self.close)
        heading=ctk.CTkFrame(self,fg_color="transparent")
        heading.grid(row=0,column=0,sticky="ew",padx=18,pady=(16,6))
        heading.grid_columnconfigure(0,weight=1)
        ctk.CTkLabel(
            heading,text="⚙ ADD-ONS CENTER ⚙",
            font=("Times New Roman",28,"bold"),text_color=theme["gold"],
        ).grid(row=0,column=0,sticky="ew")
        ctk.CTkButton(
            heading,text="Help",
            command=lambda:self.help_callback("addons-center")
            if self.help_callback else None,
            width=90,fg_color=theme["red"],hover_color=theme["red_hover"],
            text_color=theme["text"],border_width=1,
            border_color=theme["gold_dark"],
        ).grid(row=0,column=1,padx=(8,0))
        row=ctk.CTkFrame(self,fg_color="transparent")
        row.grid(row=1,column=0,sticky="ew",padx=18,pady=5)
        row.grid_columnconfigure(0,weight=1)
        self.search=ctk.CTkEntry(
            row,placeholder_text="Search available and installed addons",
            fg_color=theme["terminal_bg"],border_color=theme["gold_dark"],
            text_color=theme["text"],
        )
        self.search.grid(row=0,column=0,sticky="ew",padx=(0,8))
        self.search.bind("<Return>",lambda _event:self.refresh(),add="+")
        ctk.CTkButton(
            row,text="Apply",width=90,fg_color=theme["red"],
            hover_color=theme["red_hover"],command=self.refresh,
        ).grid(row=0,column=1)
        self.card_area=AddonCardScroller(self,theme,self._layout)
        self.card_area.grid(
            row=2,column=0,sticky="nsew",padx=18,pady=8
        )
        self.card_area.attach_input(self)
        self.footer=ctk.CTkLabel(
            self,
            text=(
                "Discovery never installs, trusts, approves, enables, "
                "loads, or runs an addon."
            ),
            text_color=theme["gold"],anchor="w",wraplength=1050,
        )
        self.footer.grid(
            row=3,column=0,sticky="ew",padx=18,pady=(2,12)
        )
        self.callbacks=PendingCallbackOwner(self)
        self.unsubscribe=manager.subscribe(
            lambda _event,_plugin:self.callbacks.schedule(0,self.refresh)
        )
        self.refresh()

    def _center(self,width,height):
        screen_width=self.winfo_screenwidth()
        screen_height=self.winfo_screenheight()
        width=min(width,screen_width)
        height=min(height,screen_height)
        return (
            f"{width}x{height}+{max(0,(screen_width-width)//2)}"
            f"+{max(0,(screen_height-height)//2)}"
        )

    def _layout(self,_viewport_width=None,preserve_offset=None):
        columns=2 if self.card_area.viewport_width>=900 else 1
        for card in self.cards.values():card.grid_remove()
        for index,plugin_id in enumerate(self.visible_plugin_ids):
            self.cards[plugin_id].grid(
                row=index//columns,column=index%columns,
                sticky="nsew",padx=8,pady=8,
            )
        for column in range(2):
            self.card_area.content.grid_columnconfigure(
                column,weight=1 if column<columns else 0
            )
        self.card_area.schedule_scrollregion(preserve_offset)

    def refresh(self):
        if not widget_exists(self):return
        position=self.card_area.scroll_offset() if hasattr(self,"card_area") else 0
        query=self.search.get().casefold() if hasattr(self,"search") else ""
        specs={}
        visible=[]
        for item in self.manager.official():
            spec=card_spec(item,self.manager,self.window_host)
            specs[spec.plugin_id]=spec
            if not query or query in (
                spec.name+spec.plugin_id+spec.description
            ).casefold():
                visible.append(spec.plugin_id)
        for plugin_id in tuple(self.cards):
            if plugin_id not in specs:
                card=self.cards.pop(plugin_id)
                if focused_within(card):safe_focus(self.search)
                card.destroy()
        ordered={}
        for plugin_id,spec in specs.items():
            card=self.cards.get(plugin_id)
            if card is None:
                card=AddonCard(
                    self.card_area.content,self.theme,spec,self.action,
                    self.card_area.ensure_visible,
                )
            else:
                card.update_spec(spec)
            ordered[plugin_id]=card
        hidden=set(ordered)-set(visible)
        for plugin_id in hidden:
            if focused_within(ordered[plugin_id]):safe_focus(self.search)
        self.cards=ordered
        self.visible_plugin_ids=tuple(visible)
        self._layout(preserve_offset=position)
        self.footer.configure(
            text=self.status_message or (
                f"{len(self.visible_plugin_ids)} official addons · "
                "Every lifecycle transition remains explicit."
            )
        )

    def focus_addon(self, query):
        """Focus/filter the existing catalog without changing addon lifecycle."""
        self.deiconify()
        self.lift()
        self.search.delete(0,"end")
        self.search.insert(0,str(query or ""))
        self.refresh()
        safe_focus(self.search)
        return self

    def _panel_id(self,plugin_id):
        return next(
            (
                contribution.contribution_id
                for contribution in self.manager.registry.by_plugin(plugin_id)
                if contribution.contribution_type=="pentest-panel"
            ),
            "",
        )

    def action(self,name,plugin_id):
        item=(
            self.manager.catalog.get(plugin_id,self.manager.records)
            if self.manager.catalog else None
        )
        if name=="Details" and item:
            manifest=(
                self.manager.records[plugin_id][2]
                if plugin_id in self.manager.records else item.manifest
            )
            messagebox.showinfo(
                manifest.name,
                f"{manifest.description}\n\n"
                f"Capabilities: "
                f"{', '.join(manifest.requested_capabilities) or 'None'}"
                f"\n\n{manifest.caution_text}",
                parent=self,
            )
        elif name=="Install" and item:
            self._result(
                self.manager.install_official(plugin_id,item.package_digest)
            )
        elif name=="Review Update" and item:
            review=self.manager.official_update_review(
                plugin_id,item.package_digest
            )
            if not review.ok:self._result(review)
            elif widget_exists(self.review_dialog):
                self.review_dialog.lift()
                self.review_dialog.focus_force()
            else:
                self.review_dialog=UpdateReviewDialog(
                    self,self.theme,review.status,
                    lambda:self.manager.mark_official_update_reviewed(
                        plugin_id,item.package_digest
                    ),
                    self._review_closed,
                )
        elif name=="Install Update" and item:
            self._result(
                self.manager.install_official_update(
                    plugin_id,item.package_digest
                )
            )
        elif name=="Trust":
            manifest=self.manager.records[plugin_id][2]
            digest=self.manager.records[plugin_id][1].package_digest
            confirmed=messagebox.askyesno(
                "Trust Zero-Capability Addon",
                f"Addon: {manifest.name}\nVersion: {manifest.version}\n"
                f"Package digest: {digest}\n\n"
                "This addon requests zero capabilities. Trust is bound only "
                "to this exact digest. Trusting does not enable, load, or open "
                "it.\n\nTrust this package?",
                parent=self,
            )
            self._result(
                self.manager.trust_zero_capability(plugin_id,confirmed)
            )
        elif name in {"Permissions","Review Permissions"}:
            manifest=self.manager.records[plugin_id][2]
            confirmed=(
                not bool(set(manifest.requested_capabilities)&HIGH_IMPACT)
                or messagebox.askyesno(
                    "Approve Addon Permissions",
                    "Approve the displayed capabilities for this exact "
                    "package digest?",
                    parent=self,
                )
            )
            self._result(
                self.manager.approve(
                    plugin_id,manifest.requested_capabilities,confirmed
                )
            )
        elif name=="Enable":
            self._result(self.manager.enable(plugin_id))
        elif name=="Load":
            self._result(self.manager.load(plugin_id))
        elif name in {"Open","Focus"}:
            contribution_id=self._panel_id(plugin_id)
            window=self.window_host.open(contribution_id)
            self.refresh()
            if window is None:
                self.footer.configure(
                    text=self.window_host.errors.get(
                        contribution_id,
                        "Addon window could not be opened.",
                    ),
                    text_color=self.theme["error"],
                )
        elif name=="Unload":
            self._result(self.manager.unload(plugin_id))
        else:
            action=(
                next(
                    (
                        value
                        for value in item.manifest.addon_ui.get(
                            "catalog_actions",()
                        )
                        if value.get("label")==name
                    ),
                    None,
                )
                if item else None
            )
            if action and action.get("kind")=="export-template":
                destination=self.destination_chooser()
                if destination:
                    result=self.manager.catalog.export_template(
                        plugin_id,action["action_id"],destination,
                        item.package_digest,
                    )
                    self.status_message=(
                        f"Exported {result.file_count} files "
                        f"({result.total_bytes} bytes) to {result.path}. "
                        f"Source digest: {result.source_digest}. The copy was "
                        "not installed or executed."
                        if result.ok else result.error
                    )
                    self.footer.configure(
                        text_color=(
                            self.theme["success"]
                            if result.ok else self.theme["error"]
                        )
                    )
                    self.refresh()

    def _result(self,result):
        self.status_message=(
            "Operation complete."
            if result.ok else (result.error or "Operation failed.")
        )
        self.footer.configure(
            text_color=(
                self.theme["success"] if result.ok else self.theme["error"]
            )
        )
        self.refresh()

    def _review_closed(self,result=None):
        self.review_dialog=None
        if result is not None:self._result(result)

    def close(self):
        if widget_exists(self.review_dialog):self.review_dialog.close()
        if self.unsubscribe:
            self.unsubscribe()
            self.unsubscribe=None
        self.callbacks.cancel_all()
        self.card_area.close()
        safe_focus(self.master)
        if self.on_close:self.on_close()
        self.destroy()
