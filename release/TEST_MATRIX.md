# Test matrix

| Area | Local fake-only validation | Representative machine |
|---|---|---|
| Python unit suite | Required | CI: Linux and Windows |
| GUI construction | Xvfb where available | Linux and Windows |
| Linux package | One-folder build, resources, manifest, checksums, CLI | Locally passed; representative clean machine pending |
| Windows package | Static definition and CI validation | Representative Windows build/launch pending |
| Android tools | Injected fakes only | Authorized test device |

No automated release check contacts a device or invokes optional security tools.
