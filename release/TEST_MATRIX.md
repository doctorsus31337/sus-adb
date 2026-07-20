# Test matrix

| Area | Local fake-only validation | Representative machine |
|---|---|---|
| Python unit suite | Required | CI: Linux and Windows |
| GUI construction | Xvfb where available | Linux and Windows |
| Linux package | One-folder build, required resources, explicit zero-or-more curated-asset report, example plugin, manifest, checksums, CLI | Locally passed; representative clean machine pending |
| Windows package | Static definition, `release/**` CI packaging, and the same asset policy | Representative Windows build/launch pending |
| Android tools | Injected fakes only | Authorized test device |

No automated release check contacts a device or invokes optional security tools.
