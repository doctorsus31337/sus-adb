# SUS Companion 1.0.0 RC4

**Android Security & Recovery Workstation**

SUS Companion is a local-first Android reverse-engineering, authorized security-assessment, and recovery workstation for Linux and Windows. Use it only for devices and applications you own or have explicit permission to test.

## Install and run

Use CPython 3.11–3.13 in a virtual environment:

```sh
python -m venv .venv
python -m pip install -r requirements.txt -c constraints.txt
python main.py
```

ADB is required for device workflows. Frida, Objection, Java/APK tools, packet/proxy tools, and external terminals are optional and diagnosed without automatic installation. Run `python main.py --diagnostics` for local readiness, `--version` for version output, or `--self-test` for packaged-resource/configuration validation.

## Current tested builds

- Accepted RC source branch: `release/1.0.0-rc.4`
- Current RC tag: `v1.0.0-rc.4`

For a source checkout, select the intended branch or commit and run:

```sh
python -m pip install -r requirements.txt -c constraints.txt
python main.py
```

The manually dispatched GitHub Actions workflow **Package Current Testing Build**
accepts a branch, tag, or commit ref and produces separate Linux and Windows
artifacts. Artifact names include the selected ref and short commit hash.
Every artifact includes build identity metadata, SHA-256 checksums, a file
manifest, a verification report, and a platform publication archive. The
workflow never creates a tag or publishes a GitHub Release.

SUS Companion shows a responsive local splash while constructing the lightweight
**Workspace Home** shell. Home presents Console, Instrumentation, Device
Recovery, Script Studio, Pentest, and Sessions without scanning a device or
constructing a heavy workspace. The compact device dock retains explicit
multi-device selection and expands only when details are requested. Console is
eager; Instrumentation, Script Studio, Pentest, Plugin Manager, and Pentest's
operational sections are built only on first explicit access.

The Gothic title, **View → Home**, and **Alt+Home** return to Workspace Home.
Guided mode keeps its descriptions and recommendation concise; Advanced mode
adds compact target/serial context without placing raw commands on Home.
The compact SUS Companion emblem shares the established title-to-Home action,
and **About → About SUS Companion** opens a lazy themed build-information
window. Missing branding assets fall back to the existing text presentation.
Add-ons Center, Sessions Center, Device Rescue, assistants, Learning Center,
Context Help, Diagnostics, and Advanced Command Reference remain detached
singleton tools where designed.

The official disabled-by-default **Frida Assistant** and **Objection Assistant**
open as independent contextual windows. They consume only approved immutable
selected-device and selected-target state, provide local explanations and
copyable previews, and hand off to the shared discovery, Script Studio, and
Sessions Center workflows. Opening an assistant never scans, attaches, spawns,
loads a script, starts a server, issues an Objection command, or modifies a
device. Their original foundations lessons remain available under Learn.

Press **Ctrl+K** or choose **View → Command Palette** to search Workspaces,
Tools, Add-ons, Help, and runtime-only recent destinations. Use Up/Down,
Page Up/Page Down, Home/End, Enter, and Escape from the keyboard, or use the
mouse and themed scrollbar. Guided mode favors plain-language descriptions;
Advanced mode adds compact already-known device, target, package, and
contribution context. Palette choices only navigate or focus existing screens:
they never launch a shell, attach or spawn, run a script, change a device, or
silently install, trust, approve, enable, load, or open an unready addon.
Unready and uninstalled addons route to their Add-ons Center card.

Choose **Tools → Workflow Recipes** or search `recipes` with **Ctrl+K** for
guided Device Readiness, Frida Readiness, Instrumentation Session,
Broken-Screen Recovery Preparation, and Authorized App Assessment Setup
procedures. A recipe is a reviewable checklist, not a macro: starting it runs
nothing, one classified step is handled at a time, and Continue is always
explicit. State-changing steps show a preview and retain the existing scope
and confirmation gates. Runs bind to the exact selected serial and target;
state changes pause rather than silently adopting a replacement. Guided mode
explains why each step matters, while Advanced mode adds exact known
identifiers and technical previews. Individual palette results focus a recipe
without starting it.

The established `sus-adb` command and user-local storage directory remain supported; packaged builds prefer `sus-companion` and include a lightweight compatibility launcher. Existing configuration, cases, workspaces, plugin IDs, and trust records remain compatible. Cases and evidence are sensitive local data; back them up securely. SUS Companion has no telemetry or automatic upload.

See [installation](docs/installation.md), [responsive startup](docs/startup.md), [quick start](docs/quick-start.md), [user guide](docs/user-guide.md), [privacy/security](docs/privacy-security.md), and [testing](docs/testing.md).
