"""Static Frida Foundations course; lesson browsing performs no action."""

from app.core.learning_center import Course, Lesson
from app.plugins.contribution_registry import Contribution


def _lesson(identifier, title, explanation, example, expected, *hints):
    return Lesson(
        identifier,
        title,
        explanation,
        ("Read the preceding lesson when one is listed.",),
        example,
        "Review the synthetic values and predict the displayed result. "
        "No target or script is launched.",
        expected,
        hints or ("Compare the package, process, and session state shown.",),
        "The exercise is complete when the expected synthetic state can be explained.",
    )


LESSONS = (
    _lesson("what-is-frida", "What Frida is",
            "Frida is a dynamic instrumentation toolkit. SUS Companion uses it only through an explicitly selected route, device, target, and session.",
            "Synthetic state: device=DEMO, target=org.example.demo, action=preview",
            "A reviewable plan with no running session."),
    _lesson("server-vs-gadget", "Server versus Gadget",
            "Frida Server is an existing device service, commonly requiring existing root. Gadget is deliberately embedded in an APK through a separate laboratory workflow.",
            "Route A: rooted server ready\nRoute B: Gadget preparation available",
            "Two distinct routes with different prerequisites.",
            "Neither route acquires root or patches an APK automatically."),
    _lesson("readiness", "Device and target readiness",
            "Readiness combines ADB state, host tools, endpoint reachability, architecture, and an explicit target.",
            "ADB=device; host=ready; endpoint=unreachable",
            "The route remains blocked on endpoint reachability."),
    _lesson("packages-processes", "Packages versus processes",
            "A package is a stable Android application identifier. A process is a currently running operating-system instance.",
            "package=org.example.demo; process=org.example.demo:worker",
            "One package can correspond to multiple processes."),
    _lesson("pid", "PID",
            "PID means Process ID—Android's temporary numeric identifier for a running app or service.",
            "first launch PID=412; second launch PID=927",
            "The package stays stable while the PID can change."),
    _lesson("attach-spawn", "Attach versus spawn",
            "Attach observes an app already running. Spawn starts an app under Frida; both remain explicit Sessions Center actions.",
            "attach -> running target\nspawn -> package before normal startup",
            "The operator can explain why spawn is not a synonym for attach."),
    _lesson("installed-discovery", "Installed-app discovery",
            "Installed applications are discovered through ADB and do not require Frida Server, Gadget, or a runtime endpoint.",
            "ADB package list -> org.example.demo",
            "The package appears even when no process is running."),
    _lesson("runtime-discovery", "Runtime-target discovery",
            "Runtime Targets are Frida-backed running processes and remain separate from installed applications.",
            "PID 412  Demo App",
            "A reachable Frida route returns a process target."),
    _lesson("local-script", "Loading a local observation script",
            "A reviewed Script Studio file is selected, validated, and loaded only after explicit confirmation in a dedicated runtime workflow.",
            "send({type: 'practice', value: 1});",
            "A synthetic message object; no script is loaded by this lesson.",
            "Lesson examples are not execution buttons."),
    _lesson("send-events", "Understanding send() events",
            "send() carries structured values from a Frida script to the host event view.",
            "send({type: 'lesson', result: 'observed'});",
            "The host displays a structured lesson event."),
    _lesson("java-availability", "Java.available and Java.perform",
            "Java.available indicates whether the Java runtime can be used. Java.perform schedules work when the VM is ready.",
            "if (Java.available) { Java.perform(function () { send('ready'); }); }",
            "The synthetic path sends ready only when Java is available."),
    _lesson("classes-methods", "Classes, methods, and overloads",
            "A class owns methods; overloaded methods share a name but have different argument signatures.",
            "Demo.login('name') versus Demo.login('name', 1)",
            "The signature identifies the intended overload."),
    _lesson("rpc", "RPC exports",
            "RPC exports deliberately expose named script functions to the host. They are invoked only from an active reviewed session.",
            "rpc.exports = { status: function () { return 'ready'; } };",
            "The synthetic status call returns ready."),
    _lesson("cleanup", "Session cleanup",
            "Unload scripts before detaching where practical, then close or terminate the dedicated session explicitly.",
            "loaded -> unloaded -> detached -> exited",
            "No session or script remains active."),
    _lesson("connection-loss", "Connection-loss troubleshooting",
            "A device, application, Frida service, or managed forwarding route can disappear. Preserve serial and target, check connection, and start a fresh reviewed attach or spawn when required.",
            "connected -> device gone -> disconnected",
            "The plan offers checks and reconnect; it never switches devices or restarts automatically."),
)


def course_spec(_context=None):
    return Course(
        "frida-foundations",
        "susadb.frida-tutorial",
        "Frida Foundations",
        "Fifteen local lessons using synthetic practice and no automatic execution.",
        LESSONS,
    )


class Plugin:
    def activate(self, api):
        self.api = api
        return (
            Contribution(
                "frida-tutorial.course", "learning-course",
                "Frida Foundations", factory=course_spec,
                metadata={"category": "education", "synthetic_only": True},
            ),
        )

    def deactivate(self):
        self.api = None
