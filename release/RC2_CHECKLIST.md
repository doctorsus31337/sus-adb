# SUS Companion 1.0.0 RC2 release checklist

RC2 publication is permitted only when every gate applies to the same exact
release commit.

- [ ] Source unit suite, compilation, diff check, self-test, and diagnostics
- [ ] Complete isolated GUI smoke matrix and clean shutdown
- [ ] Immutable local Linux one-folder build
- [ ] Linux CLI, GUI, manifest, checksum, build-info, and privacy verification
- [ ] GitHub Linux package job
- [ ] GitHub Windows package job
- [ ] Downloaded Linux archive integrity and privacy verification
- [ ] Downloaded Windows archive integrity and privacy verification
- [ ] Preferred `sus-companion` and compatibility `sus-adb` launchers
- [ ] Exact `release/1.0.0-rc.2` ref and commit in both build-info files
- [ ] Six official addons, themes, documentation, and CustomTkinter resources
- [ ] Exact release source promoted to `main`
- [ ] Annotated `v1.0.0-rc.2` tag points to the packaged release commit
- [ ] GitHub Release is explicitly marked prerelease
- [ ] Only validated platform publication assets are attached

Packages are unsigned. Windows is an extract-and-run portable folder, not an
installer.
