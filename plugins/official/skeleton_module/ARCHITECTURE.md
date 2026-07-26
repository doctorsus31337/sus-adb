# Architecture

```text
manifest -> static inspection -> disabled store -> digest trust -> capability approval
         -> explicit enable -> explicit load -> public PluginAPI façades
         -> owned contributions -> explicit unload -> unregister and worker cleanup
```

Selected device, selected target, active scope, timeline, evidence, and findings are sanitized façade interactions. Raw services remain host-owned.

API 1.1 flow: immutable form/action specs → host validation → explicit click
→ capability recheck → host worker → bounded result → host refresh/navigation.
Close or unload invalidates ownership and stale results are discarded.
