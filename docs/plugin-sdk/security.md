# Security Model

Third-party packages start untrusted and disabled. Inspection rejects traversal, symlink escapes, oversized archives, unknown capabilities, unsupported contributions, absolute paths, and missing files. Static validation never imports code.

Loaded Python is trusted code and cannot be perfectly sandboxed in-process. The worker offers bounded JSON request/response and process cleanup, not a hardened sandbox. Its environment allow-list omits common credential variables. SUS-ADB performs no signature identity claim, network lookup, automatic trust, download, or update.
