"""Isolated actionable official-addon update acceptance checks."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

def main():
    import customtkinter as ctk

    from app.gui.addons_center import AddonsCenter,UpdateReviewDialog
    from app.gui.theme import get_theme
    from app.plugins.addon_presenter import card_actions,card_spec,lifecycle_for
    from app.plugins.contribution_registry import Contribution,ContributionRegistry
    from app.plugins.plugin_loader import LoaderState,LoaderStatus
    from app.plugins.plugin_manager import PluginManager
    from app.plugins.plugin_package import PluginPackage
    from app.plugins.plugin_store import PluginStore
    from app.plugins.plugin_trust import PluginTrustStore

    target_id="zz.official-update"
    errors=[]
    measurements=[]
    observed_states=set()

    def package(path,plugin_id,version,marker,capabilities=()):
        path.mkdir(parents=True,exist_ok=True)
        manifest={
            "plugin_id":plugin_id,"name":"ZZ Update Demo" if plugin_id==target_id else f"Fixture {plugin_id}",
            "version":version,"description":f"Local-only {marker} package used for update acceptance.",
            "author":"SUS Companion","entry_point":"plugin.py:Plugin",
            "requested_capabilities":list(capabilities),
            "contributed_components":[{
                "contribution_id":f"{plugin_id}.panel","contribution_type":"pentest-panel",
                "title":f"{plugin_id} Panel","factory":"panel_spec",
                "metadata":{"ui_mode":"window"},
            }],
            "addon_ui":{"ui_mode":"window"},"enabled":False,
        }
        (path/"manifest.json").write_text(json.dumps(manifest),encoding="utf-8")
        (path/"plugin.py").write_text(
            f"MARKER={marker!r}\nclass Plugin:\n"
            " def activate(self,api): return ()\n"
            " def deactivate(self): pass\n",encoding="utf-8",
        )
        return path

    class WindowHost:
        def __init__(self):self.opened=False;self.errors={}
        def is_open(self,_contribution_id):return self.opened
        def open(self,_contribution_id):return None

    def pump(root):
        root.update_idletasks();root.update();root.update_idletasks()

    def descendants(widget):
        for child in widget.winfo_children():
            yield child
            yield from descendants(child)

    def button(dialog,label):
        return next(
            widget for widget in descendants(dialog)
            if isinstance(widget,ctk.CTkButton) and widget.cget("text")==label
        )

    def no_blue(widget):
        for current in (widget,*descendants(widget)):
            keys=getattr(current,"keys",lambda:())()
            for key in ("fg_color","hover_color","border_color","button_color","button_hover_color"):
                if key in keys:
                    value=str(current.cget(key)).casefold()
                    assert "blue" not in value and "#3b8ed0" not in value and "#1f6aa5" not in value

    with tempfile.TemporaryDirectory() as directory:
        root_path=Path(directory)
        os.environ["XDG_CONFIG_HOME"]=directory
        official=root_path/"official"
        old=package(root_path/"old",target_id,"1.0.0","installed",("read-selected-device",))
        package(official/"target",target_id,"1.1.0","candidate",("read-selected-device","read-selected-target"))
        for index in range(11):
            package(official/f"fixture-{index:02d}",f"fixture.addon-{index:02d}","1.0.0",f"available-{index}")
        store=PluginStore(root_path/"store")
        assert store.install(old).ok
        trust=PluginTrustStore(store.root/"state"/"trust.json")
        manager=PluginManager(store,trust,ContributionRegistry(),official_root=official)
        host=WindowHost()
        item=manager.catalog.get(target_id,manager.records)
        observed_states.add("permissions required")
        assert lifecycle_for(manager,target_id)=="Permissions Required"
        old_digest=manager.records[target_id][1].package_digest
        trust.approve(target_id,old_digest,("read-selected-device",))
        manager.refresh()
        observed_states.add("installed")
        assert lifecycle_for(manager,target_id)=="Installed"
        assert manager.enable(target_id).ok
        observed_states.add("enabled")
        assert lifecycle_for(manager,target_id)=="Enabled"

        root=ctk.CTk()
        root.withdraw()
        root.report_callback_exception=lambda kind,value,trace:errors.append((kind.__name__,str(value)))
        center=AddonsCenter(root,get_theme(),manager,host)
        center.deiconify()
        pump(root)
        assert len(center.cards)==12
        observed_states.update(("available","update available but current version usable"))
        card=center.cards[target_id]
        stable_card=card
        assert card.spec.version=="1.0.0"
        assert card.spec.update_available
        assert "Load" in card.actions and "Review Update" in card.actions
        assert "Install Update" not in card.actions

        for width,height in ((900,650),(980,650),(1180,780),(1400,860)):
            center.geometry(f"{width}x{height}+0+0")
            pump(root)
            center.card_area._parent_canvas.yview_moveto(1)
            pump(root)
            viewport=(center.card_area._parent_canvas.winfo_rooty(),center.card_area._parent_canvas.winfo_rooty()+center.card_area._parent_canvas.winfo_height())
            footer_top=center.footer.winfo_rooty()
            bounds=(card.winfo_rooty(),card.winfo_rooty()+card.winfo_height())
            assert viewport[1]<=footer_top
            assert bounds[0]>=viewport[0] and bounds[1]<=viewport[1] and bounds[1]<footer_top,(width,height,viewport,bounds,footer_top)
            assert all(value.winfo_rootx()+value.winfo_width()<=card.winfo_rootx()+card.winfo_width() for value in card.buttons.values() if value.winfo_ismapped())
            measurements.append((f"{width}x{height}",viewport,bounds,footer_top))

        canvas=center.card_area._parent_canvas
        canvas.yview_moveto(1)
        pump(root)
        position=center.card_area.scroll_offset()
        state_before=store.state(target_id).copy()
        card.buttons["Review Update"].invoke()
        pump(root)
        dialog=center.review_dialog
        assert isinstance(dialog,UpdateReviewDialog)
        text=next(widget for widget in descendants(dialog) if isinstance(widget,ctk.CTkTextbox)).get("1.0","end")
        for value in ("Installed version: 1.0.0","Candidate version: 1.1.0","Requested capabilities","Contributions","Presentation metadata changed","Executable/plugin files changed","Prior trust and capability approval"):
            assert value in text
        assert button(dialog,"Close") and button(dialog,"Mark Reviewed")
        button(dialog,"Close").invoke()
        pump(root)
        assert store.state(target_id)==state_before
        assert "Install Update" not in card.actions

        card.buttons["Review Update"].invoke()
        pump(root)
        review_button=card.buttons["Review Update"]
        button(center.review_dialog,"Mark Reviewed").invoke()
        pump(root)
        observed_states.add("update reviewed")
        assert center.cards[target_id] is stable_card
        assert center.cards[target_id].buttons["Review Update"] is review_button
        assert abs(center.card_area.scroll_offset()-position)<=3
        assert "Install Update" in card.actions
        assert manager.official_update_reviewed(target_id,item.package_digest)

        manager.loader.statuses[target_id]=LoaderStatus(target_id,LoaderState.ACTIVE)
        manager.loader.instances[target_id]=object()
        manager.registry.register(target_id,(Contribution(f"{target_id}.panel","pentest-panel","Update Demo",target_id),))
        host.opened=True
        center.refresh();pump(root)
        observed_states.update(("loaded","open","unload required"))
        assert card.spec.lifecycle_status=="Window Open"
        assert "Unload" in card.actions and "Install Update" not in card.actions
        assert "unload addon before installing" in card.spec.update_status
        assert not manager.install_official_update(target_id,item.package_digest).ok
        assert manager.official_update_reviewed(target_id,item.package_digest)
        manager.unload(target_id);host.opened=False
        center.refresh();pump(root)
        observed_states.add("update ready")
        assert "Install Update" in card.actions

        old_path=manager.records[target_id][0]
        with mock.patch("app.plugins.plugin_store.shutil.copytree",side_effect=OSError("synthetic copy failure")):
            card.buttons["Install Update"].invoke()
        pump(root)
        observed_states.add("update failed with rollback")
        assert manager.records[target_id][2].version=="1.0.0"
        assert PluginPackage.inspect(old_path).package_digest==old_digest
        assert trust.verify(target_id,old_digest)
        assert "synthetic copy failure" in center.footer.cget("text")
        assert center.cards[target_id] is stable_card

        search_value="ZZ Update Demo"
        center.search.insert(0,search_value)
        center.refresh();pump(root)
        assert center.search.get()==search_value
        assert center.visible_plugin_ids==(target_id,)
        card.buttons["Install Update"].invoke()
        pump(root)
        observed_states.add("updated and trust required")
        assert center.search.get()==search_value
        assert center.cards[target_id] is stable_card
        assert center.cards[target_id].spec.version=="1.1.0"
        assert center.cards[target_id].spec.lifecycle_status=="Permissions Required"
        assert center.cards[target_id].spec.update_status==(
            "Update installed.\n"
            "Review and approve this package’s new exact digest before enabling it."
        )
        assert "Review Permissions" in center.cards[target_id].actions
        assert "Review Update" not in center.cards[target_id].actions
        assert "Install Update" not in center.cards[target_id].actions
        assert not center.cards[target_id].spec.update_available
        assert not manager.records[target_id][2].enabled
        assert not trust.verify(target_id,item.package_digest)
        assert not manager.registry.by_plugin(target_id)
        assert center.search.get()==search_value
        center.close();pump(root)
        center=AddonsCenter(root,get_theme(),manager,host)
        center.deiconify();pump(root)
        card=center.cards[target_id]
        stable_card=card
        assert card.spec.lifecycle_status=="Permissions Required"
        assert "Review Permissions" in card.actions
        center.search.insert(0,search_value)
        center.refresh();pump(root)
        activation_position=center.card_area.scroll_offset()
        card.buttons["Review Permissions"].invoke()
        pump(root)
        assert center.cards[target_id] is stable_card
        assert center.search.get()==search_value
        assert abs(center.card_area.scroll_offset()-activation_position)<=2
        assert card.actions==("Details","Enable")
        assert not manager.records[target_id][2].enabled
        card.buttons["Enable"].invoke();pump(root)
        assert center.cards[target_id] is stable_card
        assert card.actions==("Details","Load")
        def fake_load(_path,_inspection,enabled=False):
            status=LoaderStatus(target_id,LoaderState.ACTIVE)
            manager.loader.statuses[target_id]=status
            manager.registry.register(
                target_id,
                (Contribution(
                    f"{target_id}.panel","pentest-panel",
                    "Update Demo",target_id,
                ),),
            )
            return status
        with mock.patch.object(manager.loader,"load",side_effect=fake_load):
            card.buttons["Load"].invoke()
        pump(root)
        assert center.cards[target_id] is stable_card
        assert card.actions==("Details","Open","Unload")
        assert not host.opened
        card.buttons["Unload"].invoke();pump(root)
        assert card.actions==("Details","Load")
        assert not manager.registry.by_plugin(target_id)
        center.search.delete(0,"end")
        center.refresh();pump(root)
        assert len(center.visible_plugin_ids)==12
        assert target_id in center.visible_plugin_ids
        no_blue(center)
        assert not errors,errors

        center.close();pump(root)
        reopened=AddonsCenter(root,get_theme(),manager,host)
        reopened.deiconify();pump(root)
        assert reopened.cards[target_id].spec.version=="1.1.0"
        assert not reopened.cards[target_id].spec.update_available
        assert reopened.cards[target_id].actions==("Details","Load")
        reopened.close();pump(root)
        assert not errors,errors
        assert not manager.registry.list()
        assert not manager.loader.instances
        assert all(not child._callbacks._pending for child in root.winfo_children() if hasattr(child,"_callbacks"))
        root.destroy()

    required={"available","installed","permissions required","enabled","loaded","open","update available but current version usable","update reviewed","unload required","update ready","updated and trust required","update failed with rollback"}
    assert required<=observed_states,(required-observed_states)
    print(
        "addons-update-smoke=PASS "
        "sizes=900x650,980x650,1180x780,1400x860 "
        f"states={sorted(observed_states)} measurements={measurements} "
        "review-close-mark-install-unload-rollback-retry-no-restart-filter-scroll-focus-shutdown=PASS"
    )
    return 0

if __name__=="__main__":
    raise SystemExit(main())
