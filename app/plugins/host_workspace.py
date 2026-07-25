"""GUI-neutral registration for capability-gated host addon workspaces."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class HostWorkspaceBinding:
    factory: object
    required_capability: str = ""
    device_selector: bool = False


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
    if (
        binding.required_capability
        and binding.required_capability not in set(approved_capabilities)
    ):
        return (
            None,
            "Host workspace requires approved capability: "
            f"{binding.required_capability}",
        )
    return binding, ""
