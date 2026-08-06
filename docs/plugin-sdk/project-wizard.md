# Plugin Project Wizard v1

Open **Tools → Plugin Project Wizard** or search for `plugin wizard` in the
Universal Command Palette. The Wizard creates a starter project from the
official Skeleton architecture. It does not implement an operational add-on,
scan the filesystem, execute generated Python, install a package, or remember
destination paths.

## Guided flow

1. **Project Type** selects the interactive Plugin API 1.1 window starter.
2. **Identity** records a stable derivative-owned plugin ID, semantic version,
   publisher details, platforms, and portable folder name. `susadb.*`
   identities are reserved.
3. **Contribution** records one canonical window contribution. The manifest
   and Python registration IDs must match.
4. **Capabilities** defaults to none. A declaration requests exact-digest
   approval; it does not implement an operation. High-impact declarations
   require acknowledgment.
5. **Developer Details** adds bounded intent and design notes to documentation,
   especially `DEVELOPER_BRIEF.md`. Never enter credentials or device history.
6. **Review** previews the file tree and manifest. **Validate Project**
   explicitly invokes production validation and Workbench static analysis.
7. **Generate** offers separate explicit folder, deterministic ZIP, Workbench
   handoff, and Developer Brief export actions.

Advanced mode exposes capability façade details and validation warnings. It
uses the same draft, generator, validation, and output implementation as Guided
mode, so switching modes does not rewrite identifiers.

## Identifiers and capabilities

Plugin and contribution IDs are stable ownership boundaries. Suggestions are
editable and do not claim global uniqueness. A contribution suggestion follows
the project ID until it is manually edited; after that, the Wizard does not
silently rewrite it.

Plugin-ID suggestions remove an exact repeated publisher-token prefix from the
project slug. Automatically suggested plugin IDs and folder names continue to
follow their inputs; manually edited values are operator-owned. Pressing a
Suggest button previews and confirms any replacement of an operator-owned
value. Review always shows the exact project folder and starter ZIP name, and
marks an intentionally retained custom folder.

Keep the recommended zero-capability profile unless the planned implementation
needs an existing documented host façade. Fake capabilities and unrestricted
filesystem, network, shell, subprocess, ADB, Frida, or Objection access are not
offered. Capability approval remains a later, explicit lifecycle action.

## Outputs and safety boundaries

Each native destination dialog is operator initiated; canceling it changes
nothing. Existing output requires confirmation. Folder writes use a temporary
sibling and atomic replacement with rollback. ZIP creation reuses the
Workbench deterministic package builder and production validation. The
Workbench handoff performs static analysis only.

The generated `tests/test_lifecycle.py` file produces one expected,
non-blocking Wizard advisory. Guided mode presents concise advisories, while
Advanced mode adds canonical rule provenance without duplicating the same
production and Workbench warning.

Generated projects remain disabled, untrusted, and operationally inert.
Installation, digest trust, capability approval, enable, load, and open remain
separate explicit actions. Static analysis can find structural and
compatibility problems but cannot prove that future edited code is safe.

The generated Developer Brief is intended to accompany the complete project
when collaborating with another LLM. It records exact IDs, capability intent,
public and private import boundaries, lifecycle rules, no-work-on-open and
confirmation rules, worker/cancellation expectations, cross-platform
requirements, tests, Workbench validation, lifecycle steps, and known SDK
compatibility gaps. Ask for complete files, not fragments.
