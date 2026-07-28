# Plugin Project Scaffold Generator

The GUI-neutral project generator accepts immutable identity, contribution,
capability, and developer-intent specifications. It creates a deterministic
Plugin API 1.1 file plan before any selected destination is written.

The plan uses the official Skeleton architecture without modifying the bundled
Skeleton package. It contains a root manifest, public-only inert plugin source,
developer brief, architecture/tutorial/checklist/troubleshooting material, and
a static starter test.

Validation composes the canonical manifest model, production package inspector
and validator, official catalog identities, and Plugin Developer Workbench.
Generated Python is parsed and compiled statically but is never imported or
executed. A blocking production or Workbench finding prevents output.

Folder output is written to a temporary sibling and committed only after
complete validation. Existing output requires explicit overwrite confirmation;
failed generation preserves the previous destination and removes temporary
content. Plans contain no timestamps, random identifiers, machine paths,
usernames, secrets, locale-dependent values, or current-directory state.
