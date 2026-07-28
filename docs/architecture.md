# Architecture

Core models/services contain no GUI dependencies. GUI panels compose services and marshal worker callbacks to Tk. Shared selected-device/target, Pentest, Frida, evidence, timeline, and plugin systems avoid hidden duplicates. Release services manage configuration/logging outside the repository.

The responsive startup path constructs only the root, splash,
configuration/logging essentials, core service façades, the principal
navigation shell, lightweight Workspace Home, compact device dock, eager
Console, and status bar. A GUI-agnostic principal-workspace controller
normalizes Home, Console, Instrumentation, Script Studio, and Pentest routes so
Home cards, menus, the Gothic title, and keyboard shortcuts do not implement
parallel navigation.

`LazyPanelHost` owns GUI-thread construction for Instrumentation, Script Studio,
and Pentest. Pentest independently defers ADB Explorer, Runtime Explorer,
Network, Storage, APK Laboratory, Findings/Reports, and Plugins until explicit
selection. Detached singleton tools are not principal workspaces and remain
open when the principal view changes.

The device dock is a host-owned projection of the existing `DeviceManager`; it
does not duplicate discovery or expose a manager to plugins. Non-widget
discovery runs through bounded workers only after the Home shell has received
an idle callback or an operator explicitly requests it. Tk widgets are never
constructed in workers. Lazy panels hydrate from shared selected-device,
selected-target, assessment, and plugin state after construction and own their
normal cleanup once present.
