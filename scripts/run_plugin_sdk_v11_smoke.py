"""Local-only Plugin SDK v1.1 renderer and scoped-input smoke."""
from types import SimpleNamespace
import threading
import time
import tkinter as tk

import customtkinter as ctk

from app.core.worker import BackgroundWorker
from app.gui.customtkinter_compat import wheel_scroll_units
from app.gui.plugin_manager_panel import PluginSpecFrame
from app.gui.theme import get_theme
from app.plugins.plugin_interactive import (
    PluginActionResult,PluginActionSpec,PluginFieldSpec,PluginFieldType,
    PluginFormSpec,PluginOptionSpec,PluginProgressUpdate,
)
from app.plugins.plugin_ui import PluginPanelSpec,PluginView


class Allowed:
    ok=True;error=""
class Context:
    selected_device={};selected_target={};approved_capabilities=();generation=1


def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


def pump(root,ui_queue=(),limit=8):
    for _ in range(limit):
        while ui_queue:
            callback,args=ui_queue.pop(0);callback(*args)
        root.update_idletasks();root.update()


def assert_no_blue(widget):
    blue={"blue","#0000ff","#1f6aa5","#144870"}
    for child in (widget,*descendants(widget)):
        for key in ("fg_color","hover_color","button_color","border_color"):
            try:value=child.cget(key)
            except (AttributeError,ValueError,tk.TclError):continue
            values=value if isinstance(value,(tuple,list)) else (value,)
            assert not any(str(item).casefold() in blue for item in values),(child,key,value)


def main():
    root=ctk.CTk();root.withdraw();theme=get_theme();errors=[]
    root.report_callback_exception=lambda exc,value,tb:errors.append((exc,value))
    calls=[];workers=[];ui_queue=[];measurements=[]
    def callback(request):
        calls.append(request)
        request.progress(PluginProgressUpdate("Synthetic progress",0.5))
        return PluginActionResult(True,"Synthetic action complete")
    def start(target,done):
        worker=BackgroundWorker(target,callback=done);workers.append(worker);worker.start();return worker
    fields=(
        PluginFieldSpec("name","Required name",required=True),
        PluginFieldSpec("secret","Sensitive value",PluginFieldType.PASSWORD,sensitive=True),
        PluginFieldSpec("enabled","Enabled",PluginFieldType.CHECKBOX,description="Synthetic checkbox"),
        PluginFieldSpec("choice","Choice",PluginFieldType.CHOICE,default="one",options=(PluginOptionSpec("one","One"),PluginOptionSpec("two","Two"))),
        PluginFieldSpec("count","Bounded integer",PluginFieldType.INTEGER,default=2,minimum=1,maximum=3),
        PluginFieldSpec("readonly","Read-only value",PluginFieldType.READ_ONLY,default="Host value"),
        PluginFieldSpec("notes","Multiline notes",PluginFieldType.MULTILINE,default="".join(f"Line {value}\n" for value in range(40)),max_length=4000),
        *(PluginFieldSpec(f"extra-{value}",f"Additional field {value}",default=f"value-{value}") for value in range(8)),
    )
    form=PluginFormSpec("demo",fields,title="Overflowing form",description="Every host-rendered field remains reachable.")
    primary=PluginActionSpec("inspect","Run explicit no-op",callback,description="Host-owned synthetic action with a deliberately long description for wrapping and wheel routing.",form=form,primary=True,supports_cancellation=True)
    secondary=PluginActionSpec("secondary","Secondary action",callback,description="Dark and subordinate.")
    unavailable=PluginActionSpec("unavailable","Unavailable action",callback,enabled=False,unavailable_reason="Synthetic availability explanation.")
    actions=(primary,secondary,unavailable)
    def panel(status="Ready"):
        return PluginPanelSpec("Plugin SDK v1.1",(PluginView("Overview","Synthetic immutable content. "*30),),{"API":"1.1","Status":status},actions)

    for width,height in ((900,650),(980,650),(1180,780),(1400,860)):
        window=ctk.CTkToplevel(root);window.geometry(f"{width}x{height}+0+0");window.grid_columnconfigure(0,weight=1);window.grid_rowconfigure(0,weight=1)
        global_before={sequence:root.bind_all(sequence) for sequence in ("<MouseWheel>","<KeyPress-Shift_L>","<KeyPress-Shift_R>","<KeyRelease-Shift_L>","<KeyRelease-Shift_R>")}
        frame=PluginSpecFrame(window,theme,panel(),plugin_id="synthetic",context_provider=Context,authorize=lambda _caps:Allowed(),start_background=start,ui_dispatch=lambda fn,*args:ui_queue.append((fn,args)));frame.grid(sticky="nsew");pump(root,ui_queue)
        assert global_before=={sequence:root.bind_all(sequence) for sequence in global_before}
        canvas=frame.action_host._parent_canvas;canvas.yview_moveto(0);pump(root,ui_queue)
        region=tuple(float(value) for value in str(canvas.cget("scrollregion")).split())
        content_height=region[3]-region[1];viewport_height=canvas.winfo_height()
        assert content_height>viewport_height and frame.action_host._scrollbar.winfo_ismapped()
        assert canvas.xview()==(0.0,1.0)
        assert frame.field_widgets[("inspect","secret")].cget("show")=="•"
        router=frame.action_host._scroll_router
        assert router.bindings.count>0 and router.nested_bindings.count==3

        targets=(
            frame.action_cards["inspect"],frame.action_titles["inspect"],
            frame.action_descriptions["inspect"],frame.field_labels[("inspect","name")],
            frame.field_widgets[("inspect","name")],frame.field_widgets[("inspect","secret")],
            frame.field_widgets[("inspect","enabled")],
            frame.field_widgets[("inspect","count")],frame.field_widgets[("inspect","readonly")],
            frame.action_buttons["inspect"],frame.action_status,
        )
        for target in targets:
            canvas.yview_moveto(0);before=canvas.yview()
            result=frame._action_wheel(SimpleNamespace(widget=target,num=5,delta=0))
            assert result=="break",(target.__class__.__name__,result)
            assert canvas.yview()!=before,target
        choice=frame.field_widgets[("inspect","choice")]
        canvas.yview_moveto(0);choice_before=canvas.yview()
        assert frame._action_wheel(
            SimpleNamespace(widget=choice,num=5,delta=0)
        ) is None
        assert canvas.yview()==choice_before
        assert frame._action_wheel(SimpleNamespace(widget=".native.file.dialog",num=5,delta=-120)) is None

        canvas.yview_moveto(.5);middle=canvas.yview()[0]
        assert frame._action_wheel(SimpleNamespace(widget=frame.action_titles["inspect"],num=4,delta=0))=="break";assert canvas.yview()[0]<middle
        canvas.yview_moveto(.5);assert frame._action_wheel(SimpleNamespace(widget=frame.action_titles["inspect"],num=5,delta=0))=="break";assert canvas.yview()[0]>middle
        canvas.yview_moveto(.5);assert frame._action_wheel(SimpleNamespace(widget=frame.action_titles["inspect"],num=None,delta=120))=="break";assert canvas.yview()[0]<middle
        canvas.yview_moveto(.5);assert frame._action_wheel(SimpleNamespace(widget=frame.action_titles["inspect"],num=None,delta=-120))=="break";assert canvas.yview()[0]>middle
        canvas.yview_moveto(.5);assert frame._action_wheel(SimpleNamespace(widget=frame.action_titles["inspect"],num=None,delta=-1))=="break";assert canvas.yview()[0]>middle

        multiline=frame.field_widgets[("inspect","notes")];inner=multiline._textbox
        inner.yview_moveto(0);canvas.yview_moveto(0);inner_before=inner.yview();outer_before=canvas.yview()
        assert frame._action_wheel(SimpleNamespace(widget=inner,num=5,delta=0))=="break"
        assert inner.yview()!=inner_before and canvas.yview()==outer_before
        inner.yview_moveto(1);canvas.yview_moveto(0);inner_before=inner.yview();outer_before=canvas.yview()
        assert frame._action_wheel(SimpleNamespace(widget=inner,num=5,delta=0))=="break"
        assert inner.yview()==inner_before and canvas.yview()!=outer_before
        inner.yview_moveto(1);canvas.yview_moveto(0);outer_before=canvas.yview()
        inner.event_generate("<Button-5>");pump(root,ui_queue)
        assert canvas.yview()!=outer_before

        canvas.yview_moveto(0);pump(root,ui_queue);actual_before=canvas.yview()
        frame.field_widgets[("inspect","name")]._entry.event_generate("<Button-5>")
        pump(root,ui_queue);assert canvas.yview()!=actual_before

        canvas.yview_moveto(.45);offset_before=frame._action_scroll_offset();bindings_before=(router.bindings.count,router.nested_bindings.count)
        frame.update_spec(panel("Refreshed"));pump(root,ui_queue)
        assert bindings_before==(router.bindings.count,router.nested_bindings.count)
        assert abs(frame._action_scroll_offset()-offset_before)<=3,(offset_before,frame._action_scroll_offset())

        canvas.yview_moveto(0);frame._action_key(SimpleNamespace(widget=canvas,keysym="Next"));assert canvas.yview()[0]>0
        frame._action_key(SimpleNamespace(widget=canvas,keysym="End"));assert canvas.yview()[1]>.99
        frame._action_key(SimpleNamespace(widget=canvas,keysym="Home"));assert canvas.yview()[0]<.01
        entry=frame.field_widgets[("inspect","name")]
        before=canvas.yview();assert frame._action_key(SimpleNamespace(widget=entry,keysym="Down")) is None;assert canvas.yview()==before

        frame.field_vars[("inspect","name")][1].set("")
        assert not frame.invoke_action(primary) and "required" in frame.action_status.cget("text").casefold()
        frame.field_vars[("inspect","name")][1].set("synthetic")
        assert frame.invoke_action(primary);assert not frame.invoke_action(primary)
        deadline=time.monotonic()+2
        while frame.active_action and time.monotonic()<deadline:pump(root,ui_queue,1);time.sleep(.01)
        assert calls and "complete" in frame.action_status.cget("text").casefold()

        if width==900:
            second_window=ctk.CTkToplevel(root);second_window.geometry("900x650+20+20");second=PluginSpecFrame(second_window,theme,panel(),plugin_id="second",context_provider=Context,authorize=lambda _caps:Allowed(),start_background=start,ui_dispatch=lambda fn,*args:ui_queue.append((fn,args)));second.grid();pump(root,ui_queue)
            second_canvas=second.action_host._parent_canvas;second_canvas.yview_moveto(0);first_before=canvas.yview();second_before=second_canvas.yview()
            assert frame._action_wheel(SimpleNamespace(widget=second.action_titles["inspect"],num=5,delta=0)) is None
            assert canvas.yview()==first_before and second_canvas.yview()==second_before
            second.cleanup();second_window.destroy();pump(root,ui_queue)

        canvas.yview_moveto(1);pump(root,ui_queue)
        last=frame.action_cards["unavailable"];viewport_bottom=canvas.winfo_rooty()+canvas.winfo_height();last_bottom=last.winfo_rooty()+last.winfo_height()
        assert last_bottom<=viewport_bottom+2,(last_bottom,viewport_bottom)
        initial=(0.0,viewport_height/max(content_height,1));final=canvas.yview()
        measurements.append((f"{width}x{height}",viewport_height,round(content_height),initial,final,frame.action_host._scrollbar.winfo_width(),last_bottom,viewport_bottom))
        assert_no_blue(frame)

        legacy=PluginSpecFrame(window,theme,PluginPanelSpec("Legacy",(PluginView("Overview","API 1.0"),)));legacy.grid();pump(root,ui_queue)
        assert not legacy.action_host._parent_frame.winfo_ismapped()
        assert legacy._action_wheel(SimpleNamespace(widget=legacy.action_status,num=5,delta=0)) is None
        legacy.cleanup();legacy.destroy()

        secret=frame.field_vars[("inspect","secret")][1];secret.set("runtime-only")
        frame.cleanup();assert secret.get()=="";assert router.count==0 and not frame._callbacks._pending
        window.destroy();pump(root,ui_queue)
    for worker in workers:worker.join(1);assert not worker.is_alive()
    assert not errors,errors
    root.destroy()
    print(
        "plugin-sdk-v1.1-gui-smoke=PASS "
        "sizes=900x650,980x650,1180x780,1400x860 "
        f"measurements={measurements} "
        f"wheel-units=button4:{wheel_scroll_units(SimpleNamespace(num=4),36)},"
        f"button5:{wheel_scroll_units(SimpleNamespace(num=5),36)},"
        f"mouse-positive:{wheel_scroll_units(SimpleNamespace(num=None,delta=120),36)},"
        f"mouse-negative:{wheel_scroll_units(SimpleNamespace(num=None,delta=-120),36)},"
        f"touchpad:{wheel_scroll_units(SimpleNamespace(num=None,delta=-1),36)} "
        "nested-scroll-isolation-keyboard-dialog-rerender-cleanup=PASS"
    )


if __name__=="__main__":main()
