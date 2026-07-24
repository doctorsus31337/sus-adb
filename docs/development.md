# Development

Follow `AGENTS.md`, use feature branches, preserve modular boundaries, and keep Tk work on the GUI thread. Tests use fakes and local temporary files only. Install development dependencies separately and run release checks before review.

New heavyweight workspaces must be lazy by default. Declare the panel factory in a GUI-thread `LazyPanelHost`, keep worker-safe preparation immutable, hydrate shared state in the host's ready callback, and register cleanup only after construction. Do not perform filesystem discovery, tool probing, device work, plugin indexing, or widget creation merely because an unopened tab exists.
