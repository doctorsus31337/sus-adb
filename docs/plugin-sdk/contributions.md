# Contributions

Supported types are dashboard cards, Pentest panels, Tools actions, Script Studio assets, Objection recipes, diagnostics, evidence processors, finding templates, report sections/profiles, parsers, and assessment actions.

Every registered item has a stable ID and plugin owner. Duplicate IDs are rejected. A failed registration rolls back that plugin only; unload unregisters all of its contributions. Assessment actions declare capability/scope requirements, classification, preview, confirmation, execution, and rollback guidance.

Plugin panel factories return immutable `PluginPanelSpec`/`PluginView` data. The host owns Tk construction and navigation, so plugins never retain a Tk root or import private GUI internals.

## Addon presentation modes

Public `AddonCardSpec` and `AddonWindowSpec` data select `embedded`, `window`, or `hybrid` presentation. Addons provide immutable content; the core owns every `CTkToplevel`, theme, singleton lookup, focus operation, geometry clamp, close protocol, and cleanup. Closing a window leaves the addon loaded; unload and uninstall close all owned windows.

The top-level **Addons** menu and focused **Add-ons Center** preserve available, installed, capability-approved, enabled, loaded, and window-open as separate states. Opening either surface changes none of them. Plugins never receive the raw Tk root.
