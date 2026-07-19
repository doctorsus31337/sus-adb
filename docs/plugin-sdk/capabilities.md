# Capabilities

Capabilities are denied by default and approved per plugin digest. High-impact capabilities require explicit confirmation. At every high-impact call, the API façade also checks the active assessment session and scope; excluded scope categories override plugin approval.

The v1 values are defined in `app/plugins/plugin_capabilities.py`. Approval never exposes unrestricted subprocess, filesystem, Tk, credentials, or raw service objects.
