# Contributions

Supported types are dashboard cards, Pentest panels, Tools actions, Script Studio assets, Objection recipes, diagnostics, evidence processors, finding templates, report sections/profiles, parsers, and assessment actions.

Every registered item has a stable ID and plugin owner. Duplicate IDs are rejected. A failed registration rolls back that plugin only; unload unregisters all of its contributions. Assessment actions declare capability/scope requirements, classification, preview, confirmation, execution, and rollback guidance.

Plugin panel factories return immutable `PluginPanelSpec`/`PluginView` data. The host owns Tk construction and navigation, so plugins never retain a Tk root or import private GUI internals.
