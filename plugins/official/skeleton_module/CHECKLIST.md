# TODO conversion checklist

- [ ] New stable ID and display name; never reuse `susadb.skeleton-module`
- [ ] Semantic version and supported platforms
- [ ] Minimal explicit capabilities
- [ ] No private core/GUI imports
- [ ] API 1.1 actions are explicit; state changes have confirmation
- [ ] Unique field/action IDs and bounded runtime-only values
- [ ] Immutable inputs/results
- [ ] Selected device/target explicit
- [ ] Active-scope checks
- [ ] Bounded worker, buffers, files, bytes, recursion, cancellation
- [ ] Structured failures and cleanup
- [ ] Fake-only tests
- [ ] Digest-change, uninstall, and packaging tests
