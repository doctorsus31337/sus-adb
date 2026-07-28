# SUS Companion 1.0.0 RC3 release checklist

RC3 publication is permitted only when every gate applies to the exact
metadata commit on `release/1.0.0-rc.3`.

- [ ] Source unit suite, compilation, diff check, release checks, self-test,
  and diagnostics
- [ ] Complete isolated GUI matrix at 100%, 125%, and 150% scaling
- [ ] Clean application shutdown with zero residual workers and callbacks
- [ ] Immutable local Linux one-folder build from the exact metadata commit
- [ ] Linux CLI, GUI, manifest, checksum, build-info, and privacy verification
- [ ] GitHub Linux and Windows package jobs from one successful workflow run
- [ ] Independently downloaded Linux and Windows archive verification
- [ ] Preferred `sus-companion` and compatibility `sus-adb` launchers
- [ ] Exact `release/1.0.0-rc.3` ref, metadata commit, and `rc` channel
- [ ] Six official addons, Plugin API 1.1, branding, themes, documentation,
  Project Wizard, Workbench, Pillow, Frida, and CustomTkinter resources
- [ ] No protected paths, user-local state, caches, bytecode, or developer path
- [ ] Exact release source promoted to `main` only after both packages pass
- [ ] Annotated `v1.0.0-rc.3` tag points to the packaged metadata commit
- [ ] GitHub Release is a published prerelease, not a draft
- [ ] Exactly the 12 independently validated publication assets are attached
- [ ] Recovery is synchronized to the metadata commit without history rewrite

Packages are unsigned. Windows is an extract-and-run portable folder, not an
installer.
