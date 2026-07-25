"""Redacted local crash reports; never submitted automatically."""
from __future__ import annotations
import json,re,traceback,uuid
from dataclasses import dataclass
from pathlib import Path
from app.core.assessment_scope import now
@dataclass(frozen=True,slots=True)
class CrashReport:
    report_id:str;timestamp:str;app_version:str;platform:str;exception_type:str;message:str;traceback_text:str;recent_logs:tuple[str,...]=();workspace_names:tuple[str,...]=();plugin_id:str=""
    def to_dict(self):return {k:getattr(self,k) for k in self.__dataclass_fields__}
class CrashReporter:
    def __init__(self,directory,metadata,log_tail=lambda:()):self.directory=Path(directory).resolve();self.metadata=metadata;self.log_tail=log_tail
    @staticmethod
    def redact(text):
        text=re.sub(r"(?i)(password|token|secret)\s*[:=]\s*\S+",r"\1=[REDACTED]",str(text));text=re.sub(r"(?:/home/[^/\s]+|C:\\Users\\[^\\\s]+)","[LOCAL-HOME-REDACTED]",text);return text.replace("-----BEGIN PRIVATE KEY-----","[PRIVATE-KEY-REDACTED]")
    def capture(self,exc,workspace_names=(),plugin_id=""):
        report=CrashReport(str(uuid.uuid4()),now(),self.metadata.version,self.metadata.platform_name,type(exc).__name__,self.redact(exc),self.redact("".join(traceback.format_exception(exc))),tuple(self.redact(v) for v in self.log_tail()),tuple(Path(v).name for v in workspace_names),plugin_id)
        try:self.directory.mkdir(parents=True,exist_ok=True);path=self.directory/f"crash-{report.report_id}.json";path.write_text(json.dumps(report.to_dict(),indent=2,sort_keys=True)+"\n",encoding="utf-8")
        except OSError:path=None
        return report,path
