# Manifest

`manifest.json` declares a stable lowercase `plugin_id`, semantic `version`, descriptive metadata, `plugin_api_version`, portable `entry_point`, requested capabilities, and contributed components. Paths must be package-relative and may not contain `..`.

Contributions use `{contribution_id, contribution_type, title, factory, metadata}`. Installation computes the package digest; trust records bind approval to that exact digest. `enabled` defaults to false and does not grant trust or permissions.

Official manifests use the same API and validation rules. `trust_state` and `enabled` in source never grant runtime trust; mutable operator decisions live only in the local plugin store.
