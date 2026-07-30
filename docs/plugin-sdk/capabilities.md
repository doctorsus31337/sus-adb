# Capabilities

Capabilities are denied by default and approved per plugin digest. High-impact capabilities require explicit confirmation. At every high-impact call, the API façade also checks the active assessment session and scope; excluded scope categories override plugin approval.

The v1 values are defined in `app/plugins/plugin_capabilities.py`. Approval never exposes unrestricted subprocess, filesystem, Tk, credentials, or raw service objects.

`read-device-logs` is a privacy-sensitive, read-only capability for a bounded
host-owned Logcat façade. It also requires `read-selected-device`. It does not
grant generic ADB shell, device-buffer clearing, filesystem, network, Frida,
Objection, host-process, or device-state access. Device logs may contain
identifiers, paths, messages, tokens, account information, and application
data, so approval is explicit and remains bound to the exact package digest.
