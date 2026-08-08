# SUS Companion 1.0.0 RC3 publication plan

This document records the gated publication sequence for the explicitly
authorized `release/1.0.0-rc.3` prerelease.

## Accepted source

- Recovery and the RC3 branch began at the accepted Wizard/reliability commit.
- The GUI acceptance harness isolates its configuration and relative
  assessment workspace from the caller’s working directory.
- Every source and GUI gate must pass before the RC3 metadata commit is made.
- The metadata commit becomes the immutable Linux/Windows package and tag
  target. The later `main` publication merge is never the tag target.

## Package prerequisites

- Export the exact metadata commit to a disposable directory outside the
  checkout and inject its version, commit, selected ref, and `rc` channel.
- Verify the local Linux one-folder package, preferred and compatibility
  launchers, build-info, release manifest, checksums, verification report,
  branding, Plugin API 1.1, official add-ons, Wizard, Workbench, and privacy.
- Dispatch the read-only packaging workflow for the exact RC3 ref and require
  both Linux and Windows jobs from the same run to succeed.
- Download that run’s artifacts to a fresh disposable directory and verify
  both platforms independently before promotion or publication.

## Publication sequence

1. Promote the exact RC3 source to `main` with the authorized no-fast-forward
   publication merge and run the complete source gate.
2. Create annotated tag `v1.0.0-rc.3` at the packaged metadata commit.
3. Create the non-draft GitHub prerelease titled
   **SUS Companion 1.0.0 RC3** using the committed RC3 release notes.
4. Upload only the 12 independently validated Linux and Windows publication
   assets from the single successful workflow run.
5. Verify remote title, tag target, prerelease state, release-notes body,
   asset inventory, and archive digests.
6. Synchronize recovery to the verified metadata commit, rerun its full source
   gate, and finish on the clean RC3 branch.

No packaging workflow step tags, merges, or publishes. RC2 remains unchanged,
and no stable `1.0.0` release is created.
