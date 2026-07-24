"""Advisory static validation for Script Studio sources."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from app.core.script_descriptor import ScriptDescriptor


@dataclass(frozen=True, slots=True)
class ScriptValidation:
    valid: bool
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    features: tuple[str, ...] = ()
    changes_runtime: bool = False
    suggestions: tuple[str, ...] = ()
    advisories: tuple[str, ...] = ()


class ScriptValidator:
    PLACEHOLDER = re.compile(r"\{\{[^}]+}}|\$\{[^}]+}")
    STATE_APIS = ("Interceptor.attach", "Interceptor.replace", "Memory.write", "Java.registerClass", ".implementation =")

    def __init__(self, compiler: Callable[[str], object] | None = None, max_size: int = 2_000_000):
        self.compiler = compiler
        self.max_size = max_size

    def validate(self, descriptor: ScriptDescriptor, source: str | None) -> ScriptValidation:
        errors, warnings, features, suggestions, advisories = [], [], [], [], []
        text = source or ""
        if not text.strip():
            errors.append("The script source is empty.")
        if Path(descriptor.path).suffix.casefold() == ".ts":
            errors.append("Raw TypeScript is editable metadata only; compile it to JavaScript before loading.")
        if len(text.encode("utf-8")) > self.max_size:
            errors.append(f"The script exceeds the {self.max_size}-byte size limit.")
        if not descriptor.metadata_path:
            warnings.append("No metadata file is associated with this script.")
        if descriptor.sha256:
            from app.core.script_library import ScriptLibrary
            if ScriptLibrary.digest_bytes(text.encode()) != descriptor.sha256:
                warnings.append("The digest changed since the last metadata review.")
        if self.PLACEHOLDER.search(text):
            warnings.append("Unexpanded placeholder values were detected.")
        for opening, closing in (("(", ")"), ("[", "]"), ("{", "}")):
            if text.count(opening) != text.count(closing):
                warnings.append(f"Possible unmatched {opening}{closing} delimiters.")
        changes = any(api in text for api in self.STATE_APIS)
        if changes:
            features.append("state-changing APIs")
        if "rpc.exports" in text:
            features.append("rpc.exports")
        if "send(" in text:
            features.append("send")
        if "recv(" in text:
            features.append("recv")
        if "Java." in text and "Java.available" not in text:
            suggestions.append("Java APIs are used without checking Java.available.")
        if self.compiler and not errors:
            try:
                self.compiler(text)
            except Exception as exc:
                errors.append(f"Frida compile validation failed: {exc}")
        advisories.append("Static validation is advisory and cannot prove third-party code is safe.")
        return ScriptValidation(
            not errors,
            tuple(errors),
            tuple(dict.fromkeys(warnings)),
            tuple(features),
            changes,
            tuple(dict.fromkeys(suggestions)),
            tuple(dict.fromkeys(advisories)),
        )
