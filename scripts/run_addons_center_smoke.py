"""Isolated Add-ons Center scrolling acceptance checks; executes no add-on."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    import customtkinter as ctk

    from app.gui.addons_center import AddonsCenter
    from app.gui.customtkinter_compat import focused_within
    from app.gui.theme import get_theme
    from app.plugins.contribution_registry import ContributionRegistry
    from app.plugins.plugin_manager import PluginManager
    from app.plugins.plugin_store import PluginStore
    from app.plugins.plugin_trust import PluginTrustStore

    theme=get_theme()
    errors=[]
    measurements=[]

    class WindowHost:
        errors={}
        def is_open(self,_contribution_id):return False
        def open(self,_contribution_id):return None

    class FakeTrust:
        def verify(self,_plugin_id,_digest):return False
        def approved(self,_plugin_id,_digest):return ()

    class FakeRegistry:
        def by_plugin(self,_plugin_id):return ()

    class FakeCatalog:
        def __init__(self,items):self.items=items
        def get(self,plugin_id,_records):
            return next(
                (
                    item for item in self.items
                    if item.manifest.plugin_id==plugin_id
                ),
                None,
            )

    class FakeManager:
        def __init__(self,count):
            self.records={}
            self.loader=SimpleNamespace(statuses={})
            self.trust=FakeTrust()
            self.registry=FakeRegistry()
            self.listeners=[]
            self.invocations=[]
            self.set_count(count)
        def set_count(self,count,long_text=False):
            items=[]
            for index in range(count):
                suffix=(
                    " — A deliberately long deterministic add-on name"
                    if long_text else ""
                )
                description=(
                    "A long local-only description used to verify responsive "
                    "wrapping, capability text changes, and bounded horizontal "
                    "layout without executing plugin code. "
                )*2 if long_text else f"Synthetic add-on {index+1}."
                manifest=SimpleNamespace(
                    plugin_id=f"fixture.addon-{index+1:02d}",
                    name=f"Fixture Add-on {index+1:02d}{suffix}",
                    version="1.0.0",
                    description=description,
                    requested_capabilities=(
                        ("read-selected-device",) if index%2 else ()
                    ),
                    contributed_components=(),
                    addon_ui={"ui_mode":"window"},
                    caution_text=(
                        "Local-only fixture. No plugin code is executed."
                    ),
                    enabled=False,
                )
                items.append(
                    SimpleNamespace(
                        manifest=manifest,installed=False,
                        package_digest=f"digest-{index+1:02d}",
                    )
                )
            self.items=items
            self.catalog=FakeCatalog(items)
        def official(self):return tuple(self.items)
        def subscribe(self,callback):
            self.listeners.append(callback)
            def unsubscribe():
                if callback in self.listeners:self.listeners.remove(callback)
            return unsubscribe
        def install_official(self,plugin_id,_digest):
            self.invocations.append(plugin_id)
            return SimpleNamespace(ok=True,error=None)

    def pump(root):
        root.update_idletasks()
        root.update()
        root.update_idletasks()

    def visible_bounds(widget):
        return (
            widget.winfo_rootx(),widget.winfo_rooty(),
            widget.winfo_rootx()+widget.winfo_width(),
            widget.winfo_rooty()+widget.winfo_height(),
        )

    def button_text_fits(button):
        text=str(button.cget("text"))
        font=getattr(button,"_font",None)
        if not text or font is None or not hasattr(font,"measure"):return True
        required=max(font.measure(line) for line in text.splitlines())+18
        return required<=button.winfo_width()

    def assert_no_blue(root):
        stack=[root]
        while stack:
            widget=stack.pop()
            stack.extend(widget.winfo_children())
            keys=getattr(widget,"keys",lambda:())()
            for key in (
                "fg_color","hover_color","border_color","button_color",
                "button_hover_color","highlightcolor",
            ):
                if key not in keys:continue
                try:value=str(widget.cget(key)).casefold()
                except (ValueError,RuntimeError):continue
                assert "blue" not in value
                assert "#3b8ed0" not in value and "#1f6aa5" not in value

    def reach_bottom(center,width,height,label):
        center.geometry(f"{width}x{height}+0+0")
        center.card_area._parent_canvas.yview_moveto(0)
        pump(center)
        canvas=center.card_area._parent_canvas
        scrollbar=center.card_area._scrollbar
        visible=tuple(center.visible_plugin_ids)
        assert visible
        first=center.cards[visible[0]]
        last=center.cards[visible[-1]]
        viewport=visible_bounds(canvas)
        footer=visible_bounds(center.footer)
        window=visible_bounds(center)
        assert viewport[0]>=window[0] and viewport[2]<=window[2]
        assert viewport[1]>=window[1] and viewport[3]<=footer[1]
        assert scrollbar.winfo_ismapped() and scrollbar.winfo_width()>=16
        assert scrollbar.cget("scrollbar_color")==theme["gold_dark"]
        assert scrollbar.cget("scrollbar_hover_color")==theme["red_hover"]
        assert canvas.yview()!=(0.0,1.0) or len(visible)==1
        assert visible_bounds(first)[1]>=viewport[1]
        assert canvas.xview()==(0.0,1.0)
        scrollbar._command("moveto",1.0)
        pump(center)
        last_bounds=visible_bounds(last)
        viewport=visible_bounds(canvas)
        assert last_bounds[1]>=viewport[1]
        assert last_bounds[3]<=viewport[3]
        assert last_bounds[3]<footer[1]
        assert viewport[3]-last_bounds[3]>=center.card_area.BOTTOM_PADDING-2
        assert all(
            button_text_fits(button)
            for plugin_id in visible
            for button in center.cards[plugin_id].buttons.values()
            if button.winfo_ismapped()
        )
        first_button=first.buttons[first.actions[0]]
        assert str(canvas.cget("takefocus"))=="1"
        assert str(canvas.tk.call("tk_focusNext",canvas._w))==first_button._w
        assert all(
            str(button.tk.call(button._w,"cget","-takefocus"))=="1"
            and (
                not hasattr(button,"_canvas")
                or str(button._canvas.cget("takefocus"))=="0"
            )
            for plugin_id in visible
            for button in center.cards[plugin_id].buttons.values()
        )
        start,end=scrollbar.get()
        ystart,yend=canvas.yview()
        assert abs(start-ystart)<0.01 and abs(end-yend)<0.01
        measurements.append(
            (
                label,f"{width}x{height}",len(visible),
                (viewport[1],viewport[3]),
                last_bounds[3],footer[1],scrollbar.winfo_width(),
            )
        )
        return viewport,last_bounds,footer

    with tempfile.TemporaryDirectory() as directory:
        os.environ["XDG_CONFIG_HOME"]=directory
        root=ctk.CTk()
        root.withdraw()
        root.report_callback_exception=lambda kind,value,trace:errors.append(
            (kind.__name__,str(value))
        )
        store=PluginStore(Path(directory)/"plugin-store")
        manager=PluginManager(
            store,
            PluginTrustStore(store.root/"state"/"trust.json"),
            ContributionRegistry(),
            official_root=ROOT/"plugins"/"official",
        )
        center=AddonsCenter(root,theme,manager,WindowHost())
        center.deiconify()
        pump(root)
        assert len(center.cards)==7
        assert len(set(center.cards))==7
        for width,height in ((900,650),(980,650),(1180,780),(1400,860)):
            reach_bottom(center,width,height,"official")

        canvas=center.card_area._parent_canvas
        first_id=center.visible_plugin_ids[0]
        first=center.cards[first_id]
        canvas.yview_moveto(0)
        pump(root)
        before=canvas.yview()
        result=center.card_area._mouse_wheel_all(
            SimpleNamespace(widget=first.name_label,delta=-120,num=None)
        )
        pump(root)
        assert result=="break" and canvas.yview()!=before
        install_button=first.buttons["Install"]
        records_before=tuple(manager.records)
        before=canvas.yview()
        center.card_area._mouse_wheel_all(
            SimpleNamespace(widget=install_button,delta=-1,num=None)
        )
        pump(root)
        assert canvas.yview()!=before
        assert tuple(manager.records)==records_before
        before=canvas.yview()
        center.card_area._mouse_wheel_all(
            SimpleNamespace(widget=first.state_label,delta=0,num=5)
        )
        pump(root)
        assert canvas.yview()!=before
        before=canvas.yview()
        assert center.card_area._mouse_wheel_all(
            SimpleNamespace(widget=".native.file.dialog",delta=-120,num=5)
        ) is None
        assert canvas.yview()==before

        canvas.yview_moveto(0)
        center.card_area._keyboard_scroll(
            SimpleNamespace(widget=canvas,keysym="Next")
        )
        assert canvas.yview()[0]>0
        center.card_area._keyboard_scroll(
            SimpleNamespace(widget=canvas,keysym="End")
        )
        pump(root)
        assert canvas.yview()[1]>0.99
        center.card_area._keyboard_scroll(
            SimpleNamespace(widget=canvas,keysym="Home")
        )
        assert canvas.yview()[0]<0.01

        canvas.yview_moveto(1)
        pump(root)
        center.search.insert(0,first.spec.name)
        center.refresh()
        pump(root)
        assert center.visible_plugin_ids==(first_id,)
        assert canvas.yview()[0]<0.01 and canvas.yview()[1]>0.99
        assert len(center.cards)==7
        center.search.delete(0,"end")
        center.refresh()
        pump(root)
        assert len(center.visible_plugin_ids)==7
        center.search.insert(0,"no matching add-on fixture")
        center.refresh()
        pump(root)
        assert not center.visible_plugin_ids
        assert canvas.yview()[0]<0.01 and canvas.yview()[1]>0.99
        center.search.delete(0,"end")
        center.refresh()
        pump(root)

        last_id=center.visible_plugin_ids[-1]
        stable_card=center.cards[last_id]
        canvas.yview_moveto(1)
        pump(root)
        position_before=center.card_area.scroll_offset()
        stable_card.buttons["Install"].invoke()
        pump(root)
        assert last_id in manager.records
        assert center.cards[last_id] is stable_card
        assert abs(center.card_area.scroll_offset()-position_before)<=2
        assert center.cards[last_id].actions[0]=="Details"
        assert "Permissions" in center.cards[last_id].actions
        reach_bottom(center,900,650,"official-installed")
        assert_no_blue(center)

        router=center.card_area._scroll_router
        assert router.count>0
        center.close()
        pump(root)
        assert router.count==0
        assert not center.card_area._callbacks._pending
        reopened=AddonsCenter(root,theme,manager,WindowHost())
        reopened.deiconify()
        pump(root)
        reopened_router=reopened.card_area._scroll_router
        assert reopened_router.count>0
        reopened.close()
        pump(root)
        assert reopened_router.count==0

        for count in (1,4,6,7,12,30):
            fake=FakeManager(count)
            synthetic=AddonsCenter(root,theme,fake,WindowHost())
            synthetic.deiconify()
            pump(root)
            reach_bottom(synthetic,900,650,f"synthetic-{count}")
            if count in {12,30}:
                fake.set_count(count,long_text=True)
                synthetic.refresh()
                pump(root)
                reach_bottom(
                    synthetic,1400,860,f"synthetic-{count}-long"
                )
            if count==4:
                removed_id=synthetic.visible_plugin_ids[-1]
                removed=synthetic.cards[removed_id]
                synthetic.focus_force()
                removed.buttons["Install"].focus_set()
                pump(root)
                fake.items=fake.items[:-1]
                fake.catalog.items=fake.items
                synthetic.refresh()
                pump(root)
                assert removed_id not in synthetic.cards
                assert focused_within(synthetic.search)
            synthetic.close()
            pump(root)

        for scale in (1.25,1.5):
            ctk.set_widget_scaling(scale)
            fake=FakeManager(12)
            scaled=AddonsCenter(root,theme,fake,WindowHost())
            scaled.deiconify()
            pump(root)
            reach_bottom(scaled,900,650,f"scaled-{int(scale*100)}")
            scaled.close()
            pump(root)
        ctk.set_widget_scaling(1.0)
        assert not errors,errors
        assert all(
            not child._callbacks._pending
            for child in root.winfo_children()
            if hasattr(child,"_callbacks")
        )
        root.destroy()

    print(
        "addons-center-smoke=PASS "
        "sizes=900x650,980x650,1180x780,1400x860 "
        "scales=125%,150% cards=1,4,6,7,12,30 "
        f"measurements={measurements} "
        "wheel=windows,touchpad,linux-x11 keyboard=up-down-page-home-end "
        "filter-lifecycle-focus-reopen-native-dialog-shutdown=PASS"
    )
    return 0


if __name__=="__main__":
    raise SystemExit(main())
