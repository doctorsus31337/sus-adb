# Skeleton Module

This disabled, zero-capability package is a copyable Plugin API v1 learning template. It validates, installs, accepts digest-bound trust, enables, loads, unloads, and uninstalls while doing nothing externally. Read `TUTORIAL.md`, `ARCHITECTURE.md`, `EXERCISES.md`, `TROUBLESHOOTING.md`, and `CHECKLIST.md` before enabling commented examples.

An exported template is an editable developer copy, not the bundled official package. Before installation, change `plugin_id`, the display name, and version; review every requested capability and never reuse `susadb.skeleton-module`. Editing the copy does not change the bundled source, and export does not install, trust, enable, load, or execute it. Install a completed derivative through Plugin Manager when ready.

Direct imports of private core services are prohibited because they bypass stable façades, capability approval, scope override, and lifecycle cleanup. Plugins never receive raw Tk, raw manager objects, unrestricted subprocess execution, arbitrary filesystem access, or secret-provider access.
