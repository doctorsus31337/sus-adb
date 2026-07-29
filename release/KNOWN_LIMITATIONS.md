# Known limitations

- RC4 is a prerelease. Linux and Windows packages are unsigned.
- Windows is distributed as a portable extracted directory, not an installer.
  Run it only after extracting the complete archive.
- Linux is distributed as a one-folder archive; desktop integration and
  system-wide installation remain manual.
- Optional Android, ADB, Frida, Objection, and other external tools are not
  downloaded or installed automatically. The Python Frida API is bundled in
  standalone packages, while frida-tools, frida-server, and Objection remain
  separately installed external tools.
- Console completion does not include fuzzy search, filesystem or path
  completion, arbitrary host-shell expansion, live device enumeration, or
  persisted history.
- Script Studio is included, but RC4 does not bundle a reviewed core curated
  script pack; user-local and third-party scripts remain separately reviewed
  local content.
- In-process trusted plugins are trusted Python code, not a hardened sandbox.
- Plugin SDK 1.1 does not expose unrestricted subprocess, shell, filesystem,
  network, ADB-shell, Frida, or Objection access.
- Generated plugins remain untrusted and disabled until explicitly reviewed.
- Static analysis can identify compatibility and packaging problems, but it
  does not prove third-party code is safe.
- The legacy branding multi-root smoke may emit pre-existing CustomTkinter
  teardown notices while its branding assertions pass. The authoritative
  isolated full-application and packaged shutdown probes must remain clean.
- PDF report generation is outside v1; offline HTML, Markdown, and JSON are
  supported.
- No stable 1.0.0 release is created by the RC4 publication.
