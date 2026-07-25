# SUS Companion Development Instructions

## Product and safety

SUS Companion is a cross-platform Android reverse-engineering and authorized
security-testing workstation built with Python and CustomTkinter. Use it only
with devices and applications owned by the operator or covered by explicit
permission.

Preserve the Medieval Gothic blackhat visual language: black and charcoal
backgrounds, crimson emphasis, aged-gold highlights, parchment tones, readable
spacing, and no default-blue widgets.

## Architecture and implementation

1. Preserve the modular architecture and reuse existing managers, stores,
   workers, lifecycle coordinators, navigation, plugin state, and host state.
2. Read every affected implementation and directly relevant test in full
   before editing.
3. Make complete integrations, including every affected import; do not provide
   partial source-file snippets.
4. Keep GUI composition separate from ADB, Frida, Objection, package, storage,
   reporting, and process logic.
5. Never block the Tk UI thread, and modify Tk widgets only from that thread.
6. Use explicit selected serials and targets; never switch either silently.
7. Preserve Windows and Linux support, including paths containing spaces.
8. Launch processes with structured argv and `shell=False`.
9. Preserve lazy construction, responsive startup, and Guided/Advanced modes.
10. Use the existing theme dictionary; do not hard-code unrelated colors.
11. Do not create duplicate managers, parallel state systems, placeholder
    modules, or files added only to increase file count.

## Folder responsibilities

- `app/core`: application state, managers, lifecycle, and process execution
- `app/gui`: windows and composed panels
- `app/widgets`: reusable CustomTkinter controls
- `app/modules`: ADB, Frida, Objection, Logcat, and APK features
- `app/utils`: stateless helpers
- `tests`: backend, fake-driven, and regression coverage

## Plugin SDK boundaries

- Plugins import only public `app.plugins` SDK surfaces.
- Plugins receive no raw Tk root, raw managers, unrestricted subprocess or
  filesystem access, credentials, or secret-provider access.
- Install, trust, capability approval, enable, load, open, close, unload,
  disable, and uninstall remain separate lifecycle actions.
- Capability approval is bound to the exact package digest, and scope
  exclusions always win.
- The host owns addon windows, focus, geometry, theme, subscriptions, and
  cleanup.
- Report an SDK compatibility gap instead of importing private core services.

## Protected and user-local paths

Do not inspect, print, modify, stage, commit, package, or summarize these paths
unless the operator explicitly authorizes the exact file:

- `scripts/frida/custom/flutter_popup_bypass.js`
- `scripts/metadata/flutter_popup_bypass.meta.json`
- `activate_venv.sh`
- `bd_prefs/`

Leave user-local scripts, plugin state, configuration, preferences, cases,
assessments, evidence, reports, logs, recovered files, APKs, firmware,
binaries, credentials, private keys, certificates, keystores, caches, and
build outputs untouched. Protected or unrelated untracked files do not by
themselves justify stopping.

## Git and branch rules

- Before editing, fetch origin and verify the branch, expected ancestry, origin
  synchronization, and tracked cleanliness.
- Never work directly on `main`, a published release branch, or a tag unless
  explicitly authorized.
- Never force-push, amend accepted commits, rewrite history, delete branches,
  reset, restore, stash, or discard user work.
- Stop for unrelated tracked changes, conflicts, unexpected divergence
  requiring force, repository authentication failure, secrets, or a genuine
  unrecoverable required-gate failure.
- Commit completed work in focused, independently verified increments.
- Push only the explicitly authorized branch and never use force.
- Do not merge, tag, publish, or modify protected branches without explicit
  authorization.

## Test discipline

Automated tests use injected fakes and local-only resources. Do not use real
ADB devices, Frida, Objection, networks, external terminals, or host processes
unless a separately authorized manual acceptance step requires them.

During implementation:

1. Run the requested baseline gates before source edits.
2. Run focused tests for the changed area.
3. Run compilation and `git diff --check` at checkpoints.
4. Run only relevant GUI smoke while iterating.
5. Do not rerun the full suite after every small edit.

Before a final source commit or merge, run:

```bash
python -m unittest discover -s tests -v
python -m compileall -q app main.py
git diff --check
python scripts/run_release_checks.py
python main.py --version
python main.py --self-test
```

Run the complete requested GUI matrix once at the final gate. After any
modification, run the appropriate tests and compilation checks, review the
exact diff, and provide a concise diff and commit summary.

## Standard workflow and efficiency

1. Read this file, inspect the repository, and report the exact files to add or
   modify before editing.
2. Continue automatically unless a defined stop condition occurs.
3. Prefer one focused workstream and one planned commit per prompt.
4. Reuse this file and applicable skills instead of repeating permanent rules.
5. Do not rerun completed phases after compaction or interruption; resume from
   the exact repository state and preserve completed work.
6. After editing, run focused checks, review the diff boundary, commit only the
   completed workstream, run final gates once, and push only when authorized.
7. Report commits, files, tests, GUI checks, limitations, protected paths left
   untouched, final branch synchronization, and tracked status.
