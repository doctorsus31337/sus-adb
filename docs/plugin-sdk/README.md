# SUS-ADB Plugin SDK v1

The local Plugin SDK extends SUS-ADB without changing core files. A package is inspected and stored disabled; those steps never import it. Trust approval, capability approval, enablement, and loading are distinct explicit actions.

Start with `plugins/examples/hello_plugin`. Its manifest is disabled, requests no device or network capability, and contributes only local read-only UI/report/script metadata.

`plugins/official` is a bundled, read-only source catalog. Official packages remain uninstalled and inactive until explicit install, digest trust, capability approval, enable, and load. The harmless example is packaging validation material; installed third-party packages live in mutable user storage; Skeleton derivatives are user-created packages with new IDs and digests.

Python plugins run as trusted code when loaded. The in-process loader is not a security sandbox. Parsers and report processors may use the optional worker for crash containment, but v1 does not claim hardened isolation.

No marketplace, download, update, upload, or automatic activation is provided.
