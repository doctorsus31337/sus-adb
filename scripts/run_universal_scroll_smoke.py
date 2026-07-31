"""Isolated synthetic acceptance for application-owned universal scrolling."""
from __future__ import annotations

import sys
import tempfile
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from scripts.run_gui_smoke import isolated_smoke_environment


def event(widget,*,num=None,delta=0,keysym="",state=0):
    return SimpleNamespace(
        widget=widget,num=num,delta=delta,keysym=keysym,state=state,
    )


def pump(widget):
    widget.update_idletasks()
    widget.update()
    widget.update_idletasks()


def force_extent(frame,height=7000):
    canvas=frame._parent_canvas
    canvas.configure(
        yscrollincrement=1,
        scrollregion=(0,0,max(1,canvas.winfo_width()),height),
    )
    return canvas


def moved(router,canvas,origin,*,num=None,delta=0,keysym=""):
    canvas.yview_moveto(.4)
    before=canvas.yview()
    callback=router._key if keysym else router._wheel
    result=callback(event(origin,num=num,delta=delta,keysym=keysym))
    return result,before,canvas.yview()


def main():
    measurements=[]
    with tempfile.TemporaryDirectory() as temporary,isolated_smoke_environment(temporary):
        import customtkinter as ctk

        from app.gui.customtkinter_compat import ScopedScrollableFrame
        from app.gui.main_window import SusADBWindow

        app=SusADBWindow()
        app._deferred_started=True
        app.geometry("1200x760+0+0")
        app.navigate_workspace("Pentest")
        pentest=app.pentest_workspace
        pentest.open_plugins()
        panel=pentest.plugin_panel
        panel.tabs.set("Official Catalog")
        pump(app)

        originals=tuple(app.plugin_manager.official())
        assert len(originals)==7

        def catalog(size):
            values=[]
            for index in range(size):
                item=originals[index%len(originals)]
                manifest=replace(
                    item.manifest,
                    plugin_id=f"fixture.scroll-{index:03d}",
                    name=f"Scroll Fixture {index+1}",
                )
                values.append(replace(
                    item,
                    manifest=manifest,
                    package_digest=f"{index+1:064x}",
                    installed=False,
                ))
            return tuple(values)

        manager_official=app.plugin_manager.official
        for size in (1,6,12,30,75):
            values=catalog(size)
            app.plugin_manager.official=lambda values=values:values
            panel.render_official()
            pump(app)
            assert len(panel.official_cards.winfo_children())==size
            for width,height in ((900,650),(980,650),(1180,780),(1400,860),(1600,900)):
                app.geometry(f"{width}x{height}+0+0")
                pump(app)
                canvas=panel.official_cards._parent_canvas
                content=max(
                    1,
                    canvas.bbox("all")[3] if canvas.bbox("all") else 1,
                )
                measurements.append((
                    size,f"{width}x{height}",canvas.winfo_height(),content,
                    canvas.yview(),panel.official_cards._scrollbar.winfo_width(),
                    app.status_bar.winfo_rooty(),
                ))

        values=catalog(30)
        app.plugin_manager.official=lambda:values
        panel.render_official()
        pump(app)
        frame=panel.official_cards
        canvas=force_extent(frame)
        router=frame._scroll_router
        cards=frame.winfo_children()
        first=cards[0]
        title,description,button=first.winfo_children()

        # X11, Windows/macOS-style, and smooth touchpad directions.
        result,before,after=moved(router,canvas,title,num=4)
        assert result=="break" and after[0]<before[0]
        result,before,after=moved(router,canvas,title,num=5)
        assert result=="break" and after[0]>before[0]
        result,before,after=moved(router,canvas,title,delta=120)
        assert result=="break" and after[0]<before[0]
        result,before,after=moved(router,canvas,title,delta=-120)
        assert result=="break" and after[0]>before[0]
        result,before,after=moved(router,canvas,title,delta=1)
        assert result=="break" and after[0]<before[0]
        result,before,after=moved(router,canvas,title,delta=-1)
        assert result=="break" and after[0]>before[0]
        before=canvas.yview()
        assert router._wheel(event(title,delta=0)) is None
        assert canvas.yview()==before

        # Every catalog hit target routes to the same canvas.
        records_before=tuple(app.plugin_manager.records)
        for origin in (
            frame,canvas,first,title,description,button,frame._scrollbar,
        ):
            result,before,after=moved(router,canvas,origin,num=5)
            assert result=="break" and after[0]>before[0],origin
        assert tuple(app.plugin_manager.records)==records_before

        # Keyboard works without focusing the scrollbar.
        for keysym,direction in (
            ("Prior",-1),("Next",1),("Up",-1),("Down",1),
        ):
            result,before,after=moved(
                router,canvas,title,keysym=keysym,
            )
            assert result=="break"
            assert (after[0]-before[0])*direction>0
        canvas.yview_moveto(.5)
        assert router._key(event(title,keysym="Home"))=="break"
        assert canvas.yview()[0]<.001
        assert router._key(event(title,keysym="End"))=="break"
        assert canvas.yview()[1]>.999

        # Editing and choice controls retain native arrows/dropdown scrolling.
        entry=ctk.CTkEntry(first)
        entry.grid(row=2,column=0)
        combo=ctk.CTkComboBox(first,values=("One","Two"))
        combo.grid(row=3,column=0)
        pump(app)
        canvas.yview_moveto(.4)
        before=canvas.yview()
        assert router._key(event(entry._entry,keysym="Down")) is None
        assert router._wheel(event(combo._entry,num=5)) is None
        assert canvas.yview()==before
        entry.destroy()
        combo.destroy()

        # Focus traversal brings an off-screen card action into view.
        canvas=force_extent(frame)
        canvas.yview_moveto(0)
        last_button=cards[-1].winfo_children()[-1]
        router.ensure_visible(last_button)
        assert canvas.yview()[0]>0

        # Hidden tabs and unrelated text surfaces cannot move each other.
        panel.tabs.set("Installed")
        pump(app)
        hidden_before=canvas.yview()
        installed_before=panel.installed._textbox.yview()
        assert router._wheel(event(title,num=5)) is None
        assert canvas.yview()==hidden_before
        assert panel.installed._textbox.yview()==installed_before
        panel.tabs.set("Official Catalog")
        pump(app)
        before=panel.installed._textbox.yview()
        router._wheel(event(title,num=5))
        assert panel.installed._textbox.yview()==before

        # Refresh preserves a valid absolute catalog offset and no handlers duplicate.
        canvas=frame._parent_canvas
        canvas.yview_moveto(.4)
        pump(app)
        offset=max(0.0,float(canvas.canvasy(0)))
        count=router.count
        panel.render_official()
        pump(app)
        assert abs(float(canvas.canvasy(0))-offset)<=3
        assert router.count==count

        # A second window is isolated; outside/native path input is ignored.
        second=ctk.CTkToplevel(app)
        second.geometry("900x650+0+0")
        other=ScopedScrollableFrame(second,fg_color=app.theme["panel"])
        other.pack(fill="both",expand=True)
        for index in range(40):
            ctk.CTkLabel(
                other,text=f"Other {index}",text_color=app.theme["text"],
            ).grid(row=index,column=0,pady=8)
        pump(second)
        other_canvas=force_extent(other)
        other_before=other_canvas.yview()
        catalog_before=canvas.yview()
        assert router._wheel(event(other,num=5)) is None
        assert other_canvas.yview()==other_before
        assert canvas.yview()==catalog_before
        assert router._wheel(event(".native.file.dialog",num=5)) is None
        assert canvas.yview()==catalog_before

        # Nested text consumes while it can move, then the outer surface moves.
        nested_host=ScopedScrollableFrame(second,fg_color=app.theme["panel"])
        nested_host.pack(fill="both",expand=True)
        nested=ctk.CTkTextbox(nested_host,height=90)
        nested.grid(row=0,column=0)
        nested.insert("1.0","\n".join(f"line {index}" for index in range(80)))
        for index in range(30):
            ctk.CTkLabel(nested_host,text=f"Outer {index}").grid(row=index+1,column=0)
        nested_host.register_nested_scroll(nested)
        pump(second)
        outer_canvas=force_extent(nested_host)
        nested._textbox.yview_moveto(0)
        outer_canvas.yview_moveto(0)
        nested_before=nested._textbox.yview()
        outer_before=outer_canvas.yview()
        assert nested_host._scroll_router._nested_wheel(
            event(nested._textbox,num=5)
        )=="break"
        assert nested._textbox.yview()!=nested_before
        assert outer_canvas.yview()==outer_before
        nested._textbox.yview_moveto(1)
        assert nested_host._scroll_router._nested_wheel(
            event(nested._textbox,num=5)
        ) is None
        assert nested_host._scroll_router._wheel(
            event(nested._textbox,num=5)
        )=="break"
        assert outer_canvas.yview()!=outer_before

        # Read-only native text keeps wheel/page behavior and focus.
        panel.installed.configure(state="normal")
        panel.installed.delete("1.0","end")
        panel.installed.insert("1.0","\n".join(f"plugin {index}" for index in range(200)))
        panel.installed.configure(state="disabled")
        panel.tabs.set("Installed")
        pump(app)
        panel.installed._textbox.focus_set()
        panel.installed._textbox.yview_moveto(.5)
        text_before=panel.installed._textbox.yview()
        panel.installed._textbox.event_generate("<Next>")
        pump(app)
        assert panel.installed._textbox.yview()!=text_before

        # Representative detached/lazy standard surfaces use the same router.
        about=app.open_about()
        help_window=app.open_context_help("console")
        learning=app.open_learning_center()
        recipes=app.open_workflow_recipes()
        pentest.workspace.set("Dashboard")
        pentest._section_selected()
        pump(app)
        representatives=(
            about.content,
            help_window.topic_list,
            learning.addon_list,
            recipes.library,
            pentest.dashboard_scroll,
        )
        for surface in representatives:
            surface_canvas=force_extent(surface)
            origin=surface.winfo_children()[0] if surface.winfo_children() else surface_canvas
            result,before,after=moved(
                surface._scroll_router,surface_canvas,origin,num=5,
            )
            assert result=="break" and after[0]>before[0],surface

        # Destroy/replacement/close removes only owned bindings.
        temporary_frame=ScopedScrollableFrame(second)
        temporary_frame.pack()
        temporary_router=temporary_frame._scroll_router
        assert temporary_router.count>0
        temporary_frame.destroy()
        assert temporary_router.count==0
        nested_router=nested_host._scroll_router
        other_router=other._scroll_router
        second.destroy()
        assert nested_router.count==0 and other_router.count==0
        assert nested_router._wheel(event(nested._textbox,num=5)) is None

        routers=[
            widget._scroll_router
            for widget in (
                panel.official_cards,about.content,help_window.topic_list,
                learning.addon_list,recipes.library,pentest.dashboard_scroll,
            )
        ]
        app.plugin_manager.official=manager_official
        app.shutdown()
        assert all(value.count==0 for value in routers)

    print(
        "universal-scroll-smoke=PASS "
        "catalog=1,6,12,30,75 "
        "main=900x650,980x650,1180x780,1400x860,1600x900 "
        "wheel=button4,button5,positive,negative,touchpad "
        "keyboard=page,home,end,up,down "
        "focus-hidden-isolation-refresh-native-dialog-nested-readonly-cleanup=PASS "
        f"measurements={measurements}"
    )
    return 0


if __name__=="__main__":
    raise SystemExit(main())
