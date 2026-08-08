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

Markdown and JSON reports provide stable Manifest, Capabilities,
Contributions, Findings, Update Comparison, Package Plan, and Limitation
summaries. Empty capability and contribution lists, a missing installed
package match, and an unavailable package plan are stated explicitly.

Local candidates that retain a bundled official add-on ID are blocked from
Plugin Manager handoff before installation. Exported educational templates
remain inspectable and reportable, but derivatives must choose a new stable
plugin ID and keep unique contribution IDs synchronized between the manifest
and Python registration.

For API 1.1 the Workbench indexes interactive models and reports `Plugin API
1.1 interactive contract detected`. Static checks cover IDs, bounds,
navigation, confirmations, capabilities, callback shape, sensitive defaults,
`.success` misuse, and 1.1 symbols under a 1.0 manifest where the AST supports
a deterministic conclusion. Candidate code is never executed.
