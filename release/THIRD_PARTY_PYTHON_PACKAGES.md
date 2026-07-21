# Python packages

Runtime dependencies are declared in `requirements.txt`; development and packaging tools are separated into `requirements-dev.txt` and `requirements-build.txt`. Installed distributions retain their upstream licenses. The release process must review dependency notices before redistribution.

Standalone packages include the bounded Python `frida` binding and its platform-native runtime for direct Script Studio and Runtime Explorer integration. They do not include frida-tools command-line programs, Objection, frida-server, or device binaries.
