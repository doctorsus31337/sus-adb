# Test matrix

| Area | Local fake-only validation | Representative machine |
|---|---|---|
| Python unit suite | Required | CI: Linux and Windows |
| GUI construction | Xvfb where available | Linux and Windows |
| Linux package | Immutable-source one-folder build, publication archive, required resources, curated-asset report, manifest, checksums, CLI, GUI, and privacy audit | Local RC2 gate plus GitHub Actions |
| Windows package | Manual chosen-ref workflow, portable archive, build metadata, manifest, checksums, verification report, and privacy audit | GitHub Actions static/package gate |
| Windows UI/argv regressions | Destroyed-widget focus lifecycle, rapid addon state changes, terminal argv, and paths with spaces | CI: Windows |
| Android tools | Injected fakes only | Authorized test device |

No automated release check contacts a device or invokes optional security tools.
