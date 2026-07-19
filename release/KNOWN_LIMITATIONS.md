# Known limitations

- RC1 binaries are not code-signed and no installer is provided.
- Windows packaging has static and CI definitions but requires a representative Windows build and launch confirmation.
- The Linux one-folder package passed local isolated validation; a clean representative Linux machine remains pending.
- External Android/security tools are optional and installed separately.
- In-process trusted plugins are trusted Python code, not a hardened sandbox.
- PDF report generation is outside v1; offline HTML, Markdown, and JSON are supported.
