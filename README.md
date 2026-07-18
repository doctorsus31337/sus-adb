# SUS-ADB Companion

Cross-platform Android reverse-engineering companion with a Medieval Gothic blackhat interface.

## Current recovery build

- Detects ADB, Fastboot, Frida, and Objection on the host.
- Discovers online, offline, and unauthorized Android devices.
- Retrieves device model, Android version, ABI, battery, root, and Frida-server status.
- Renders selectable device cards.
- Runs terminal commands without freezing the GUI.
- Marshals background output safely back onto Tk's UI thread.
- Forwards Frida ports 27042 and 27043 for the selected device.
- Provides a non-modal command cheat sheet that can remain open while the main terminal is used.

## Run

```powershell
python -m pip install -r requirements.txt
python main.py
```

## Test

```powershell
python -m unittest discover -s tests -v
```

## Planned milestones

1. Stable ADB/device foundation
2. Frida diagnostics and server lifecycle
3. Objection session launcher
4. Target application/process selector
5. Logcat, packages, APK install/pull, screenshots, and file browser
6. Profiles, sessions, plugins, and packaging for Windows/Linux
