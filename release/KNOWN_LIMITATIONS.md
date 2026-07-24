# Known limitations

- RC2 is a prerelease. Linux and Windows binaries are not code-signed.
- Windows is distributed as a portable extracted folder, not an installer. Run it only after extracting the complete archive.
- Linux is distributed as a one-folder archive; desktop integration and system-wide installation remain manual.
- The Python Frida API is bundled in standalone packages. External Android/security CLI tools, including frida-tools, Objection, and frida-server, remain optional and installed separately.
- Script Studio is included, but RC2 does not bundle a reviewed core curated script pack; user-local and third-party scripts remain separately reviewed local content.
- In-process trusted plugins are trusted Python code, not a hardened sandbox.
- PDF report generation is outside v1; offline HTML, Markdown, and JSON are supported.
- External Android/security tools are not downloaded or installed automatically.
