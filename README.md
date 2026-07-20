# SUS-ADB Companion 1.0.0-rc.1

SUS-ADB is a local-first Android reverse-engineering and authorized security-assessment workstation for Linux and Windows. Use it only for devices and applications you own or have explicit permission to test.

## Install and run

Use CPython 3.11–3.13 in a virtual environment:

```sh
python -m venv .venv
python -m pip install -r requirements.txt
python main.py
```

ADB is required for device workflows. Frida, Objection, Java/APK tools, packet/proxy tools, and external terminals are optional and diagnosed without automatic installation. Run `python main.py --diagnostics` for local readiness, `--version` for version output, or `--self-test` for packaged-resource/configuration validation.

SUS-ADB includes Console, Instrumentation, Script Studio, and an authorized Pentest workspace with ADB, Runtime, Network, Storage, APK, Findings/Reports, and local Plugin Manager sections. Script Studio includes the local Script Library and import, edit, validate, and explicit load workflows. RC1 does not bundle a reviewed core curated script pack. The disabled hello example plugin includes a harmless demonstration asset; it does not load automatically. User-authored and third-party scripts execute only after explicit review and approval, and private/local Script Studio files are not release-package inputs.

Configuration and logs use the user-local platform configuration directory. Cases and evidence are sensitive local data; back them up securely. SUS-ADB has no telemetry or automatic upload.

See [installation](docs/installation.md), [quick start](docs/quick-start.md), [user guide](docs/user-guide.md), [privacy/security](docs/privacy-security.md), and [testing](docs/testing.md).
