"""Non-destructive clean-shutdown marker and recovery mode."""
from pathlib import Path
class RecoveryManager:
    def __init__(self,state_dir):self.directory=Path(state_dir).resolve();self.marker=self.directory/"running.marker"
    def begin_startup(self):
        unclean=self.marker.exists();self.directory.mkdir(parents=True,exist_ok=True);self.marker.write_text("running\n",encoding="utf-8");return unclean
    def mark_clean_shutdown(self):
        try:self.marker.unlink(missing_ok=True);return True
        except OSError:return False
    def recovery_options(self):return ("start-normally","disable-third-party-plugins")
