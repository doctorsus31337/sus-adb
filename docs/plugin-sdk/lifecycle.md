# Lifecycle

1. Inspect a local directory or bounded ZIP without import.
2. Install into isolated disabled storage without execution.
3. Validate manifest, paths, digest, API, and declarations.
4. Review and approve trust for the exact digest.
5. Approve requested capabilities individually.
6. Enable explicitly.
7. Load explicitly; the digest is verified immediately beforehand.
8. Unload to unregister contributions; disable or uninstall separately.

Opening a case, discovering a directory, installing, or enabling never loads a plugin. Content changes invalidate trust and cause quarantine during verification.

Official catalog discovery adds no lifecycle state: it only inspects bundled tracked source. Explicit catalog installation enters step 2 and follows the same remaining lifecycle as third-party packages.
