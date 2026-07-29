# User Guide

The principal workspaces are Workspace Home, Console, Instrumentation, Script
Studio, and Pentest. Only one is visible at a time. Home is the default landing
surface and provides one Open action for Console, Instrumentation, Device
Recovery, Script Studio, Pentest, and Sessions. It performs no device or tool
scan. Use the Gothic title, **View → Home**, or **Alt+Home** to return.

The compact device dock remains visible above the active workspace. Its
collapsed state shows the explicitly selected device and ADB state. Expand it
to view full serials, connection states, and the device list. Refresh and
selection remain explicit; expanding the drawer does not contact or modify a
device, and SUS Companion never silently selects a replacement device.

Guided mode uses plain descriptions and one recommended next step on Home.
Advanced mode adds compact selected serial/target context. Both modes retain
the same backend capabilities.

The Pentest dashboard navigates to scoped ADB, Runtime, Network, Storage, APK,
Findings/Reports, Plugins, Timeline, Evidence, Notes, and Changes. Add-ons
Center, Sessions Center, Device Rescue, Frida/Objection Assistants, Learning
Center, Context Help, Diagnostics, and Advanced Command Reference remain
detached windows. Long operations run in background workers; missing optional
tools reduce only their related workflows.

The integrated Console supports bounded Android Platform-Tools discovery,
connection-state commands, and a deliberately narrow Fastboot family:
version/help, device discovery, and `getvar` with an operator-entered Fastboot
serial. It never substitutes the selected ADB serial for a Fastboot transport.
Flashing, wiping, locking/unlocking, rebooting, OEM, partition, image, and
unknown Fastboot operations are rejected rather than handed to a terminal.
Wireless ADB pairing is deferred to a dedicated future workflow so pairing
codes and interactive secrets are not casually retained in Console history or
transcripts. ADB root/remount/verity, transport-mode switching, sideload, and
arbitrary shell expansion remain outside this milestone.
