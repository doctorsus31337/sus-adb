# SUS Companion 1.0.0-rc.2 publication plan

This document prepares a later `release/1.0.0-rc.2` publication after live
Linux and Windows acceptance. It does not authorize or create a branch, tag,
GitHub Release, or public artifact.

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

## Later publication sequence

1. Obtain explicit authorization after live acceptance.
2. Create `release/1.0.0-rc.2` from the accepted commit.
3. Run the manual **Package Current Testing Build** workflow against that exact
   ref and retain its Linux/Windows verification reports.
4. Verify checksums, manifests, build-info JSON, legacy `sus-adb` launchers,
   and SUS Companion branding on both platforms.
5. Prepare release notes and a final manual checklist from the verified
   artifacts.
6. Only with separate authorization, create the RC2 tag and GitHub Release and
   attach the already-verified artifacts.

No publication step is automated by the current-testing workflow.
