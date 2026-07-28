import tkinter as tk
import unittest
from pathlib import Path
from app.gui.customtkinter_compat import (
    ScopedEventBindings,
    widget_within,
)


def widget(master=None):
    value=object.__new__(tk.Misc);value.master=master
    value.winfo_exists=lambda:1
    return value


class FakeBindingOwner:
    def __init__(self):self.exists=True;self.bound=[];self.unbound=[]
    def winfo_exists(self):return self.exists
    def bind(self,sequence,callback,add=None):
        binding=f"{sequence}:{len(self.bound)}";self.bound.append((sequence,callback,add,binding));return binding
    def unbind(self,sequence,binding):self.unbound.append((sequence,binding))


class PluginActionScrollingTests(unittest.TestCase):
    def test_widget_routing_is_owned_and_rejects_native_paths(self):
        container=widget();child=widget(container);grandchild=widget(child)
        self.assertTrue(widget_within(grandchild,container))
        self.assertFalse(widget_within(widget(),container))
        self.assertFalse(widget_within(".native.file.dialog",container))

    def test_scoped_bindings_remove_exact_additive_ids(self):
        owner=FakeBindingOwner();bindings=ScopedEventBindings()
        for sequence in ("<MouseWheel>","<Button-4>","<Button-5>"):
            bindings.bind(owner,sequence,lambda _event:None)
        self.assertEqual(bindings.count,3)
        self.assertTrue(all(value[2]=="+" for value in owner.bound))
        bindings.close()
        self.assertEqual(bindings.count,0)
        self.assertEqual(
            owner.unbound,
            [(value[0],value[3]) for value in owner.bound],
        )

    def test_every_application_scroll_frame_uses_the_scoped_subclass(self):
        root=Path(__file__).parents[1]
        direct=[]
        for folder in ("app/gui","app/widgets"):
            for path in (root/folder).glob("*.py"):
                if path.name=="customtkinter_compat.py":continue
                if "ctk.CTkScrollableFrame(" in path.read_text(encoding="utf-8"):
                    direct.append(path.relative_to(root).as_posix())
        self.assertEqual(direct,[])

    def test_canonical_router_owns_required_input_contract(self):
        source=(Path(__file__).parents[1]/"app/gui/customtkinter_compat.py").read_text(
            encoding="utf-8"
        )
        for sequence in (
            "<MouseWheel>","<Button-4>","<Button-5>","<Prior>","<Next>",
            "<Home>","<End>","<Up>","<Down>",
        ):
            self.assertIn(sequence,source)
        self.assertIn("binding_id=owner.bind(sequence,callback,add=\"+\")",source)
        self.assertIn("owner.unbind(sequence,binding_id)",source)
        self.assertIn("parent.__class__.__name__==\"CTkTabview\"",source)

if __name__=="__main__":unittest.main()
