# Skeleton Module

This disabled, zero-capability package is a copyable Plugin API v1 learning template. It validates, installs, accepts digest-bound trust, enables, loads, unloads, and uninstalls while doing nothing externally. Read `TUTORIAL.md`, `ARCHITECTURE.md`, `EXERCISES.md`, `TROUBLESHOOTING.md`, and `CHECKLIST.md` before enabling commented examples.

Direct imports of private core services are prohibited because they bypass stable façades, capability approval, scope override, and lifecycle cleanup. Plugins never receive raw Tk, raw manager objects, unrestricted subprocess execution, arbitrary filesystem access, or secret-provider access.
