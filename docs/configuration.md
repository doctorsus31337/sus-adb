# Configuration

Configuration is deterministic JSON in the user-local platform directory, schema version 3. Writes are atomic; migrations create a backup; malformed files are quarantined. Secrets are prohibited. Explicit exports may redact local paths.
