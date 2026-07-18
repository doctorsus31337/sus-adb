# SUS-ADB Development Instructions

## Project vision

SUS-ADB Companion is a cross-platform Android reverse-engineering
workstation focused on ADB, Frida, Objection, device diagnostics,
APK inspection, and repeatable security-testing workflows.

The interface uses a Medieval Gothic blackhat hacker aesthetic:
black, charcoal, crimson, aged gold, and parchment tones.
Do not introduce blue UI elements.

## Development rules

1. Preserve the existing modular architecture.
2. Inspect the complete affected files before editing.
3. Never give partial integration snippets when changing source files.
4. Update every affected import in the same change.
5. Run tests and compile checks after modifications.
6. Keep GUI code separate from ADB, Frida, and Objection logic.
7. Never perform blocking subprocess work on the Tkinter UI thread.
8. Tkinter widgets may only be modified from the GUI thread.
9. Preserve Windows and Linux compatibility.
10. Do not add placeholder modules solely to increase file count.

## Folder responsibilities

- app/core: application state, managers, process execution
- app/gui: windows and composed panels
- app/widgets: reusable CustomTkinter controls
- app/modules: ADB, Frida, Objection, Logcat, APK features
- app/utils: stateless helpers
- tests: backend and regression tests

## Workflow

Before editing:

1. Inspect the repository.
2. Run the tests.
3. Explain the exact files affected.

After editing:

1. Run the tests.
2. Run Python compilation checks.
3. Show a concise diff summary.
4. Provide a Git commit summary and description.

## Safety and scope

This tool is for authorized testing of devices and applications owned
by the user or for which the user has explicit permission.
