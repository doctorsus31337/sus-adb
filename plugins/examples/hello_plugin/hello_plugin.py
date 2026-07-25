"""Harmless Plugin SDK example; imported only after explicit trust, enable and load."""
from app.plugins.contribution_registry import Contribution
def report_section(_context=None):return {"title":"Plugin SDK Example","body":"The local hello example was explicitly loaded."}
class Plugin:
    def activate(self,api):
        api.message("Hello Local Example activated explicitly.")
        return (
            Contribution("hello.dashboard","dashboard-card","Hello Plugin",metadata={"read_only":True}),
            Contribution("hello.menu","menu-action","Hello from Plugin",metadata={"read_only":True}),
            Contribution("hello.report","report-section","Plugin SDK Example",factory=report_section,capability_requirement="contribute-report-section"),
            Contribution("hello.script","script-asset","Hello Observer",metadata={"path":"assets/hello_observer.js"}),
        )
    def deactivate(self):pass
