# SUS Companion 1.0.0 RC4 release checklist

RC4 publication is permitted only when every gate applies to the exact
metadata commit on `release/1.0.0-rc.4`.

- [ ] Source unit suite, compilation, diff check, release checks, self-test,
  and diagnostics
- [ ] Complete isolated GUI matrix at 100%, 125%, and 150% scaling
- [ ] Universal scrolling, Console Command Assistant, Console read-only,
  application display protection, and Script Studio real-shell matrices
- [ ] Clean application shutdown with zero residual workers, callbacks,
  bindings, or temporary resources
- [ ] Immutable local Linux one-folder build from the exact metadata commit
- [ ] Linux CLI, GUI, manifest, checksum, build-info, and privacy verification
- [ ] GitHub Linux and Windows package jobs from one successful workflow run
- [ ] Independently downloaded Linux and Windows archive verification
- [ ] Preferred `sus-companion` and compatibility `sus-adb` launchers
- [ ] Exact `release/1.0.0-rc.4` ref, metadata commit, and `rc` channel
- [ ] Six official add-ons, Plugin API 1.1, branding, themes, documentation,
  Command Assistant, Project Wizard, Workbench, Pillow, Frida, and
  CustomTkinter resources
- [ ] No protected paths, user-local state, caches, bytecode, developer paths,
  local scripts, device data, or generated operator content
- [ ] Exact release source promoted to `main` only after both packages pass
- [ ] Annotated `v1.0.0-rc.4` tag points to the packaged metadata commit
- [ ] GitHub Release is a published prerelease, not a draft
- [ ] Exactly the 12 independently validated publication assets are attached
- [ ] Recovery is synchronized to the metadata commit without history rewrite

Packages are unsigned. Windows is an extract-and-run portable folder, not an
installer. No stable 1.0.0 release is created.
