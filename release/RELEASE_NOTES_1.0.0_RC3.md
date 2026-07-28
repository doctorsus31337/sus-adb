# SUS Companion 1.0.0 RC3

SUS Companion 1.0.0 RC3 is a **prerelease** focused on a clearer operator
workspace, reliable recovery and instrumentation assistance, Plugin SDK 1.1,
and independently verifiable Linux and Windows portable packages.

## Highlights

- Redesigns Workspace Home around six clear entry points and a compact
  selected-device dock while preserving explicit device and target ownership.
- Adds the Universal Command Palette for safe navigation and focus without
  silently executing commands or advancing addon lifecycle state.
- Adds Workflow Recipes as operator-reviewed procedures whose classified steps
  never run or advance automatically.
- Completes SUS Companion visual branding across the splash, application shell,
  About window, launchers, and packaged runtime assets.
- Improves Add-ons Center scrolling, filtering, focus, review, update,
  rollback, and post-update activation lifecycle behavior.
- Improves Device Rescue and recovery reliability with bounded queues,
  progress, cancellation, resume metadata, integrity checks, and
  partial-success reporting.
- Improves Frida and Objection assistants with immutable selected-device and
  selected-target context, explicit handoffs, and recoverable session guidance.
- Adds the Plugin Developer Workbench for bounded non-executing compatibility,
  privacy, capability, SDK, and deterministic packaging analysis.
- Introduces Plugin SDK 1.1 host-rendered forms, actions, confirmations,
  progress, cancellation, refresh behavior, and safe navigation while
  preserving Plugin API 1.0 compatibility.
- Adds the Plugin Project Wizard with deterministic, inert addon folder and ZIP
  generation, exact identity ownership, validation, and Workbench handoff.
- Produces independently verifiable Linux and Windows one-folder packages with
  exact build identity, manifests, checksums, verification reports, branding,
  privacy auditing, and protected-path controls.

## Safety and privacy

Use SUS Companion only with devices and applications you own or are explicitly
authorized to assess. The application has no telemetry and performs no
automatic upload. Opening a screen, assistant, recipe, addon, or project does
not scan a device, attach or spawn, execute a script, run a shell, change
device state, or approve plugin capabilities.

Plugins and scripts remain disabled until their separate explicit review,
trust, capability approval, enable, load, and action boundaries are satisfied.
Capability approval is bound to the exact package digest, and scope exclusions
always win.

Plugin SDK 1.1 does not expose unrestricted shell, subprocess, filesystem,
network, ADB shell, Frida, or Objection capabilities. Static analysis can
identify compatibility and packaging problems, but it does not prove
third-party code is safe.

## Installation

### Linux

1. Download `sus-companion-1.0.0-rc.3-linux-x86_64.tar.gz`.
2. Verify the supplied archive SHA-256.
3. Extract the complete archive.
4. Run `sus-companion`; `sus-adb` remains as a compatibility launcher.

### Windows

1. Download `sus-companion-1.0.0-rc.3-windows-amd64.zip`.
2. Verify the supplied archive SHA-256.
3. Extract the complete archive.
4. Keep `sus-companion.exe` beside its `_internal` directory.
5. Launch `sus-companion.exe`; `sus-adb.cmd` remains a compatibility launcher.

## Current limitations

- RC3 is a prerelease and its Linux and Windows packages are unsigned.
- Windows is a portable extracted folder, not an installer.
- Optional Android, ADB, Frida, Objection, and other external tools are not
  installed automatically.
- No reviewed core curated Script Studio pack is bundled.
- Trusted in-process plugins are trusted Python code, not a hardened sandbox.
- PDF report generation remains outside v1; offline HTML, Markdown, and JSON
  are supported.
- The legacy branding multi-root test harness may emit pre-existing
  CustomTkinter teardown notices while its assertions report PASS. The
  authoritative isolated application and packaged normal-shutdown probes
  remain clean with no callbacks or workers left behind.
