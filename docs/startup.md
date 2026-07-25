# Responsive startup

SUS Companion paints a typographic Gothic splash before service and workspace construction. Its progress labels correspond to real local bootstrap stages: Tk root, splash, configuration/logging, core services, and the responsive Console shell. Tips come from a bounded packaged JSON catalog; they are never downloaded and contain no personal data.

The latest startup report is available in **Tools → Environment Diagnostics → Startup**. It records monotonic start offsets, durations, success or failure, eager/deferred/on-demand classification, and UI/worker classification. Notes are bounded and local paths are redacted. SUS Companion sends no telemetry or analytics.

Console is eager. Instrumentation, Script Studio, Pentest, Plugin Manager, the Add-ons Center, detached addon windows, and Pentest operational sections are constructed only after explicit navigation. A first open may briefly show a loading state. Subsequent opens reuse the same panel. Shared device, target, assessment, and addon state is applied after construction.

After Console receives a responsive idle callback, environment checks and the initial selected-device refresh may run in background workers. Startup never automatically loads a plugin, starts Frida, performs an assessment action, or contacts a network service. Shutdown ignores unopened panels and cleans every panel or addon window that was actually constructed.

The public product is **SUS Companion — Android Security & Recovery Workstation**. The repository name, `sus-adb` CLI compatibility launcher, legacy configuration directory, `susadb.*` plugin IDs, schemas, cases, evidence, workspaces, event channels, and trust records remain compatible.
