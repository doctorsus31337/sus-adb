# Plugin Manager

Third-party plugins begin disabled and untrusted. Installation and validation never import code. Trust is digest-bound; capability approval, enablement, and loading are separate. In-process Python plugins are trusted code, not a hardened sandbox. No marketplace/update exists in v1.

The Official Catalog lists bundled Git-tracked source separately from installed packages. Catalog discovery never installs, trusts, approves, enables, or loads. The harmless example remains packaging/SDK sample data; official packages are explicitly installable; third-party packages use local import; Skeleton derivatives are user-created packages with independent IDs and trust.
