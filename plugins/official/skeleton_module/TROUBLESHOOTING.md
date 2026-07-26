# Troubleshooting

- Missing entry point: keep the manifest path package-relative.
- Digest changed: reinstall/review and explicitly approve the new digest.
- Capability denied: declare it, approve it, and ensure active scope permits it.
- Contribution missing: load explicitly and use a unique owned ID.
- UI callback failure: use host marshalling; never retain raw Tk.
- Action unavailable: verify the exact digest still has every declared capability.
- Stale result ignored: the window closed, plugin unloaded, or context ownership changed.
