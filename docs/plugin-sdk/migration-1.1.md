# Migrating from Plugin API 1.0 to 1.1

Plugin API 1.0 remains supported unchanged. Do not rewrite a 1.0 manifest
unless the add-on needs 1.1 interactions.

Declare API `1.1`, retain stable plugin/contribution IDs, and add explicit
immutable actions to the existing panel. Start no work in panel construction.
Use host-rendered forms, real minimal capabilities, exact context binding,
confirmation for state changes, bounded progress, and cooperative
cancellation.

Common mistakes include `.success` instead of `.ok`, private `app.core` or
`app.gui` imports, plugin-owned `Tk()`/`CTk()`, fake capability names, direct
subprocess/shell use, blocking Tk, returning widgets, logging sensitive form
values, assuming context cannot change, and starting work during construction.

Use fake-driven tests and the non-executing Workbench, build a deterministic
ZIP, then follow install, digest trust, capability approval, enable, load, and
open as separate explicit lifecycle steps.
