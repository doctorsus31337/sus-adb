"""Objection Assistant declarations and secondary synthetic learning course."""

from app.core.learning_center import Course, Lesson
from app.plugins.contribution_registry import Contribution
from app.plugins.plugin_ui import PluginPanelSpec, PluginView


def _lesson(identifier, title, explanation, example, expected, *hints):
    return Lesson(
        identifier,
        title,
        explanation,
        ("Use only the synthetic prompt shown in this course.",),
        example,
        "Read the synthetic transcript and identify the prompt, command, and result. "
        "No command is sent.",
        expected,
        hints or ("Separate reference text from an executable session action.",),
        "The exercise is complete when the synthetic session state can be explained.",
    )


LESSONS = (
    _lesson("what-objection-adds", "What Objection adds to Frida",
            "Objection provides an interactive command layer built on Frida. It still needs an explicit device, target, route, and dedicated session.",
            "Frida route ready -> Objection prompt available",
            "Objection does not replace Frida readiness."),
    _lesson("connecting", "Connecting to a target",
            "Attach and spawn are distinct plans. Sessions Center binds the command to the selected serial and package.",
            "serial=DEMO; package=org.example.demo; mode=attach",
            "A command preview appears; no session launches in the lesson."),
    _lesson("prompt", "Understanding the prompt",
            "The prompt shows that an interactive Objection session is ready to accept a command.",
            "[usb] org.example.demo on (android: 13) [explore] #",
            "The prompt is a session state, not command output."),
    _lesson("command-groups", "Command groups",
            "Commands are grouped by platform and purpose. Review contextual help before using a group in an authorized session.",
            "android hooking list classes",
            "The example is recognized as an Android command-group path."),
    _lesson("contextual-help", "Contextual help",
            "`help android sslpinning` is a help/reference command. It describes a command group; it is not the action itself.",
            "help android sslpinning",
            "Reference text is displayed without invoking a pinning action.",
            "A successful help result does not prove the later prompt redraw will remain connected."),
    _lesson("application-info", "Application information",
            "Application-information commands summarize the selected target. The package remains explicit.",
            "android hooking get current_activity",
            "A synthetic activity name is returned."),
    _lesson("activities-services", "Activities and services",
            "Activities are user-facing Android components; services perform background work. Listing is distinct from starting.",
            "activities=[MainActivity]; services=[SyncService]",
            "The transcript contains a read-only list."),
    _lesson("files-preferences", "Files/preferences concepts",
            "Application files and preferences can contain sensitive data. Access depends on existing routes and assessment scope.",
            "preferences keys=[theme, tutorial_seen]",
            "Only key names appear in synthetic practice."),
    _lesson("jobs-history", "Jobs/history",
            "Objection jobs represent ongoing work; history recalls prior prompt commands where available.",
            "jobs list -> 1 synthetic-observer",
            "The job can be distinguished from command history."),
    _lesson("cleanup", "Session cleanup",
            "Stop reviewed jobs, preserve useful history, then exit or terminate the dedicated session explicitly.",
            "job running -> stopped; prompt -> exit",
            "The session reaches exited without an orphan."),
    _lesson("device-gone", "Device-gone troubleshooting",
            "A help command may succeed, then prompt redraw can fail because the device or application vanished. This is a connection loss, not invalid syntax.",
            "help result=success\nnext prompt=frida.InvalidOperationError: device is gone",
            "The host offers Check Connection, managed-forwarding repair, reconnect, and diagnostics.",
            "Never switch serials silently or auto-attach."),
    _lesson("common-errors", "Common errors",
            "Distinguish invalid command syntax, endpoint failure, process exit, forwarding loss, and device-gone cleanup noise.",
            "primary=device gone; cleanup=script is destroyed",
            "The primary connection error remains visible while cleanup noise is bounded."),
    _lesson("exporting-notes", "Exporting notes",
            "Record learning notes locally and deliberately. Course browsing never registers evidence or uploads telemetry.",
            "note='Prompt help reviewed'",
            "A local note exists only after an explicit save workflow."),
    _lesson("move-to-script-studio", "Moving from Objection to Script Studio",
            "Use Script Studio when a reviewed repeatable observation script is more appropriate than interactive commands.",
            "interactive observation -> reviewed local script draft",
            "The operator opens Script Studio; no script is generated or loaded automatically."),
)


def course_spec(_context=None):
    return Course(
        "objection-foundations",
        "susadb.objection-tutorial",
        "Objection Foundations",
        "Fourteen local lessons using synthetic prompt practice and no automatic execution.",
        LESSONS,
    )


def panel_spec(context=None):
    device = dict(getattr(context, "selected_device", {}) or {})
    target = dict(getattr(context, "selected_target", {}) or {})
    serial = str(device.get("serial", ""))
    identifier = str(target.get("identifier") or target.get("name") or "")
    return PluginPanelSpec(
        "Objection Assistant",
        (
            PluginView(
                "Overview",
                "Host-owned contextual assistance for targets, connection plans, "
                "dedicated sessions, command previews, recovery, and learning.",
                (
                    ("Selected serial", serial or "None"),
                    ("Selected target", identifier or "None"),
                ),
            ),
        ),
        {"device": serial or "None", "target": identifier or "None"},
    )


class Plugin:
    def activate(self, api):
        self.api = api
        return (
            Contribution(
                "objection-assistant.panel", "pentest-panel",
                "Objection Assistant", factory=panel_spec,
                metadata={
                    "ui_mode": "window", "singleton": True,
                    "workspace_kind": "objection-assistant",
                    "default_width": 1180, "default_height": 780,
                    "minimum_width": 900, "minimum_height": 650,
                },
            ),
            Contribution(
                "objection-assistant.menu", "menu-action",
                "Open Objection Assistant",
                metadata={"target": "objection-assistant.panel"},
            ),
            Contribution(
                "objection-tutorial.course", "learning-course",
                "Objection Foundations", factory=course_spec,
                metadata={"category": "education", "synthetic_only": True},
            ),
        )

    def deactivate(self):
        self.api = None
