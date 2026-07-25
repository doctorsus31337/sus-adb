import importlib.util,sys
from pathlib import Path
ROOT=Path(__file__).parents[1]
def load(name,directory):
 path=ROOT/"plugins/official"/directory/"plugin.py";spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module
