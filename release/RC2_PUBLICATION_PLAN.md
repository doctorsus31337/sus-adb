# SUS Companion 1.0.0 RC2 publication plan

This document records the gated publication sequence for the explicitly
authorized `release/1.0.0-rc.2` prerelease.

## Acceptance prerequisites

- Every operator-experience workstream is committed and pushed on
  `feature/operator-experience-reliability`.
- The full fake-only unit suite, compilation, release checks, self-test,
  diagnostics, GUI matrix, Linux package verification, and Windows package
  workflow pass at the exact candidate commit.
- Representative Windows and Linux launches confirm responsive splash, lazy
  workspaces, addon focus lifecycle, compact windows, Sessions Center,
  recovery workflows, Learning Center, and clean shutdown.
- Build metadata identifies the exact candidate commit and selected ref.
- The package privacy audit confirms that no credentials, keys, tokens,
  user configuration, plugin state, local scripts, cases, evidence, reports,
  logs, APKs, firmware, Frida binaries, recovered files, or caches are present.

## Publication sequence

1. Create `release/1.0.0-rc.2` from the verified recovery merge.
2. Run all source, GUI, local Linux package, integrity, and privacy gates.
3. Run the manual **Package Current Testing Build** workflow against that exact
   ref and retain its Linux/Windows verification reports.
4. Verify checksums, manifests, build-info JSON, legacy `sus-adb` launchers,
   and SUS Companion branding on both platforms.
5. Promote the exact passing source commit to `main`.
6. Tag the exact packaged commit as `v1.0.0-rc.2`.
7. Create a GitHub prerelease and attach only the validated publication files.

No tagging or GitHub Release step is automated by the packaging workflow.
