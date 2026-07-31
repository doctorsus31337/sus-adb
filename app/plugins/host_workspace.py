"""GUI-neutral registration for capability-gated host addon workspaces."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class HostWorkspaceBinding:
    factory: object
    required_capability: str = ""
    device_selector: bool = False
    required_capabilities: tuple[str, ...] = ()

    def __post_init__(self):
        required = tuple(
            dict.fromkeys(
                (
                    *((self.required_capability,) if self.required_capability else ()),
                    *self.required_capabilities,
                )
            )
        )
        object.__setattr__(self, "required_capabilities", required)


def normalize_host_workspace_bindings(values):
    return {
        key: (
            value
            if isinstance(value, HostWorkspaceBinding)
            else HostWorkspaceBinding(value)
        )
        for key, value in dict(values or {}).items()
    }


def resolve_host_workspace(
    bindings,
    *,
    workspace_kind="",
    contribution_id="",
    approved_capabilities=(),
):
    binding = bindings.get(workspace_kind) or bindings.get(contribution_id)
    if binding is None:
        return None, ""
    missing = tuple(
        capability
        for capability in binding.required_capabilities
        if capability not in set(approved_capabilities)
    )
    if missing:
        return (
            None,
            "Host workspace requires approved capabilities: "
            f"{', '.join(missing)}",
        )
    return binding, ""
