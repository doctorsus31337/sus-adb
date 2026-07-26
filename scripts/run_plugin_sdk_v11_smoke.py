"""Local-only Plugin SDK v1.1 renderer smoke; no plugin package is executed."""
import threading
import time
import customtkinter as ctk

from app.core.worker import BackgroundWorker
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


def main():
    root=ctk.CTk();root.withdraw();theme=get_theme()
    calls=[]
    def callback(request):
        calls.append(request)
        request.progress(PluginProgressUpdate("Synthetic progress",0.5))
        return PluginActionResult(True,"Synthetic action complete")
    form=PluginFormSpec("demo",(
        PluginFieldSpec("name","Required name",required=True),
        PluginFieldSpec("choice","Choice",PluginFieldType.CHOICE,default="one",options=(PluginOptionSpec("one","One"),PluginOptionSpec("two","Two"))),
        PluginFieldSpec("count","Bounded integer",PluginFieldType.INTEGER,default=2,minimum=1,maximum=3),
        PluginFieldSpec("secret","Sensitive value",PluginFieldType.PASSWORD,sensitive=True),
    ))
    action=PluginActionSpec("inspect","Run explicit no-op",callback,description="Host-owned synthetic action.",form=form,primary=True,supports_cancellation=True)
    panel=PluginPanelSpec("Plugin SDK v1.1",(
        PluginView("Overview","Synthetic immutable content. "*30),
    ),{"API":"1.1"},(action,))
    workers=[];ui_queue=[]
    def start(target,done):
        worker=BackgroundWorker(target,callback=done);workers.append(worker);worker.start();return worker
    for width,height in ((900,650),(980,650),(1180,780),(1400,860)):
        window=ctk.CTkToplevel(root);window.geometry(f"{width}x{height}+0+0");window.grid_columnconfigure(0,weight=1);window.grid_rowconfigure(0,weight=1)
        frame=PluginSpecFrame(window,theme,panel,plugin_id="synthetic",context_provider=Context,authorize=lambda _caps:Allowed(),start_background=start,ui_dispatch=lambda fn,*args:ui_queue.append((fn,args)));frame.grid(sticky="nsew");window.update_idletasks()
        assert frame.action_buttons["inspect"].cget("state")=="normal"
        frame.field_vars[("inspect","name")][1].set("synthetic")
        assert frame.invoke_action(action);assert not frame.invoke_action(action)
        deadline=time.monotonic()+2
        while frame.active_action and time.monotonic()<deadline:
            while ui_queue:
                fn,args=ui_queue.pop(0);fn(*args)
            root.update();time.sleep(.01)
        assert calls and "complete" in frame.action_status.cget("text").casefold()
        secret=frame.field_vars[("inspect","secret")][1];secret.set("runtime-only");frame.cleanup();assert secret.get()==""
        window.destroy()
    for worker in workers:worker.join(1);assert not worker.is_alive()
    root.destroy();assert threading.active_count()>=1
    print("plugin-sdk-v1.1-gui-smoke=ok sizes=900x650,980x650,1180x780,1400x860")


if __name__=="__main__":main()
