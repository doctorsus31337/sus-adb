# Architecture

Core models/services contain no GUI dependencies. GUI panels compose services and marshal worker callbacks to Tk. Shared selected-device/target, Pentest, Frida, evidence, timeline, and plugin systems avoid hidden duplicates. Release services manage configuration/logging outside the repository.
