"""SUS Companion command-line and responsive GUI entry point."""

import time
PROCESS_STARTED=time.perf_counter()

import argparse,json
from app.core.app_metadata import METADATA
from app.core.config_manager import ConfigManager
from app.core.environment_diagnostics import EnvironmentDiagnostics


def cli(argv=None):
    parse_started=time.perf_counter();parser=argparse.ArgumentParser(prog=METADATA.preferred_executable,description=METADATA.descriptor);parser.add_argument("--version",action="store_true");parser.add_argument("--self-test",action="store_true");parser.add_argument("--diagnostics",action="store_true");args=parser.parse_args(argv);parse_finished=time.perf_counter()
    if args.version:print(METADATA.version);return 0
    if args.self_test:
        config=ConfigManager().load();print(json.dumps({"ok":config.ok,"version":METADATA.version,"configuration_schema":METADATA.configuration_schema_version,"plugin_api":METADATA.plugin_api_version},sort_keys=True));return 0 if config.ok else 1
    if args.diagnostics:
        print(f"BUILD\tProduct version\t{METADATA.version}")
        print(f"BUILD\tCommit\t{METADATA.short_revision}")
        print(f"BUILD\tBranch/ref\t{METADATA.repository_ref}")
        print(f"BUILD\tBuild timestamp\t{METADATA.build_timestamp}")
        print(f"BUILD\tBuild channel\t{METADATA.build_channel}")
        for r in EnvironmentDiagnostics().run(ConfigManager().directory,"workspaces"):print(f"{'OK' if r.available else 'MISSING'}\t{r.name}\t{r.version or r.path}")
        return 0
    gui_import_started=time.perf_counter();from app.gui.main_window import SusADBWindow
    gui_import_finished=time.perf_counter();app=SusADBWindow(startup_origin=PROCESS_STARTED,startup_intervals=(("command-line-parsing",parse_started,parse_finished),("gui-imports",gui_import_started,gui_import_finished)));app.mainloop();return 0
def main():return cli()


if __name__ == "__main__":
    main()
