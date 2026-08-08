# Logcat Investigator 0.2.0

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

The Events view incrementally analyzes only newly captured sequence numbers.
Deterministic local rules identify Java crashes, native fatal signals, ANRs,
SecurityException and permission denials, SELinux AVC denials, and
ActivityManager process deaths. Stack continuations and bounded surrounding
records are reconstructed without executing log content. Stable fingerprints
group repeated occurrences into at most 1,000 event groups, with 100 context
records and 200 stack lines per event. Oldest groups are discarded with a
visible dropped-group count.

Event kind, minimum severity, process/package, and free-text filters are local
and do not restart capture. Event details and raw context are read-only.
Show in Transcript temporarily delimits an available event context without
changing transcript filters; expired bounded-buffer context is reported
honestly. Pause View pauses transcript presentation only—capture and event
analysis continue.

Device logs can contain identifiers, paths, messages, tokens, account
information, and application data. Closing, unloading, uninstalling, or
shutting down stops capture and clears sensitive records and analyzed events.

Bookmarks, analyst notes, evidence/finding handoff, reports or export,
imported or persisted captures, filesystem browsing, network/cloud analysis,
AI classification, operator-supplied detector code or regex, and automatic
remediation are deferred.
