"""Local-only contextual help topics and glossary for SUS Companion."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True, slots=True)
class HelpTopic:
    topic_id: str
    title: str
    purpose: str
    prerequisites: tuple[str, ...]
    quick_start: tuple[str, ...]
    controls: tuple[str, ...]
    terminology: tuple[str, ...]
    empty_states: tuple[str, ...]
    common_errors: tuple[str, ...]
    safe_example: str
    related_tools: tuple[str, ...]
    mode_notes: str

    @property
    def searchable_text(self) -> str:
        values = (
            self.topic_id,
            self.title,
            self.purpose,
            *self.prerequisites,
            *self.quick_start,
            *self.controls,
            *self.terminology,
            *self.empty_states,
            *self.common_errors,
            self.safe_example,
            *self.related_tools,
            self.mode_notes,
        )
        return " ".join(values).casefold()


@dataclass(frozen=True, slots=True)
class GlossaryEntry:
    term: str
    definition: str
    related_terms: tuple[str, ...] = ()

    @property
    def searchable_text(self) -> str:
        return " ".join(
            (self.term, self.definition, *self.related_terms)
        ).casefold()


def _topic(
    topic_id: str,
    title: str,
    purpose: str,
    quick: str,
    *,
    prerequisites: tuple[str, ...] = ("No network connection is required.",),
    controls: tuple[str, ...] = ("Use the visible controls; actions never run merely by opening help.",),
    terminology: tuple[str, ...] = ("See the local glossary for this workspace.",),
    empty_states: tuple[str, ...] = ("An empty view explains which scan or selection is still required.",),
    common_errors: tuple[str, ...] = ("Confirm the selected device, target, and authorization state.",),
    example: str = "Review the current state and preview the next action before confirming it.",
    related: tuple[str, ...] = ("Console",),
) -> HelpTopic:
    return HelpTopic(
        topic_id,
        title,
        purpose,
        prerequisites,
        (quick,),
        controls,
        terminology,
        empty_states,
        common_errors,
        example,
        related,
        "Guided mode explains intent and hides raw identifiers under Advanced Details. Advanced mode keeps direct technical controls.",
    )


TOPICS = (
    _topic(
        "console", "Console",
        "Run bounded one-shot commands and review their output.",
        "Enter a finite ADB or diagnostic command, then choose Run.",
        terminology=("ADB", "one-shot command", "interactive session"),
        common_errors=("Interactive commands are redirected to Sessions Center.", "A busy message means a finite command is still running."),
        example="adb devices",
        related=("Sessions Center", "Advanced Command Reference"),
    ),
    _topic(
        "instrumentation-overview", "Instrumentation Overview",
        "Assess host Frida, device readiness, forwarding, and available observation routes.",
        "Select a device, run diagnostics, then review recommendations.",
        terminology=("Frida Server", "Frida Gadget", "port forwarding"),
        related=("Targets", "Sessions", "Instrumentation & Root Readiness Advisor"),
    ),
    _topic(
        "targets", "Targets",
        "Keep ADB-installed applications separate from Frida runtime processes.",
        "Scan Installed Apps without Frida, or scan Runtime Targets after a Frida route is ready.",
        terminology=("package", "process", "PID", "runtime target"),
        empty_states=("ADB scan not run, no installed apps, Frida unavailable, and no running targets are shown distinctly.",),
        related=("Instrumentation Overview", "Sessions"),
    ),
    _topic(
        "sessions", "Instrumentation Sessions",
        "Preview and launch explicit Frida and Objection sessions.",
        "Select a target, review the command preview, validate readiness, then launch.",
        terminology=("attach", "spawn", "endpoint"),
        related=("Sessions Center", "Script Studio"),
    ),
    _topic(
        "script-studio", "Script Studio",
        "Edit, validate, load, reload, and observe local Frida scripts.",
        "Select a local script, attach to an authorized target, validate, then load explicitly.",
        terminology=("RPC", "send()", "Reload Required"),
        common_errors=("Compilation errors remain beside the editor with source-line navigation.", "Runtime errors open Messages."),
        example="send({type: 'practice', value: 1});",
        related=("Sessions Center", "Runtime Explorer"),
    ),
    _topic(
        "pentest-dashboard", "Pentest Dashboard",
        "Coordinate an explicitly authorized assessment scope and local artifacts.",
        "Create or open a case, confirm scope, then start the assessment session.",
        terminology=("scope", "evidence", "finding"),
        related=("Findings/Reports", "ADB Explorer"),
    ),
    _topic(
        "adb-explorer", "ADB Explorer",
        "Inspect packages, files, components, logs, and captures through explicit ADB routes.",
        "Select an authorized device and choose a read-only scan first.",
        terminology=("ADB", "package", "user app", "system app"),
        related=("Storage", "APK Laboratory"),
    ),
    _topic(
        "runtime-explorer", "Runtime Explorer",
        "Inspect Java and native runtime structures through an active Frida session.",
        "Attach explicitly, select a runtime target, then run a bounded discovery action.",
        terminology=("runtime target", "class", "module", "export"),
        related=("Script Studio", "Instrumentation Sessions"),
    ),
    _topic(
        "network", "Network",
        "Plan authorized proxying, bounded capture, and local event review.",
        "Review diagnostics and scope before applying any state-changing network configuration.",
        terminology=("port forwarding", "proxy", "capture"),
        related=("Runtime Explorer", "Findings/Reports"),
    ),
    _topic(
        "storage", "Storage",
        "Inspect selected application and shared-storage data through explicitly available access routes.",
        "Choose a package or path, preview access, then run a bounded read-only operation.",
        terminology=("shared storage", "run-as", "root"),
        related=("ADB Explorer", "Device Rescue"),
    ),
    _topic(
        "apk-laboratory", "APK Laboratory",
        "Acquire, inspect, compare, decode, build, sign, and install APKs as separate confirmed steps.",
        "Select a local or explicitly acquired APK and begin with static inspection.",
        terminology=("APK", "ABI", "Frida Gadget"),
        related=("Instrumentation & Root Readiness Advisor", "WebView Inspector"),
    ),
    _topic(
        "findings-reports", "Findings/Reports",
        "Create local findings and deterministic reports without automatic upload.",
        "Create a draft finding, validate it, then explicitly export a report.",
        terminology=("finding", "evidence", "severity"),
        related=("Pentest Dashboard", "Network"),
    ),
    _topic(
        "plugin-manager", "Plugin Manager",
        "Install, trust, approve, enable, load, and unload plugins as distinct actions.",
        "Inspect a package digest and capabilities before explicitly trusting it.",
        terminology=("plugin capability", "package digest", "trust"),
        related=("Add-ons Center",),
    ),
    _topic(
        "addons-center", "Add-ons Center",
        "Discover and manage official add-ons without automatic installation or loading.",
        "Review an add-on card, then perform only the lifecycle transition you intend.",
        terminology=("addon", "capability", "detached window"),
        related=("Plugin Manager", "Learning Center"),
    ),
    _topic(
        "device-rescue", "Device Rescue",
        "Recover explicitly selected files from access routes already available on an owned device.",
        "Refresh devices, select the same serial, scan storage, choose a destination, then review a bounded plan.",
        terminology=("resume manifest", "safety headroom", "recovery ADB"),
        common_errors=("Unknown source size requires bounded selected-file acknowledgement.", "A serial change interrupts the queue."),
        related=("Storage", "Instrumentation & Root Readiness Advisor"),
    ),
    _topic(
        "readiness-advisor", "Instrumentation & Root Readiness Advisor",
        "Assess existing instrumentation routes and explain prerequisites without acquiring root.",
        "Refresh devices, inspect evidence, then review a non-executing route plan.",
        terminology=("bootloader", "root", "Frida Server", "Frida Gadget"),
        related=("Instrumentation Overview", "APK Laboratory"),
    ),
    _topic(
        "webview-inspector", "WebView Inspector",
        "Review WebView configuration and observation candidates without automatic hooks.",
        "Select an authorized application and begin with static candidates.",
        terminology=("WebView", "JavaScript bridge", "debuggable app"),
        related=("APK Laboratory", "Runtime Explorer"),
    ),
    _topic(
        "sessions-center", "Sessions Center",
        "Control dedicated interactive terminals without blocking the one-shot Console.",
        "Select a session type, confirm serial and target, review argv, then launch.",
        terminology=("interactive session", "external terminal", "reconnect"),
        related=("Console", "Script Studio"),
    ),
    _topic(
        "learning-center", "Learning Center",
        "Browse local educational add-ons, glossary entries, progress, and safe synthetic practice.",
        "Choose a course or glossary term; lesson browsing performs no device action.",
        prerequisites=("No device or network connection is required.",),
        terminology=("lesson", "bookmark", "synthetic practice"),
        related=("Contextual Help", "Advanced Command Reference"),
    ),
    _topic(
        "advanced-command-reference", "Advanced Command Reference",
        "Look up established technical commands after understanding the workflow.",
        "Search by tool or goal, then copy a preview into the appropriate confirmed workflow.",
        terminology=("argv", "placeholder", "endpoint"),
        related=("Console", "Sessions Center"),
    ),
)


GLOSSARY = (
    GlossaryEntry("ADB", "Android Debug Bridge, the host tool used for authorized device communication.", ("device",)),
    GlossaryEntry("package", "Android's stable application identifier, such as org.example.app.", ("APK", "process")),
    GlossaryEntry("process", "A running operating-system instance of an application or service.", ("PID", "package")),
    GlossaryEntry("PID", "Process ID: Android's temporary numeric identifier for a running process.", ("process",)),
    GlossaryEntry("attach", "Connect instrumentation to an application or process that is already running.", ("spawn",)),
    GlossaryEntry("spawn", "Start an application under instrumentation before its normal entry point continues.", ("attach",)),
    GlossaryEntry("Frida Server", "A Frida service already running on a device, commonly requiring existing root.", ("Frida Gadget", "root")),
    GlossaryEntry("Frida Gadget", "A Frida runtime library deliberately embedded into an APK.", ("Frida Server", "APK")),
    GlossaryEntry("root", "Privileged Android access. SUS Companion does not acquire root automatically.", ("bootloader",)),
    GlossaryEntry("bootloader", "The device startup component that verifies and loads the operating system.", ("root",)),
    GlossaryEntry("port forwarding", "An explicit ADB mapping connecting a host TCP port to a device TCP port.", ("ADB",)),
    GlossaryEntry("RPC", "Remote Procedure Call exports deliberately exposed by a loaded Frida script.", ("Script Studio",)),
    GlossaryEntry("Script Studio", "The local editor and runtime controller for reviewed Frida scripts.", ("RPC",)),
    GlossaryEntry("runtime target", "A running application or process visible through a working Frida route.", ("process",)),
    GlossaryEntry("APK", "Android Package file containing an application's code and resources.", ("package", "ABI")),
    GlossaryEntry("ABI", "Application Binary Interface describing the device CPU architecture expected by native code.", ("arm64", "x86_64")),
    GlossaryEntry("arm64", "The common 64-bit ARM Android architecture, also called arm64-v8a.", ("ABI",)),
    GlossaryEntry("x86_64", "A 64-bit x86 architecture common in Android emulators.", ("ABI",)),
    GlossaryEntry("scope", "The explicit authorization boundary for an assessment.", ("evidence", "finding")),
    GlossaryEntry("evidence", "A local artifact deliberately registered with an authorized case.", ("scope", "finding")),
    GlossaryEntry("finding", "A structured, reviewable security observation linked to scope and evidence.", ("evidence",)),
    GlossaryEntry("user app", "An application installed for users rather than supplied as a system package.", ("system app",)),
    GlossaryEntry("system app", "An application supplied on a protected system or product partition.", ("user app",)),
    GlossaryEntry("debuggable app", "An Android application built with debugging enabled.", ("package",)),
)


class HelpRegistry:
    def __init__(
        self,
        topics: Iterable[HelpTopic] = TOPICS,
        glossary: Iterable[GlossaryEntry] = GLOSSARY,
    ):
        self._topics = {topic.topic_id: topic for topic in topics}
        self._glossary = {entry.term.casefold(): entry for entry in glossary}

    def topics(self) -> tuple[HelpTopic, ...]:
        return tuple(sorted(self._topics.values(), key=lambda item: item.title))

    def glossary(self) -> tuple[GlossaryEntry, ...]:
        return tuple(sorted(self._glossary.values(), key=lambda item: item.term.casefold()))

    def get(self, topic_id: str) -> HelpTopic | None:
        return self._topics.get(topic_id)

    def search_topics(self, query: str) -> tuple[HelpTopic, ...]:
        value = query.strip().casefold()
        return tuple(
            topic for topic in self.topics()
            if not value or value in topic.searchable_text
        )

    def search_glossary(self, query: str) -> tuple[GlossaryEntry, ...]:
        value = query.strip().casefold()
        return tuple(
            entry for entry in self.glossary()
            if not value or value in entry.searchable_text
        )
