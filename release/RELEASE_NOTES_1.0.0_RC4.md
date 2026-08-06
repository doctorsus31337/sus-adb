# SUS Companion 1.0.0 RC4

SUS Companion 1.0.0 RC4 is a **prerelease** focused on accessible scrolling,
a contextual non-executing Console Command Assistant, stronger read-only
display protection, a source-first Script Studio Agent Editor, and
independently verifiable Linux and Windows portable packages.

## Highlights since RC3

### Universal scrolling accessibility

- Adds reliable mouse-wheel scrolling, Linux Button-4/Button-5 support,
  touchpad delta support, and keyboard Page Up/Down, Home/End, and arrow
  navigation.
- Keeps handlers scoped to their owning windows, respects nested scroll
  boundaries, protects native dialogs, and cleans up bindings and callbacks on
  refresh, close, unload, and shutdown.

### Console Command Assistant

- Adds contextual prefix and token completion, related-command suggestions,
  and command-family descriptions and classifications.
- Uses only selected device and target context already held in existing
  application memory; typing never triggers a device scan.
- Performs no filesystem completion and supports keyboard-first
  Tab/Shift+Tab, Up/Down, and Ctrl+Space behavior.
- Integrates with command history without executing a command when a
  suggestion is selected or completed.

### Console safety and usability

- Makes the Console transcript read-only, selectable, copyable, and scrollable.
- Hands accidental printable transcript typing to the real command entry and
  provides explicit Ctrl+A behavior in that entry.
- Preserves command execution through the established router and interactive
  session path.

### Application-wide read-only display protection

- Protects previews, details, results, reports, logs, manifests, and
  diagnostics from accidental editing.
- Keeps actual editors, forms, notes, filters, command inputs, and drafts
  editable.
- Preserves selection, copy, Ctrl+A, wheel/touchpad scrolling, and keyboard
  reading in read-only views.

### Script Studio Agent Editor

- Gives the actual source editor dominant vertical space and uses a compact
  Ready status strip.
- Shows technical details and compatibility controls contextually while
  keeping expanded details bounded.
- Reflows the toolbar responsively while keeping all nine actions reachable.
- Adds real-main-window layout coverage at 100%, 125%, and 150% scaling.
- Makes Editor focus presentation reversible and restores normal shell chrome
  when leaving Editor.

## Inherited major capabilities

- Workspace Home and compact selected-device dock
- Universal Command Palette and Workflow Recipes
- Branded application identity and About experience
- Device Rescue and recovery workflows
- Frida and Objection assistants
- Plugin Developer Workbench
- Plugin SDK 1.1 with Plugin API 1.0 compatibility
- Plugin Project Wizard
- Linux and Windows portable packaging

## Safety and privacy

Use SUS Companion only with devices and applications you own or are explicitly
authorized to assess. The application has no telemetry and performs no
automatic upload. Opening a screen, assistant, recipe, add-on, or project does
not scan a device, attach or spawn, execute a script, run a shell, change
device state, or approve plugin capabilities.

Plugins and scripts remain disabled until their separate explicit review,
trust, capability approval, enable, load, and action boundaries are satisfied.
Capability approval is bound to the exact package digest, and scope exclusions
always win.

Plugin SDK 1.1 does not expose unrestricted subprocess, shell, filesystem,
network, ADB-shell, Frida, or Objection access. Static analysis can identify
compatibility and packaging problems, but it does not prove third-party code
is safe.

## Installation

### Linux

1. Download `sus-companion-1.0.0-rc.4-linux-x86_64.tar.gz`.
2. Verify the supplied archive SHA-256.
3. Extract the complete archive.
4. Run `sus-companion`; `sus-adb` remains as a compatibility launcher.

### Windows

1. Download `sus-companion-1.0.0-rc.4-windows-amd64.zip`.
2. Verify the supplied archive SHA-256.
3. Extract the complete archive.
4. Keep `sus-companion.exe` beside its `_internal` directory.
5. Launch `sus-companion.exe`; `sus-adb.cmd` remains a compatibility launcher.

## Current limitations

- RC4 is a prerelease and its Linux and Windows packages are unsigned.
- Windows is a portable extracted directory, not an installer.
- Optional Android, ADB, Frida, Objection, and other external tools are not
  installed automatically.
- Console completion does not include fuzzy search, filesystem or path
  completion, arbitrary host-shell expansion, live device enumeration, or
  persisted history.
- Static analysis does not prove third-party code is safe.
- Plugin SDK 1.1 does not expose unrestricted subprocess, shell, filesystem,
  network, ADB-shell, Frida, or Objection access.
- Generated plugins remain untrusted and disabled until explicitly reviewed.
- No stable 1.0.0 release is being created.
