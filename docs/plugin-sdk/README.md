# SUS Companion Plugin SDK v1

The local Plugin SDK extends SUS Companion without changing core files. The stable `susadb.*` plugin IDs and Plugin API v1 remain unchanged for compatibility. A package is inspected and stored disabled; those steps never import it. Package-digest trust, requested-capability approval, enablement, loading, and window opening are distinct explicit states. A zero-capability package still needs explicit digest trust, but it has no permission grant to review.

Start with `plugins/examples/hello_plugin`. Its manifest is disabled, requests no device or network capability, and contributes only local read-only UI/report/script metadata.

`plugins/official` is a bundled, read-only source catalog. Official packages remain uninstalled and inactive until explicit install, digest trust, capability approval, enable, and load. The harmless example is packaging validation material; installed third-party packages live in mutable user storage; Skeleton derivatives are user-created packages with new IDs and digests.

Python plugins run as trusted code when loaded. The in-process loader is not a security sandbox. Parsers and report processors may use the optional worker for crash containment, but v1 does not claim hardened isolation.

No marketplace, download, update, upload, or automatic activation is provided.
