# SUS Companion 1.0.0 RC2

SUS Companion 1.0.0 RC2 is a **prerelease** focused on operator experience,
recovery reliability, interactive tooling, and cross-platform packaging.

## Highlights

- Rebrands the workstation as SUS Companion and keeps startup responsive with
  a local splash, eager Console, and lazy heavy workspaces.
- Makes Device Rescue operational for explicitly selected files through
  already-available authorized storage routes, with destination preflight,
  bounded queues, progress, cancellation, resume manifests, hashing, and
  partial-success reporting.
- Adds Sessions Center for dedicated ADB Shell, Objection, Frida REPL, and
  Frida Trace sessions without blocking the one-shot Console.
- Makes Objection connection loss recoverable with same-device diagnostics,
  managed-forwarding repair, preserved context/history, and bounded technical
  details.
- Adds inline Script Studio operation feedback, loaded/reload-required state,
  source-line errors, script-path discovery, and advisories hidden by default.
- Adds persisted Guided and Advanced modes without removing backend capability.
- Separates ADB-installed applications from Frida runtime targets.
- Adds local Contextual Help, searchable glossary, deterministic guide, and
  Learning Center.
- Expands Instrumentation & Root Readiness Advisor while preserving the
  no-root-acquisition and no-flashing boundary.
- Converts the educational add-ons into independent Frida Assistant and
  Objection Assistant windows with immutable live context and explicit
  handoffs to shared workflows.
- Stabilizes Add-ons Center card/focus lifecycle on Linux and Windows.
- Corrects compact Pentest navigation, wrapped actions, Help labels, and main
  sidebar clutter.

## Safety and privacy

SUS Companion has no telemetry and performs no automatic upload. Plugins and
scripts remain disabled until explicit review, trust, approval, enablement, and
load actions as applicable. Device, Frida, Objection, root, APK, and recovery
actions are never triggered merely by opening an assistant or refreshing state.

Bootloader unlocking commonly wipes user data and must not be used as a
recovery technique.

## Installation

### Windows

1. Download the Windows archive.
2. Verify its SHA-256 checksum.
3. Extract the entire archive.
4. Keep `sus-companion.exe` beside its `_internal` dependency directory.
5. Launch `sus-companion.exe`.
6. Do not run it from inside the compressed archive.

The Windows package is an unsigned portable extracted folder, not an installer.

### Linux

1. Download the Linux archive.
2. Verify its SHA-256 checksum.
3. Extract it.
4. Run the included `sus-companion` executable.

The `sus-adb` compatibility launcher remains included on both platforms where
supported by the platform packaging format.

## Current limitations

- RC2 packages are unsigned.
- External Android/security tools remain optional and are not installed
  automatically.
- Windows is portable extract-and-run software, not an installer.
- No reviewed core curated Script Studio pack is bundled.
- Trusted in-process plugins are trusted Python code, not a hardened sandbox.
- PDF report generation remains outside v1; offline HTML, Markdown, and JSON
  are supported.
