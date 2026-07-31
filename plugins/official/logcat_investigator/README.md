# Logcat Investigator 0.1.0

Logcat Investigator is an official, disabled-by-default Plugin API 1.1 module.
Installation, exact-digest trust, approval of `read-selected-device` and
`read-device-logs`, enable, load, and open are separate explicit steps. Opening
the window never begins capture.

The host—not plugin code—owns the exact selected serial, structured
`adb -s SERIAL logcat -v threadtime` process, bounded 10,000-record buffer,
stdout/stderr draining, filtering, UI dispatch, termination, and cleanup.
Pause View pauses presentation only; capture continues into bounded memory.
Clear View clears host memory/display only and never clears Android's Logcat
buffer.

Device logs can contain identifiers, paths, messages, tokens, account
information, and application data. Closing, unloading, uninstalling, or
shutting down stops capture and clears sensitive records.

Crash/ANR intelligence, grouping, bookmarks, analyst notes, timelines,
evidence/finding handoff, export, imported or persisted captures, filesystem
browsing, and regex filters are deferred to later milestones.
