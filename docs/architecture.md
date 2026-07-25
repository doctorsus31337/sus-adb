# Architecture

Core models/services contain no GUI dependencies. GUI panels compose services and marshal worker callbacks to Tk. Shared selected-device/target, Pentest, Frida, evidence, timeline, and plugin systems avoid hidden duplicates. Release services manage configuration/logging outside the repository.

The responsive startup path constructs only the root, splash, configuration/logging essentials, core service façades, navigation shell, device-sidebar shell, Console, and status bar. `LazyPanelHost` owns GUI-thread construction for Instrumentation, Script Studio, and Pentest. Pentest independently defers ADB Explorer, Runtime Explorer, Network, Storage, APK Laboratory, Findings/Reports, and Plugins until explicit selection.

Non-widget discovery runs through bounded workers after the Console has received an idle callback. Tk widgets are never constructed in workers. Lazy panels hydrate from the shared selected-device, selected-target, assessment, and plugin state after construction and own their normal cleanup once present.
