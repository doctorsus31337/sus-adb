# Testing

Tests use synthetic text/images, fake device/runtime providers, and temporary directories. They contact no device, ADB, Fastboot, Frida, Objection, network, firmware service, recovery service, or real subprocess. Validate install/enable/load separation, scope override, bounded operations, cancellation, deterministic exports, unload cleanup, and package policy.
