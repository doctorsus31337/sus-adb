# Development

Follow `AGENTS.md`, use feature branches, preserve modular boundaries, and keep Tk work on the GUI thread. Tests use fakes and local temporary files only. Install development dependencies separately and run release checks before review.

New heavyweight workspaces must be lazy by default. Declare the panel factory in a GUI-thread `LazyPanelHost`, keep worker-safe preparation immutable, hydrate shared state in the host's ready callback, and register cleanup only after construction. Do not perform filesystem discovery, tool probing, device work, plugin indexing, or widget creation merely because an unopened tab exists.

Principal navigation must route through the shared workspace controller.
Workspace Home must remain a lightweight state projection: do not add scans,
tool probes, plugin discovery, filesystem traversal, or command execution to
its constructor. Detached tools should remain detached rather than becoming
new principal tabs.

The lazy Universal Command Palette is host-owned and routes through the shared
workspace controller, detached-window openers, AddonWindowHost, and Add-ons
Center. Keep its command specifications GUI-neutral and navigation-only.
Constructing or searching the palette must never scan, probe, or discover;
selection may only call an existing explicit destination opener and must never
attach, spawn, approve, enable, load, or install automatically.
