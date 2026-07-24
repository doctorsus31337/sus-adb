# Known limitations

- RC1 binaries are not code-signed and no installer is provided.
- Windows packaging has static and CI definitions but requires a representative Windows build and launch confirmation.
- The Linux one-folder package passed local isolated validation; a clean representative Linux machine remains pending.
- The Python Frida API is bundled in standalone packages. External Android/security CLI tools, including frida-tools, Objection, and frida-server, remain optional and installed separately.
- Script Studio is included, but RC1 does not bundle a reviewed core curated script pack; user-local and third-party scripts remain separately reviewed local content.
- In-process trusted plugins are trusted Python code, not a hardened sandbox.
- PDF report generation is outside v1; offline HTML, Markdown, and JSON are supported.
- Current-testing artifacts are unsigned acceptance builds and are not GitHub Releases.
