# SUS Companion Plugin SDK v1.1

The host accepts Plugin API `1.0` and `1.1`; existing 1.0 addons require no changes. Version 1.1 adds immutable host-rendered forms, explicit actions, confirmations, progress, cancellation, refresh, and safe navigation. See [interactive contracts](interactive.md) and the [migration guide](migration-1.1.md).

Start with the disabled, zero-capability `plugins/official/skeleton_module` v0.2.0 template. Inspection, installation, trust, capability approval, enable, load, and open remain separate; panel construction starts no work.

`plugins/official` is a bundled, read-only source catalog. Official packages remain uninstalled and inactive until explicit install, digest trust, capability approval, enable, and load. The harmless example is packaging validation material; installed third-party packages live in mutable user storage; Skeleton derivatives are user-created packages with new IDs and digests.

Python plugins run as trusted code when loaded. The in-process loader is not a security sandbox. Parsers and report processors may use the optional worker for crash containment, but v1 does not claim hardened isolation.

No marketplace, download, update, upload, or automatic activation is provided.
