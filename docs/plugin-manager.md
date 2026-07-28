# Plugin Manager

Third-party plugins begin disabled and untrusted. Installation and validation never import code. Trust is digest-bound; capability approval, enablement, and loading are separate. In-process Python plugins are trusted code, not a hardened sandbox. No marketplace/update exists in v1.

The Official Catalog lists bundled Git-tracked source separately from installed packages. Catalog discovery never installs, trusts, approves, enables, or loads. The harmless example remains packaging/SDK sample data; official packages are explicitly installable; third-party packages use local import; Skeleton derivatives are user-created packages with independent IDs and trust.

Operational work opens from the dedicated Add-ons Center or Addons menu. Plugin Manager remains the administrative surface for trust, permissions, diagnostics, quarantine, and uninstall. Closing a detached window does not unload its addon.

The **Plugin Developer Workbench** statically inspects an explicitly selected
local folder or ZIP, exports deterministic redacted reports, and can build a
deterministic ZIP. It never imports candidate code or runs candidate tests.
Forwarding a reviewed candidate invokes this same Plugin Manager installation
path again; installation stores it disabled and does not trust, approve,
enable, load, or open it.

Plugin API 1.1 actions remain behind the same digest trust, capability,
enablement, load, and open gates. The host rechecks required approvals
immediately before a callback and owns confirmation, worker execution,
progress, cancellation, navigation, refresh, and unload cleanup.
