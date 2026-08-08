# Logcat Investigator

Logcat Investigator 0.2.0 is an official, disabled-by-default Plugin API 1.1
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
the process and incrementally analyzing new sequences in bounded memory.
Resume View catches up from the current filtered snapshot without duplicating
events. Clear View clears transcript and analysis memory only and never runs
`adb logcat -c`.

The Events view uses deterministic local rules for Java runtime crashes,
native fatal signals, ANRs, SecurityException and permission denials, SELinux
AVC denials, and ActivityManager process death. Android markers are required:
ordinary stack-looking text, slow warnings, libc warnings, permission
information, and termination messages are not promoted to stronger events.
No message content is executed or evaluated.

Java fingerprints use event kind, process/package, exception class, and the
normalized top application frame. Native fingerprints use event kind,
process/PID, signal, and a backtrace frame with volatile addresses and offsets
removed. Timestamps, object IDs, and Java source line numbers are excluded
where they would prevent sensible grouping. Different process identities do
not group.

Analysis retains at most 1,000 unique groups. An event retains no more than 100
context records (20 before and 30 after by default), 200 reconstructed stack
lines, and 100 occurrence summaries. Oldest groups are discarded on overflow
and the dropped-group count remains visible. Filters for event kind, minimum
severity, process/package substring, and free text are local and immutable.

View Details provides selectable, copyable read-only identity, detector,
stack, and raw context surfaces. Show in Transcript delimits the current
bounded context without replacing transcript filters, and provides Return to
Live View. If rollover removed required records, the module reports:
`Context is no longer present in the bounded Logcat buffer.`

Closing, unloading, uninstalling, or shutting down stops the owned process,
removes callbacks/subscriptions, and clears sensitive records and analyzed
events. Device logs may contain identifiers, paths, messages, tokens, account
information, and application data.

Bookmarks, analyst notes, evidence/finding handoff, report export,
imported/persisted captures, filesystem browsing, network/cloud analysis, AI
classification, operator-supplied detector code or regex, and automatic
remediation are deferred.
