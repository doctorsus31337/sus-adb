# Logcat Investigator

Logcat Investigator 0.1.0 is an official, disabled-by-default Plugin API 1.1
module. It requests `read-selected-device` and the privacy-sensitive
`read-device-logs` capability. Approval remains bound to the exact package
digest; enable, load, open, and Start Capture are separate explicit actions.

The host binds capture to the exact selected online ADB serial and launches:

```text
<resolved-adb-path> -s <serial> logcat -v threadtime
```

Output is decoded with deterministic replacement, parsed without execution,
and retained in a bounded 10,000-record memory buffer. The oldest record is
dropped on overflow and the dropped count remains visible. Priority, tag,
exact PID, and case-insensitive message filters are local and never restart
capture.

Pause View pauses only transcript presentation; the host continues draining
the process into bounded memory. Resume View catches up from the current
filtered snapshot. Clear View clears host memory/display only and never runs
`adb logcat -c`.

Closing, unloading, uninstalling, or shutting down stops the owned process,
removes callbacks/subscriptions, and clears sensitive records. Device logs may
contain identifiers, paths, messages, tokens, account information, and
application data.

Crash/ANR intelligence, grouping, bookmarks, analyst notes, timelines,
evidence/finding handoff, report export, imported/persisted captures,
filesystem browsing, and regex filters are deferred.
