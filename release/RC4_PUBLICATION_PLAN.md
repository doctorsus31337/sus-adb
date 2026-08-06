# SUS Companion 1.0.0 RC4 publication plan

This document records the gated publication sequence for the explicitly
authorized `release/1.0.0-rc.4` prerelease.

## Accepted source

- Recovery and the RC4 branch begin at accepted feature commit
  `b1888714102c79b220bbb20953a5c720a4b41402`.
- Every source and isolated GUI gate must pass before the RC4 metadata commit
  is made.
- The metadata commit becomes the immutable Linux/Windows package and tag
  target. The later `main` publication merge is never the tag target.
- Any packaging-only correction is a separate commit and replaces the earlier
  immutable target only after all required gates pass again.

## Package prerequisites

- Export the exact metadata commit to a new disposable directory outside the
  checkout and inject version `1.0.0-rc.4`, its exact commit, selected ref
  `release/1.0.0-rc.4`, and `rc` channel.
- Verify the local Linux one-folder package, both launchers, build-info,
  release manifest, checksums, verification report, branding, Pillow/Tk frozen
  modules, Plugin API 1.1, official add-ons, Command Assistant, Wizard,
  Workbench, and privacy exclusions.
- Dispatch the read-only packaging workflow for the exact RC4 ref and require
  both Linux and Windows jobs from the same run to succeed.
- Download only that successful run’s artifacts into a fresh disposable
  directory and verify both platforms independently before promotion,
  tagging, or publication.

## Publication sequence

1. Promote the exact RC4 source to `main` with the authorized no-fast-forward
   publication merge and run the complete source and publication-critical GUI
   gate.
2. Create annotated tag `v1.0.0-rc.4` at the packaged metadata commit.
3. Create the non-draft GitHub prerelease titled
   **SUS Companion 1.0.0 RC4** using the committed RC4 release notes.
4. Upload only the 12 independently validated Linux and Windows publication
   assets from the single successful workflow run.
5. Verify remote title, tag target, prerelease state, release-notes body,
   asset inventory, and archive digests.
6. Synchronize recovery to the verified metadata commit, rerun its full source
   gate, and finish on the clean RC4 branch.

No packaging workflow step tags, merges, or publishes. RC1, RC2, and RC3
remain unchanged, and no stable `1.0.0` release is created.
