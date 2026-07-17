from .adb_module import ADBModule
from .frida_module import FridaModule
from .objection_module import ObjectionModule


class Modules:

    def __init__(self, terminal):

        self.adb = ADBModule(terminal)
        self.frida = FridaModule()
        self.objection = ObjectionModule()