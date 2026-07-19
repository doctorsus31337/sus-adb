"""Tolerant, read-only Android component discovery."""
from __future__ import annotations
import re
from app.core.adb_explorer_models import ComponentRecord,ComponentType
from app.core.adb_package_service import ExplorerResult

class ADBComponentService:
    def __init__(self,adb):self.adb=adb;self.cache=()
    def discover(self,serial,package):
        if not serial or not package:return ExplorerResult(False,error="A selected device and explicit package are required.")
        result=self.adb.run("shell","dumpsys","package",package,serial=serial)
        if not result.ok:return ExplorerResult(False,result=result,error=result.output)
        records,warnings=self.parse(result.stdout,package,serial);self.cache=records
        return ExplorerResult(True,records,result,warning="; ".join(warnings) or None)
    @staticmethod
    def parse(text,package,serial=""):
        records=[];warnings=[];section=None;current=None;data={}
        headings={"activities":ComponentType.ACTIVITY,"services":ComponentType.SERVICE,"receivers":ComponentType.RECEIVER,"providers":ComponentType.PROVIDER}
        def flush():
            nonlocal current,data
            if current and section:
                records.append(ComponentRecord(section,package,current,data.get("exported"),data.get("enabled"),data.get("permission",""),tuple(data.get("actions",())),tuple(data.get("categories",())),tuple(data.get("authorities",())),data.get("process",""),serial))
            current=None;data={}
        for raw in text.splitlines():
            line=raw.strip();low=line.casefold()
            matched=next((v for k,v in headings.items() if low in {k,k+":"} or low.endswith(" "+k+":")),None)
            if matched:flush();section=matched;continue
            m=re.search(r"(?:[0-9a-f]+\s+)?("+re.escape(package)+r"/[\w.$]+)",line)
            if m and section:flush();current=m.group(1).split("/",1)[1];continue
            if not current:continue
            for key in ("exported","enabled"):
                m=re.search(rf"\b{key}=(true|false)",low)
                if m:data[key]=m.group(1)=="true"
            m=re.search(r"permission=([^\s}]+)",line);data["permission"]=m.group(1) if m else data.get("permission","")
            m=re.search(r"(?:Action|action):?\s*[\"']?([\w.]+)",line,re.I)
            if m:data.setdefault("actions",[]).append(m.group(1))
            m=re.search(r"(?:Category|category):?\s*[\"']?([\w.]+)",line,re.I)
            if m:data.setdefault("categories",[]).append(m.group(1))
            m=re.search(r"(?:authority|authorities)=([^\s}]+)",line,re.I)
            if m:data.setdefault("authorities",[]).extend(m.group(1).split(";"))
            m=re.search(r"processName=([^\s}]+)",line)
            if m:data["process"]=m.group(1)
        flush()
        if text.strip() and not records:warnings.append("No component records could be parsed from this Android version's dumpsys output.")
        unique={(r.component_type,r.component_name):r for r in records}
        return tuple(sorted(unique.values(),key=lambda r:(r.component_type.value,r.component_name.casefold()))),tuple(warnings)
    def filter(self,query="",component_type="All",exported_only=False,enabled_only=False):
        q=query.casefold();return tuple(r for r in self.cache if (component_type=="All" or r.component_type.value==component_type) and (not exported_only or r.exported is True) and (not enabled_only or r.enabled is True) and q in (r.component_name+" "+" ".join(r.intent_actions)).casefold())
