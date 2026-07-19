"""Non-destructive deterministic export redaction."""
from __future__ import annotations
import re
from dataclasses import dataclass
@dataclass(frozen=True,slots=True)
class RedactionRule:
    kind:str;value:str;replacement:str=""
@dataclass(frozen=True,slots=True)
class RedactionPreview:
    original:str;redacted:str;substitutions:tuple[dict,...];warnings:tuple[str,...]=()
class RedactionService:
    def __init__(self,rules=()):self.rules=tuple(rules)
    def preview(self,text):
        output=str(text);changes=[]
        for index,rule in enumerate(self.rules,1):
            token=rule.replacement or f"[REDACTED-{rule.kind.upper()}-{index}]"
            if rule.kind=="regex":
                try:output,count=re.subn(rule.value,token,output)
                except re.error as exc:raise ValueError(f"Invalid redaction pattern: {exc}") from exc
            else:count=output.count(rule.value);output=output.replace(rule.value,token)
            if count:changes.append({"rule":rule.kind,"matches":count,"replacement":token})
        warnings=() if self.rules else ("No explicit redaction rules are configured.",)
        return RedactionPreview(str(text),output,tuple(changes),warnings)
    def apply_data(self,value):
        if isinstance(value,dict):return {k:self.apply_data(v) for k,v in value.items()}
        if isinstance(value,(list,tuple)):return [self.apply_data(v) for v in value]
        return self.preview(value).redacted if isinstance(value,str) else value
    @staticmethod
    def likely_sensitive(text):
        patterns=(r"(?i)password\s*[:=]",r"(?i)authorization\s*:\s*bearer",r"-----BEGIN [A-Z ]+PRIVATE KEY-----")
        return tuple(p for p in patterns if re.search(p,str(text)))
