"""
sus-adb
Android Device Companion   
"""

import argparse,json
from app.core.app_metadata import METADATA
from app.core.config_manager import ConfigManager
from app.core.environment_diagnostics import EnvironmentDiagnostics


def cli(argv=None):
    parser=argparse.ArgumentParser(prog="sus-adb");parser.add_argument("--version",action="store_true");parser.add_argument("--self-test",action="store_true");parser.add_argument("--diagnostics",action="store_true");args=parser.parse_args(argv)
    if args.version:print(METADATA.version);return 0
    if args.self_test:
        config=ConfigManager().load();print(json.dumps({"ok":config.ok,"version":METADATA.version,"configuration_schema":METADATA.configuration_schema_version,"plugin_api":METADATA.plugin_api_version},sort_keys=True));return 0 if config.ok else 1
    if args.diagnostics:
        for r in EnvironmentDiagnostics().run(ConfigManager().directory,"workspaces"):print(f"{'OK' if r.available else 'MISSING'}\t{r.name}\t{r.version or r.path}")
        return 0
    from app.gui.main_window import SusADBWindow
    app=SusADBWindow();app.mainloop();return 0
def main():return cli()


if __name__ == "__main__":
    main()
