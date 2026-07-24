# SUS Companion 1.0.0-rc.1

**Android Security & Recovery Workstation**

SUS Companion is a local-first Android reverse-engineering, authorized security-assessment, and recovery workstation for Linux and Windows. Use it only for devices and applications you own or have explicit permission to test.

## Install and run

Use CPython 3.11–3.13 in a virtual environment:

```sh
python -m venv .venv
python -m pip install -r requirements.txt
python main.py
```

ADB is required for device workflows. Frida, Objection, Java/APK tools, packet/proxy tools, and external terminals are optional and diagnosed without automatic installation. Run `python main.py --diagnostics` for local readiness, `--version` for version output, or `--self-test` for packaged-resource/configuration validation.

## Current tested builds

- Latest tested development branch: `feature/operator-experience-reliability`
- Stable RC branch: `release/1.0.0-rc.1`

For a source checkout, select the intended branch or commit and run:

```sh
python -m pip install -r requirements.txt
python main.py
```

The manually dispatched GitHub Actions workflow **Package Current Testing Build**
accepts a branch, tag, or commit ref and produces separate Linux and Windows
artifacts. Artifact names include the selected ref and short commit hash.
Every artifact includes build identity metadata, SHA-256 checksums, a file
manifest, and a verification report. The workflow never creates a tag or
publishes a GitHub Release. Treat current-testing artifacts as acceptance
builds, not as a replacement for the stable RC branch.

SUS Companion shows a responsive local splash while constructing the Console shell. Instrumentation, Script Studio, Pentest, Plugin Manager, and Pentest's operational sections are built only on first explicit access. Script Studio includes the local Script Library and import, edit, validate, and explicit load workflows. Official addons and third-party code remain inactive until their separate lifecycle approvals are completed.

The official disabled-by-default **Frida Assistant** and **Objection Assistant**
open as independent contextual windows. They consume only approved immutable
selected-device and selected-target state, provide local explanations and
copyable previews, and hand off to the shared discovery, Script Studio, and
Sessions Center workflows. Opening an assistant never scans, attaches, spawns,
loads a script, starts a server, issues an Objection command, or modifies a
device. Their original foundations lessons remain available under Learn.

The established `sus-adb` command and user-local storage directory remain supported; packaged builds prefer `sus-companion` and include a lightweight compatibility launcher. Existing configuration, cases, workspaces, plugin IDs, and trust records remain compatible. Cases and evidence are sensitive local data; back them up securely. SUS Companion has no telemetry or automatic upload.

See [installation](docs/installation.md), [responsive startup](docs/startup.md), [quick start](docs/quick-start.md), [user guide](docs/user-guide.md), [privacy/security](docs/privacy-security.md), and [testing](docs/testing.md).
