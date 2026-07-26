# Plugin Developer Workbench

The Plugin Developer Workbench performs bounded static analysis of an
explicitly selected plugin directory or ZIP. It reads bytes, parses JSON, and
uses Python AST and syntax compilation without importing candidate modules,
running candidate tests, invoking lifecycle methods, launching processes, or
contacting a network.

It composes the production package inspector and validator with
developer-oriented SDK, capability, contribution, packaging, and privacy
findings. `Compatible` means only that no blocking static compatibility issue
was identified. Static analysis does not prove third-party code is safe.

Selected source paths are runtime-only. Findings, comparisons, and future
exports use plugin-relative paths and redact suspected secret values.
