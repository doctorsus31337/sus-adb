# Testing Plugins

Use temporary plugin stores and fake façades. Assert installation and validation never import the entry point. Test default-denied capabilities, scope exclusions, digest changes, unload cleanup, duplicate contribution rollback, callback failure containment, and worker timeout/crash behavior.

Tests must not contact ADB, Frida, a device, a network, or a real external process. The example plugin is suitable for static validation and explicit fake-loader tests.
