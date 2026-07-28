# Plugin API 1.1 interactive contracts

Declare `"plugin_api_version": "1.1"` to use immutable models from
`app.plugins.plugin_interactive`. Plugins return specifications; the host owns
widgets, theme, geometry, validation, confirmation, workers, navigation,
progress presentation, and cleanup.

```python
from app.plugins.plugin_interactive import (
    PluginActionResult, PluginActionSpec, PluginFieldSpec, PluginFormSpec,
)
from app.plugins.plugin_ui import PluginPanelSpec, PluginView

def inspect(request):
    return PluginActionResult(True, f"Validated {request.values['label']}")

def panel_spec(_context=None):
    form = PluginFormSpec("demo", (
        PluginFieldSpec("label", "Label", required=True, max_length=80),
    ))
    action = PluginActionSpec("demo.inspect", "Validate", inspect, form=form)
    return PluginPanelSpec(
        "Demo", (PluginView("Overview", "No work runs on open."),),
        actions=(action,),
    )
```

Fields support text, password, multiline, checkbox, choice, bounded integer,
and read-only values. IDs are unique. The host checks required values, choice
membership, length, and integer bounds before invoking a callback. Sensitive
values are masked and runtime-only; never put secrets in defaults, logs,
messages, rows, reports, or exception text.

Actions are informational, navigation, read-only, or state-changing. One
action runs per contribution and opening a panel invokes nothing.
State-changing actions require host confirmation. Cancellation invokes
nothing and confirmation is never remembered. Device/target bindings are
invalidated if the context changes before invocation.

Callbacks receive one immutable `PluginActionRequest`: validated values,
sanitized context, capability-approved selected identifiers where declared, a
cooperative cancellation query, and bounded progress publisher. They receive
no widget, event, root, manager, worker, secret provider, or private state. Use
`PluginActionResult.ok`; there is no `.success`.

Blocking callbacks use the host worker architecture. Progress uses
`PluginProgressUpdate(text, value)` from 0 to 1. Close/unload requests
cancellation and discards stale results. A result may provide bounded rows,
replacement panel, retry guidance, or `PluginNavigationSpec`.

Safe destinations are `workspace-home`, `console`, `instrumentation`,
`script-studio`, `pentest`, `addons-center`, `sessions-center`,
`workflow-recipes`, `environment-diagnostics`, `contextual-help`, and
`plugin-workbench`. Navigation performs no operational action.

Guided and Advanced modes use the same renderer. Plugins release narrow
resources in `deactivate`; subscriptions and host-owned work are removed on
unload. There is no unrestricted subprocess, shell, filesystem, network, ADB
shell, Frida, or Objection contract. Missing bounded façades are SDK
compatibility gaps.
